# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 University of Southern California
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
"""
GPU support under a connection to a hypervisor through libvirt.

"""

import os

from nova.compute import vm_states
from nova import db
from nova import exception
from nova import flags
from nova import utils
from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from nova.virt.disk import api as disk
from nova.virt.gpu import utils as gpu_utils
from nova.virt.libvirt import driver

import subprocess

libvirt = None

LOG = logging.getLogger(__name__)

gpu_opts = [
    cfg.StrOpt('user',
               default='/root',
               help='home directory of login user')
]

FLAGS = flags.FLAGS
FLAGS.register_opts(gpu_opts)

lxc_mounts = {}

class GPULibvirtDriver(driver.LibvirtDriver):
    def __init__(self, read_only=False):
        if FLAGS.connection_type == 'gpu':
            assert FLAGS.libvirt_type == 'lxc', "Only LXC is supported for GPU"
        super(GPULibvirtDriver, self).__init__()

        global libvirt
        if libvirt is None:
            libvirt = __import__('libvirt')
 
        gpu_utils.init_host_gpu()

    @property
    def host_state(self):
        if not self._host_state:
            self._host_state = \
                GPUHostState(self.read_only)
        return self._host_state

    def destroy(self, instance, network_info, block_device_info=None):
        super(GPULibvirtDriver, self).destroy(instance, network_info, \
              block_device_info)
        if FLAGS.connection_type == 'gpu':
            gpu_utils.deassign_gpus(instance)

    @exception.wrap_exception()
    def reboot(self, instance, network_info, reboot_type='SOFT'):
        t = super(GPULibvirtDriver, self).reboot(instance, network_info,
                  reboot_type)
        if FLAGS.connection_type == 'gpu':
            gpu_utils.assign_gpus(instance)
        return t

    @exception.wrap_exception()
    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=None, block_device_info=None):
        t = super(GPULibvirtDriver, self).spawn(context, instance,
                  image_meta, injected_files, admin_password,
                  network_info, block_device_info)
        try:
            if FLAGS.connection_type == 'gpu':
                gpu_utils.assign_gpus(context, instance,
                                  self.get_lxc_container_root(
                                  self._lookup_by_name(instance['name'])))
        except Exception as Exn:
            LOG.error(_("Error in GPU assignment, overcommitted."))
            self.destroy(instance, network_info, block_device_info)
            db.instance_update(context, instance['uuid'],
                    {'vm_state': vm_states.DELETED})
            raise Exception(_('Error in GPU assignment, overcommitted.'))
        LOG.info(_("Instance spawned successfully."),
                     instance=instance)
        return t

    @exception.wrap_exception()
    def detach_volume(self, connection_info, instance_name, mountpoint):
        mount_device = mountpoint.rpartition("/")[2]
        try:
            # NOTE(vish): This is called to cleanup volumes after live
            #             migration, so we should still logout even if
            #             the instance doesn't exist here anymore.
            virt_dom = self._lookup_by_name(instance_name)
            if FLAGS.libvirt_type == 'lxc':
                self._detach_lxc_volume(mount_device, virt_dom, instance_name)
            else:
                xml = self._get_disk_xml(virt_dom.XMLDesc(0), mount_device)
                if not xml:
                    raise exception.DiskNotFound(location=mount_device)
                virt_dom.detachDevice(xml)
        finally:
            self.volume_driver_method('disconnect_volume',
                                      connection_info,
                                      mount_device)

        # TODO(danms) once libvirt has support for LXC hotplug,
        # replace this re-define with use of the
        # VIR_DOMAIN_AFFECT_LIVE & VIR_DOMAIN_AFFECT_CONFIG flags with
        # detachDevice()
        domxml = virt_dom.XMLDesc(libvirt.VIR_DOMAIN_XML_SECURE)
        self._conn.defineXML(domxml)


    @exception.wrap_exception()
    def _umount_lxc_volume(self, init_pid, lxc_device):
        global lxc_mounts
        LOG.info(_('umounting LXC block device'))
        dev_key = init_pid + lxc_device
        if dev_key not in lxc_mounts:
            raise Exception(_('no such process(%(init_pid)s) or ' \
                  'mount point(%(lxc_container_device)s)') % locals())
        dir_name = lxc_mounts[dev_key]

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/umount', '%s' % dir_name, 
                      run_as_root=True)

        # remove the directory
        utils.execute('lxc-attach', '-n', '%s'  % init_pid, '--',
                      '/bin/rmdir', '%s' % dir_name, 
                      run_as_root=True)

        del lxc_mounts[dev_key]  # delete dictionary entry

    @exception.wrap_exception()
    def _detach_lxc_volume(self, lxc_device, virt_dom, instance_name):
        LOG.info(_('ISI: detaching LXC block device'))

        lxc_container_root = self.get_lxc_container_root(virt_dom)
        lxc_container_device = 'dev/' + lxc_device
        lxc_container_target = "%s/%s" % (lxc_container_root,
                                          lxc_container_device)

