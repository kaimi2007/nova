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
from nova import context as nova_context
from nova import db
from nova import exception
from nova import flags
from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from nova import utils
from nova.virt.disk import api as disk
from nova.virt.gpu import utils as gpu_utils
from nova.virt.libvirt import driver

import subprocess

libvirt = None

LOG = logging.getLogger(__name__)

FLAGS = flags.FLAGS

lxc_mounts = {}


class GPULibvirtDriver(driver.LibvirtDriver):
    def __init__(self, read_only=False):
        super(GPULibvirtDriver, self).__init__()

        global libvirt
        if libvirt is None:
            libvirt = __import__('libvirt')

        gpu_utils.init_host_gpu()
        if gpu_utils.get_gpu_total() >= 1:
            assert FLAGS.libvirt_type == 'lxc', "Only LXC is supported for GPU"

    @property
    def host_state(self):
        if not self._host_state:
            self._host_state = \
                GPUHostState(self.read_only)
        return self._host_state

    def destroy(self, instance, network_info, block_device_info=None):
        super(GPULibvirtDriver, self).destroy(instance, network_info,
              block_device_info)
        gpu_utils.deassign_gpus(instance)

    @exception.wrap_exception()
    def reboot(self, instance, network_info, reboot_type='SOFT',
               block_device_info=None):
        gpu_utils.deassign_gpus(instance)
        t = super(GPULibvirtDriver, self).reboot(instance, network_info,
                  reboot_type, block_device_info)
        ctxt = nova_context.get_admin_context()
        gpu_utils.assign_gpus(ctxt, instance,
                              self.get_lxc_container_root(
                              self._lookup_by_name(instance['name'])))
        return t

    @exception.wrap_exception()
    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=None, block_device_info=None):
        t = super(GPULibvirtDriver, self).spawn(context, instance,
                  image_meta, injected_files, admin_password,
                  network_info, block_device_info)
        try:
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
            raise Exception(_('no such process(%(init_pid)s) or '
                  'mount point(%(lxc_container_device)s)') % locals())
        dir_name = lxc_mounts[dev_key]

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/umount', '%s' % dir_name,
                      run_as_root=True)

        # remove the directory
        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
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
        ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders"
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
            raise Exception(_('the same mount point(%s) is already used.')
                        % lxc_device)

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
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
        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/chmod', '777', '%s' % lxc_device,
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/mount', '/%s' % lxc_device,
                      '%s' % dir_name,
                      run_as_root=True)

        # change owner
        user = FLAGS.user
        user = user.rsplit("/")
        user = user[len(user) - 1]
        utils.execute('lxc-attach', '-n', '%s' % init_pid, '--',
                      '/bin/chown', '%s' % user, '/vmnt',
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
        LOG.info(_('attach_volume: major_num(%(major_num)d) '
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

        self._mount_lxc_volume(init_pid, lxc_container_root,
                               lxc_container_device)


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