#        if lxc_container_target:
#            disk.unbind(lxc_container_target)

        # get id of the virt_dom
        spid = str(virt_dom.ID())
        LOG.info(_('detach_volume: pid(%s)') % spid)

        # get PID of the init process
        ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" \
                              % spid, shell=True, stdout=subprocess.PIPE)
        init_pid = ps_command.stdout.read()
        init_pid = str(int(init_pid))
        retcode = ps_command.wait()
        assert retcode == 0, "ps command returned %d" % retcode

        self._umount_lxc_volume(init_pid, lxc_container_device)

        LOG.info(_('detach_volume:'))
        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/rm', '/%s' % lxc_container_device, 
                      run_as_root=True)

    @exception.wrap_exception()
    def _mount_lxc_volume(self, init_pid, lxc_root, lxc_device):
        global lxc_mounts
        LOG.info(_('ISI: mount LXC block device'))

        # check if 'mountpoint' already exists
        dev_key = init_pid + lxc_device
        if dev_key in lxc_mounts:
            raise Exception(_('the same mount point(%s) is already used.')\
                        % lxc_device)

        utils.execute('lxc-attach', '-n', '%s' % init_pid,'--',
                      '/bin/mkdir', '-p', '/vmnt', 
                      run_as_root=True)

        # create a sub-directory for mount
        found = 0
        for n in range(0, 100):
            dir_name = '/vmnt/vol' + str(n)
            if not os.path.exists(lxc_root + dir_name):
                utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                              '/bin/mkdir', '%s' % dir_name, run_as_root=True)
                found = 1
                break
        if found == 0:
            utils.execute('lxc-attach', '-n', '%s' % init_pid % init_pid, '--',
                          '/bin/rm', '%s' % lxc_device, run_as_root=True)
            raise Exception(_('cannot find mounting directories'))

        lxc_mounts[dev_key] = dir_name
        utils.execute('lxc-attach', '-n', '%s'  % init_pid, '--',
                      '/bin/chmod', '777', '%s' % lxc_device,
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', '%s'  % init_pid, '--',
                      '/bin/mount', '/%s' % lxc_device,
                      '%s' % dir_name,
                      run_as_root=True)

        # change owner
        user = FLAGS.user
        user = user.rsplit("/")
        user = user[len(user) - 1]
        utils.execute('lxc-attach', '-n', '%s'  % init_pid, '--',
                      '/bin/chown', '%s'  % user, '/vmnt',
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/chown', '%s' % user, '%s' % dir_name,
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/chmod', 'og+w', '%s' % dir_name,
                      run_as_root=True)

    @exception.wrap_exception()
    def _attach_lxc_volume(self, xml, virt_dom, instance_name):
        LOG.info(_('ISI: attaching LXC block device'))

        lxc_container_root = self.get_lxc_container_root(virt_dom)
        lxc_host_volume = self.get_lxc_host_device(xml)
        lxc_container_device = self.get_lxc_container_target(xml)
        lxc_container_target = "%s/%s" % (lxc_container_root,
                                          lxc_container_device)
        LOG.debug(_('attach_volume: root(%s)') % lxc_container_root)
        LOG.debug(_('attach_volume: host_volume(%s)') % lxc_host_volume)
        LOG.debug(_('attach_volume: device(%s)') % lxc_container_device)

        # get id of the virt_dom
        spid = str(virt_dom.ID())
        LOG.info(_('attach_volume: pid(%s)') % spid)

        (ps_out, err) = utils.execute('ps', '--format', 'pid', 
                                      '--ppid', '%s' % spid, 
                                      '--noheaders',
                                    run_as_root=True)
        init_pid = str(int(ps_out))

        LOG.info(_('attach_volume: init_pid(%s)') % init_pid)
        # get major, minor number of the device
        s = os.stat(lxc_host_volume)
        major_num = os.major(s.st_rdev)
        minor_num = os.minor(s.st_rdev)
        LOG.info(_('attach_volume: path(%s)') % lxc_container_device)
        LOG.info(_('attach_volume: major_num(%(major_num)d) ' \
                   'minor_num(%(minor_num)d)') % locals())

        # allow the device
        dev_whitelist = os.path.join("/cgroup/devices/libvirt/lxc/",
                                     instance_name,
                                     'devices.allow')
        # Allow the disk
        perm = "b %d:%d rwm" % (major_num, minor_num)
        utils.execute('tee', dev_whitelist, process_input=perm,
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/mknod', '-m', '777', '/%s' % lxc_container_device,
                      'b', '%d' % major_num, '%d' % minor_num,
                      run_as_root=True)
 
        self._mount_lxc_volume(init_pid, lxc_container_root, lxc_container_device)


class GPUHostState(driver.HostState):
    """Manages information about the compute node through libvirt"""
    def __init__(self, read_only):
        super(GPUHostState, self).__init__(read_only=False)

    def update_status(self):
        if self.connection is None:
            self.connection = GPULibvirtDriver(self.read_only)
        data = super(GPUHostState, self).update_status()
        data = gpu_utils.update_status(data)
        return data

'''
_cleanup
_create_image
  both have extra code to manage LXC with Raw image.
  If LXC with qcow2 image works,
     we can use the original libvirt/driver.py code for them
'''

'''
   The following code is for reference only

   -------------------------------------------------------------

    def _cleanup(self, instance, network_info, block_device_info):
        try:
            virt_dom = self._lookup_by_name(instance['name'])
        except exception.NotFound:
            virt_dom = None
        if virt_dom:
            try:
                # NOTE(derekh): we can switch to undefineFlags and
                # VIR_DOMAIN_UNDEFINE_MANAGED_SAVE once we require 0.9.4
                if virt_dom.hasManagedSaveImage(0):
                    virt_dom.managedSaveRemove(0)
            except libvirt.libvirtError as e:
                errcode = e.get_error_code()
                LOG.error(_("Error from libvirt during saved instance "
                              "removal. Code=%(errcode)s Error=%(e)s") %
                            locals(), instance=instance)
            try:
                # NOTE(justinsb): We remove the domain definition.
                virt_dom.undefine()
            except libvirt.libvirtError as e:
                errcode = e.get_error_code()
                LOG.error(_("Error from libvirt during undefine. "
                              "Code=%(errcode)s Error=%(e)s") %
                            locals(), instance=instance)
                raise

        self.unplug_vifs(instance, network_info)
        try:
            self.firewall_driver.unfilter_instance(instance,
                                                   network_info=network_info)
        except libvirt.libvirtError as e:
            errcode = e.get_error_code()
            LOG.error(_("Error from libvirt during unfilter. "
                          "Code=%(errcode)s Error=%(e)s") %
                        locals(), instance=instance)
            reason = "Error unfiltering instance."
            raise exception.InstanceTerminationFailure(reason=reason)

        # NOTE(vish): we disconnect from volumes regardless
        block_device_mapping = driver.block_device_info_get_mapping(
            block_device_info)
        for vol in block_device_mapping:
            connection_info = vol['connection_info']
            mount_device = vol['mount_device'].rpartition("/")[2]
            self.volume_driver_method('disconnect_volume',
                                      connection_info,
                                      mount_device)

        target = os.path.join(FLAGS.instances_path, instance['name'])
        LOG.info(_('Deleting instance files %(target)s') % locals(),
                 instance=instance)
        if FLAGS.connection_type == 'gpu':
            self.deassign_gpus(instance)
            #disk.destroy_container(self.container)
        if FLAGS.libvirt_type == 'lxc':
            container_dir = os.path.join(FLAGS.instances_path,
                                         instance['name'],
                                         'rootfs')
            disk.destroy_container(container_dir=container_dir)
        if os.path.exists(target):
            # If we fail to get rid of the directory
            # tree, this shouldn't block deletion of
            # the instance as whole.
            try:
                shutil.rmtree(target)
            except OSError, e:
                LOG.error(_("Failed to cleanup directory %(target)s: %(e)s") %
                          locals())

        #NOTE(bfilippov): destroy all LVM disks for this instance
        self._cleanup_lvm(instance)



    def _create_image(self, context, instance, libvirt_xml, suffix='',
                      disk_images=None, network_info=None,
                      block_device_info=None):
        if not suffix:
            suffix = ''

        # Are we using a config drive?
        using_config_drive = False
        if (instance.get('config_drive') or
            FLAGS.force_config_drive):
            LOG.info(_('Using config drive'), instance=instance)
            using_config_drive = True

        # syntactic nicety
        def basepath(fname='', suffix=suffix):
            return os.path.join(FLAGS.instances_path,
                                instance['name'],
                                fname + suffix)

        def image(fname, image_type=FLAGS.libvirt_images_type):
            return self.image_backend.image(instance['name'],
                                            fname + suffix, image_type)

        def raw(fname):
            return image(fname, image_type='raw')

        # ensure directories exist and are writable
        libvirt_utils.ensure_tree(basepath(suffix=''))

        LOG.info(_('Creating image'), instance=instance)
        libvirt_utils.write_to_file(basepath('libvirt.xml'), libvirt_xml)

        if FLAGS.libvirt_type == 'lxc':
            container_dir = os.path.join(FLAGS.instances_path,
                                         instance['name'],
                                         'rootfs')
            libvirt_utils.ensure_tree(container_dir)

        # NOTE(dprince): for rescue console.log may already exist... chown it.
        self._chown_console_log_for_instance(instance['name'])

        # NOTE(vish): No need add the suffix to console.log
        libvirt_utils.write_to_file(basepath('console.log', ''), '', 007)

        if not disk_images:
            disk_images = {'image_id': instance['image_ref'],
                           'kernel_id': instance['kernel_id'],
                           'ramdisk_id': instance['ramdisk_id']}

        if disk_images['kernel_id']:
            fname = disk_images['kernel_id']
            raw('kernel').cache(fn=libvirt_utils.fetch_image,
                                context=context,
                                fname=fname,
                                image_id=disk_images['kernel_id'],
                                user_id=instance['user_id'],
                                project_id=instance['project_id'])
            if disk_images['ramdisk_id']:
                fname = disk_images['ramdisk_id']
                raw('ramdisk').cache(fn=libvirt_utils.fetch_image,
                                     context=context,
                                     fname=fname,
                                     image_id=disk_images['ramdisk_id'],
                                     user_id=instance['user_id'],
                                     project_id=instance['project_id'])

        root_fname = hashlib.sha1(str(disk_images['image_id'])).hexdigest()
        size = instance['root_gb'] * 1024 * 1024 * 1024

        inst_type_id = instance['instance_type_id']
        inst_type = instance_types.get_instance_type(inst_type_id)
        if size == 0 or suffix == '.rescue':
            size = None

        if not self._volume_in_mapping(self.default_root_device,
                                       block_device_info):
            image('disk').cache(fn=libvirt_utils.fetch_image,
                                context=context,
                                fname=root_fname,
                                size=size,
                                image_id=disk_images['image_id'],
                                user_id=instance['user_id'],
                                project_id=instance['project_id'])

        ephemeral_gb = instance['ephemeral_gb']
        if ephemeral_gb and not self._volume_in_mapping(
                self.default_second_device, block_device_info):
            swap_device = self.default_third_device
            fn = functools.partial(self._create_ephemeral,
                                   fs_label='ephemeral0',
                                   os_type=instance["os_type"])
            fname = "ephemeral_%s_%s_%s" % ("0",
                                            ephemeral_gb,
                                            instance["os_type"])
            size = ephemeral_gb * 1024 * 1024 * 1024
            image('disk.local').cache(fn=fn,
                                      fname=fname,
                                      size=size,
                                      ephemeral_size=ephemeral_gb)
        else:
            swap_device = self.default_second_device

        for eph in driver.block_device_info_get_ephemerals(block_device_info):
            fn = functools.partial(self._create_ephemeral,
                                   fs_label='ephemeral%d' % eph['num'],
                                   os_type=instance["os_type"])
            size = eph['size'] * 1024 * 1024 * 1024
            fname = "ephemeral_%s_%s_%s" % (eph['num'],
                                            eph['size'],
                                            instance["os_type"])
            image(_get_eph_disk(eph)).cache(fn=fn,
                                            fname=fname,
                                            size=size,
                                            ephemeral_size=eph['size'])

        swap_mb = 0

        swap = driver.block_device_info_get_swap(block_device_info)
        if driver.swap_is_usable(swap):
            swap_mb = swap['swap_size']
        elif (inst_type['swap'] > 0 and
              not self._volume_in_mapping(swap_device, block_device_info)):
            swap_mb = inst_type['swap']

        if swap_mb > 0:
            size = swap_mb * 1024 * 1024
            image('disk.swap').cache(fn=self._create_swap,
                                     fname="swap_%s" % swap_mb,
                                     size=size,
                                     swap_mb=swap_mb)

        # target partition for file injection
        target_partition = None
        if not instance['kernel_id']:
            target_partition = FLAGS.libvirt_inject_partition
            if target_partition == 0:
                target_partition = None
        if FLAGS.libvirt_type == 'lxc':
            target_partition = None

        if FLAGS.libvirt_inject_key and instance['key_data']:
            key = str(instance['key_data'])
        else:
            key = None
        net = None

        nets = []
        ifc_template = open(FLAGS.injected_network_template).read()
        ifc_num = -1
        have_injected_networks = False
        for (network_ref, mapping) in network_info:
            ifc_num += 1

            if not network_ref['injected']:
                continue

            have_injected_networks = True
            address = mapping['ips'][0]['ip']
            netmask = mapping['ips'][0]['netmask']
            address_v6 = None
            gateway_v6 = None
            netmask_v6 = None
            if FLAGS.use_ipv6:
                address_v6 = mapping['ip6s'][0]['ip']
                netmask_v6 = mapping['ip6s'][0]['netmask']
                gateway_v6 = mapping['gateway_v6']
            net_info = {'name': 'eth%d' % ifc_num,
                   'address': address,
                   'netmask': netmask,
                   'gateway': mapping['gateway'],
                   'broadcast': mapping['broadcast'],
                   'dns': ' '.join(mapping['dns']),
                   'address_v6': address_v6,
                   'gateway_v6': gateway_v6,
                   'netmask_v6': netmask_v6}
            nets.append(net_info)

        if have_injected_networks:
            net = str(Template(ifc_template,
                               searchList=[{'interfaces': nets,
                                            'use_ipv6': FLAGS.use_ipv6}]))

        # Config drive
        cdb = None
        if using_config_drive:
            cdb = configdrive.ConfigDriveBuilder(instance=instance)

        # File injection
        metadata = instance.get('metadata')

        if FLAGS.libvirt_inject_password:
            admin_pass = instance.get('admin_pass')
        else:
            admin_pass = None

        files = instance.get('injected_files')

        if any((key, net, metadata, admin_pass, files)):
            if not using_config_drive:
                # If we're not using config_drive, inject into root fs
                injection_path = image('disk').path
                img_id = instance['image_ref']

                for injection in ('metadata', 'key', 'net', 'admin_pass',
                                  'files'):
                    if locals()[injection]:
                        LOG.info(_('Injecting %(injection)s into image'
                                   ' %(img_id)s'), locals(), instance=instance)
                try:
                    disk.inject_data(injection_path,
                                     key, net, metadata, admin_pass, files,
                                     partition=target_partition,
                                     use_cow=FLAGS.use_cow_images)

                except Exception as e:
                    # This could be a windows image, or a vmdk format disk
                    LOG.warn(_('Ignoring error injecting data into image '
                               '%(img_id)s (%(e)s)') % locals(),
                             instance=instance)

            else:
                # We're using config_drive, so put the files there instead
                cdb.inject_data(key, net, metadata, admin_pass, files)

        if using_config_drive:
            # NOTE(mikal): Render the config drive. We can't add instance
            # metadata here until after file injection, as the file injection
            # creates state the openstack metadata relies on.
            cdb.add_instance_metadata()

            try:
                configdrive_path = basepath(fname='disk.config')
                LOG.info(_('Creating config drive at %(path)s'),
                         {'path': configdrive_path}, instance=instance)
                cdb.make_drive(configdrive_path)
            finally:
                cdb.cleanup()

        if FLAGS.libvirt_type == 'lxc':
            disk.setup_container(basepath('disk'),
                                 container_dir=container_dir,
                                 use_cow=FLAGS.use_cow_images)

        if FLAGS.libvirt_type == 'uml':
            libvirt_utils.chown(basepath('disk'), 'root')

'''
'''
    def _attach_lxc_volume(self, xml, virt_dom, instance_name):
        LOG.info(_('ISI: attaching LXC block device'))

        lxc_container_root = self.get_lxc_container_root(virt_dom)
        lxc_host_volume = self.get_lxc_host_device(xml)
        lxc_container_device = self.get_lxc_container_target(xml)
        lxc_container_target = "%s/%s" % (lxc_container_root,
                                          lxc_container_device)

        # get id of the virt_dom
        spid = str(virt_dom.ID())

        # get PID of the init process
        #ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" % \
        #                   spid, shell=True, stdout=subprocess.PIPE)
        #init_pid = ps_command.stdout.read()
        #init_pid = str(int(init_pid))
        #retcode = ps_command.wait()
        #assert retcode == 0, "ps command returned %d" % retcode

        #dkang: is this needed? it looks like that 'spid' is init_pid.
        init_pid, err = utils.execute('ps', '-o pid --ppid %s --noheaders' % spid,\
                                 run_as_root=True)
        init_pid = str(int(init_pid))

        # get major, minor number of the device
        s = os.stat(lxc_host_volume)
        major_num = os.major(s.st_rdev)
        minor_num = os.minor(s.st_rdev)

        # allow the device
        dev_whitelist = os.path.join("/cgroup/devices/libvirt/lxc/",
                                     instance_name,
                                     'devices.allow')
        # Allow the disk
        #perm = "b %d:%d rwm" % (major_num, minor_num)
        #cmd = "echo %s | sudo tee -a %s" % (perm, dev_whitelist)
        #subprocess.Popen(cmd, shell=True)
        utils.execute('tee', '-a %s' & dev_whitelist,
                      process_input=perm, run_as_root=True)

        #cmd_lxc = 'sudo lxc-attach -n %s -- ' % init_pid
      
        # check if 'mountpoint' already exists

        #cmd = '/bin/mknod -m 777 /%s b %d %d '\
        #     % (lxc_container_device, major_num, minor_num)
        #cmd = cmd_lxc + cmd
        #subprocess.call(cmd, shell=True)
        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/mknod', '-m', '777', '/%s' % lxc_container_device,
                      'b', '%d' % major_num, '%d' % minor_num,
                      run_as_root=True)
                      

    @exception.wrap_exception()
    def _detach_lxc_volume(self, xml, virt_dom, instance_name):
        LOG.info(_('ISI: detaching LXC block device'))

        lxc_container_root = self.get_lxc_container_root(virt_dom)
        lxc_container_device = self.get_lxc_container_target(xml)
        lxc_container_target = "%s/%s" % (lxc_container_root,
                                          lxc_container_device)

        if lxc_container_target:
            disk.unbind(lxc_container_target)

        # get id of the virt_dom
        spid = str(virt_dom.ID())
        LOG.info(_('detach_volume: pid(%s)') % spid)

        # get PID of the init process
        ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" \
                              % spid, shell=True, stdout=subprocess.PIPE)
        init_pid = ps_command.stdout.read()
        init_pid = str(int(init_pid))
        retcode = ps_command.wait()
        assert retcode == 0, "ps command returned %d" % retcode

        cmd = cmd_lxc + ' /bin/rm ' + '/' + lxc_container_device
        LOG.info(_('detach_volume: cmd(%s)') % cmd)
        subprocess.call(cmd, shell=True)
'''
