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
Heterogeneous Architecture support under a connection to a hypervisor through libvirt.

"""

import os
import pickle

from lxml import etree
from oslo.config import cfg

from nova.compute import power_state
from nova import context as nova_context
from nova import exception
from nova import utils
from nova.objects import flavor as flavor_obj
from nova.openstack.common import excutils
from nova.openstack.common.gettextutils import _
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
#from nova.compute import utils as compute_utils
from nova.virt.hetero import gpu_utils as gpu_utils
from nova.virt.libvirt import blockinfo
from nova.virt.libvirt import driver
from nova.virt.libvirt import utils as libvirt_utils

libvirt = None
volume_devices = {}
volume_device_file = ''

LOG = logging.getLogger(__name__)


lxc_volume_opts = [
    cfg.StrOpt('volume_device_file',
               default='volume_devices',
               help='Full path of the file keeping the information of gpus allocated'),
    cfg.StrOpt('use_lxc_attach',
               default=True,
               help='whether lxc-attach is available or not'),
    cfg.ListOpt('instance_type_extra_specs',
               default=[],
               help='a list of additional capabilities corresponding to '
               'instance_type_extra_specs for this compute '
               'host to advertise. Valid entries are name=value, pairs '
               'For example, "key1:val1, key2:val2"'),
]

CONF = cfg.CONF
CONF.register_opts(lxc_volume_opts)


def load_volume_devices():
    global volume_device_file
    try:
        input = open(volume_device_file, 'r')
        data = pickle.load(input)
        input.close()
        return data
    except Exception:
        LOG.error(_("Failed to open Volume Device information"))
        return {}

def save_volume_devices(volume_devices):
    global volume_device_file
    try:
        output = open(volume_device_file, 'w')
        pickle.dump(volume_devices, output, pickle.HIGHEST_PROTOCOL)
        output.close()
    except Exception:
        LOG.error(_("Failed to save Volume Device information"))
        pass


class HeteroLibvirtDriver(driver.LibvirtDriver):
    def __init__(self, virtapi, read_only=False):
        super(HeteroLibvirtDriver, self).__init__(virtapi)

        global libvirt
        if libvirt is None:
            libvirt = __import__('libvirt')

        self._host_state = None

        gpu_utils.get_instance_type_extra_specs_capabilities()
        if CONF.libvirt.virt_type.lower() == 'lxc':
            global volume_devices
            global volume_device_file

            volume_device_file = CONF.state_path + '/' + CONF.volume_device_file
#            LOG.info(_("init: volume_device_file - %s" \
#                          % volume_device_file))
            gpu_utils.init_host_gpu(self.list_live_instance_uuids())
            volume_devices = load_volume_devices()
#            LOG.info(_("init: volume_devices %s" \
#                          % str(volume_devices)))

    def list_live_instance_uuids(self):
        uuids = []
        for name in self.list_instances():
            try:
                virt_dom = self._lookup_by_name(name)
                (state, _max_mem, _mem, _cpus, _t) = virt_dom.info()
                state = driver.LIBVIRT_POWER_STATE[state]
                if state == power_state.RUNNING:
                    uuids.append(virt_dom.UUIDString())
            except Exception:
                pass
        return uuids

    @property
    def host_state(self):
        if not self._host_state:
            self._host_state = HeteroHostState(self)
#        LOG.info(_("host_state = %s" % str(self._host_state)))
        return self._host_state

    def destroy(self, context, instance, network_info, block_device_info=None,
                destroy_disks=True):
        if CONF.libvirt.virt_type.lower() == 'lxc':
            gpu_utils.deallocate_gpus(instance)
        super(HeteroLibvirtDriver, self).destroy(context, instance, network_info,
              block_device_info, destroy_disks)
        if CONF.libvirt.virt_type.lower() != 'lxc':
            return
        #gpu_utils.deallocate_gpus(instance)

    @exception.wrap_exception()
    def reboot(self, context, instance, network_info, reboot_type='SOFT',
               block_device_info=None, bad_volumes_callback=None):
#        LOG.info(_("Instance is soft rebooting."))
        if CONF.libvirt.virt_type.lower() != 'lxc':
            return super(HeteroLibvirtDriver, self).reboot(context, instance, 
                         network_info, reboot_type, block_device_info,
                         bad_volumes_callback)
#        gpu_utils.deallocate_gpus(instance)
        t = super(HeteroLibvirtDriver, self).reboot(instance, network_info,
                  reboot_type, block_device_info, bad_volumes_callback)
#        ctxt = nova_context.get_admin_context()
#        inst_path = libvirt_utils.get_instance_path(instance)
#        container_dir = os.path.join(inst_path, 'rootfs')
#        inst_type = self.virtapi.instance_type_get(
#            nova_context.get_admin_context(read_deleted='yes'),
#            instance['instance_type_id'])
#        extra_specs = inst_type['extra_specs']
#        virt_dom = self._lookup_by_name(instance['name'])
#        cuda_flag = gpu_utils.allocate_gpus(ctxt, instance, extra_specs, virt_dom) 
        gpu_utils.allow_gpus(instance)
        return t

    @exception.wrap_exception()
    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=None, block_device_info=None):

        if CONF.libvirt.virt_type.lower() == 'lxc':
#            virt_dom = self._lookup_by_name(instance['name'])
            #inst_type = self.virtapi.instance_type_get(
            inst_type = flavor_obj.Flavor.get_by_id(
                nova_context.get_admin_context(read_deleted='yes'),
                    instance['instance_type_id'])
            extra_specs = inst_type['extra_specs']
            cuda_flag = gpu_utils.allocate_gpus(context, instance,
                                 extra_specs)
            # write to a temporary file locally first
            injected_files.append(("/etc/environment", cuda_flag))
#            LOG.info(_("injected_files = %s." % str(injected_files)))
  
        try:
            super(HeteroLibvirtDriver, self).spawn(context, instance,
                  image_meta, injected_files, admin_password,
                  network_info, block_device_info)
        except Exception:
            if CONF.libvirt.virt_type.lower() == 'lxc':
                gpu_utils.deallocate_gpus(instance)
            return

        if CONF.libvirt.virt_type.lower() == 'lxc':
            gpu_utils.allow_gpus(instance)

        LOG.info(_("Instance spawned successfully."),
                     instance=instance)

    def get_guest_disk_path(self, xml):
        if xml is None:
            raise 
        doc = etree.fromstring(xml)
        source = doc.findall('source')
        for node in source:
            disk_path = node.get('dev')
        return disk_path

    def attach_volume(self, context, connection_info, instance, mountpoint,
                      encryption=None):
        if CONF.libvirt.virt_type.lower() != 'lxc':
            super(HeteroLibvirtDriver, self).attach_volume(
                     context, connection_info, instance, mountpoint,
                     encryption)
            return
        instance_name = instance['name']
        virt_dom = self._lookup_by_name(instance_name)
        disk_dev = mountpoint.rpartition("/")[2]
        disk_info = {
            'dev': disk_dev,
            'bus': blockinfo.get_disk_bus_for_disk_dev(CONF.libvirt.virt_type,
                                                       disk_dev),
            'type': 'disk',
            }
        conf = self.volume_driver_method('connect_volume',
                                         connection_info,
                                         disk_info)
        self.set_cache_mode(conf)

        source_dev = self.get_guest_disk_path(conf.to_xml())

        # dkang: LXC: check if the device is already being used
        global volume_devices

#        LOG.info(_("attach: volume_devices = %s" % str(volume_devices)))
        uuid = virt_dom.UUIDString()
        if uuid in volume_devices:
            LOG.info(_("This instance(%s) already has volume." % uuid))
            device_list = volume_devices[uuid]
#            LOG.info(_("device_list = %s" % str(device_list)))
            for device in device_list:
                if disk_info['dev'] == device:
                    raise exception.DeviceIsBusy(device=disk_dev)
#            LOG.info(_("this instance does not use the volume device."))
        try:
            # NOTE(vish): We can always affect config because our
            #             domains are persistent, but we should only
            #             affect live if the domain is running.
            flags = libvirt.VIR_DOMAIN_AFFECT_CONFIG
            state = driver.LIBVIRT_POWER_STATE[virt_dom.info()[0]]
            if state == power_state.RUNNING:
                flags |= libvirt.VIR_DOMAIN_AFFECT_LIVE
            if CONF.libvirt.virt_type.lower() == 'lxc':
                gpu_utils._attach_lxc_volume(source_dev, 
                                   '/dev/%s' % disk_info['dev'],
                                   virt_dom, instance)
                # dkang: LXC: manage device list per instance
#                LOG.info(_("about to attach the volume at %s." \
#                          % disk_info['dev']))
                if uuid in volume_devices:
                    device_list = volume_devices[uuid]
                else:
                    device_list = []
                device_list.append(disk_info['dev'])
                volume_devices[uuid] = device_list
#                LOG.info(_("after attach: volume_devices %s" \
#                          % str(volume_devices)))
                save_volume_devices(volume_devices)
            else:
                virt_dom.attachDeviceFlags(conf.to_xml(), flags)
        except Exception, ex:
            if CONF.libvirt.virt_type.lower() == 'lxc':
                LOG.error(_("Error in Volume attachment."))
                LOG.error(_("Only one volume can be attached."))
                return
            if isinstance(ex, libvirt.libvirtError):
                errcode = ex.get_error_code()
                if errcode == libvirt.VIR_ERR_OPERATION_FAILED:
                    self.volume_driver_method('disconnect_volume',
                                              connection_info,
                                              disk_dev)
                    raise exception.DeviceIsBusy(device=disk_dev)

            with excutils.save_and_reraise_exception():
                self.volume_driver_method('disconnect_volume',
                                          connection_info,
                                          disk_dev)


    def detach_volume(self, connection_info, instance, mountpoint,
                      encryption=None):
        if CONF.libvirt.virt_type.lower() != 'lxc':
            super(HeteroLibvirtDriver, self).detach_volume(
                    connection_info, instance, mountpoint, encryption)
            return
        instance_name = instance['name']
        disk_dev = mountpoint.rpartition("/")[2]
        try:
            virt_dom = self._lookup_by_name(instance_name)
            if CONF.libvirt.virt_type.lower() == 'lxc':
                gpu_utils._detach_lxc_volume(disk_dev, virt_dom, 
                                        instance_name)
                # dkang: LXC: manage device list per instance
                global volume_devices

                uuid = virt_dom.UUIDString()
                if uuid in volume_devices:
                    device_list = volume_devices[uuid]
                    device_list.remove(disk_dev)
                    if device_list == []:
                        del volume_devices[uuid]
                    else:
                        volume_devices[uuid] = device_list
                    save_volume_devices(volume_devices)
                    LOG.info(_("detach: volume_devices %s" \
                          % str(volume_devices)))
                else:
                    LOG.info(_("Unknown volume device is asked to be detached"))
            else:
                xml = self._get_disk_xml(virt_dom.XMLDesc(0), disk_dev)
                if not xml:
                    raise exception.DiskNotFound(location=disk_dev)
                else:
                    # NOTE(vish): We can always affect config because our
                    #             domains are persistent, but we should only
                    #             affect live if the domain is running.
                    flags = libvirt.VIR_DOMAIN_AFFECT_CONFIG
                    state = driver.LIBVIRT_POWER_STATE[virt_dom.info()[0]]
                    if state == power_state.RUNNING:
                        flags |= libvirt.VIR_DOMAIN_AFFECT_LIVE
                    virt_dom.detachDeviceFlags(xml, flags)
        except libvirt.libvirtError as ex:
            # NOTE(vish): This is called to cleanup volumes after live
            #             migration, so we should still disconnect even if
            #             the instance doesn't exist here anymore.
            error_code = ex.get_error_code()
            if error_code == libvirt.VIR_ERR_NO_DOMAIN:
                # NOTE(vish):
                LOG.warn(_("During detach_volume, instance disappeared."))
            else:
                raise

        self.volume_driver_method('disconnect_volume',
                                  connection_info,
                                  disk_dev)

    def get_host_stats(self, refresh=False):
        """Return the current state of the host.

        If 'refresh' is True, run update the stats first.
        """
        return self.host_state.get_host_stats(refresh=refresh)

    def get_available_resource(self, nodename):
        """Retrieve resource information.

        This method is called when nova-compute launches, and
        as part of a periodic task that records the results in the DB.

        :param nodename: will be put in PCI device
        :returns: dictionary containing resource info
        """

        # Temporary: convert supported_instances into a string, while keeping
        # the RPC version as JSON. Can be changed when RPC broadcast is removed
        stats = self.host_state.get_host_stats(refresh=True)
        stats['supported_instances'] = jsonutils.dumps(
                stats['supported_instances'])
        return stats

'''
lxc_mounts = {}

    @exception.wrap_exception()
    def _mount_lxc_volume(self, init_pid, lxc_device, host_dev):
        global lxc_mounts
        LOG.info(_('ISI: mount LXC block device'))

        # check if 'mountpoint' already exists
        dev_key = init_pid + lxc_device
        if dev_key in lxc_mounts:
            raise Exception(_('the same mount point(%s) is already used.')
                        % lxc_device)
        # create a directory for mount
        dir_name = '/vmnt'
        utils.execute('lxc-attach', '-n', init_pid, '--',
                '/bin/mkdir', '-p', dir_name, run_as_root=True)
        # create a sub-directory for mount
        found = 0
        for n in range(0, 100):
            dir_name = CONF.volume_mount_dir + '/vol' + str(n)
            out, err = utils.execute('lxc-attach', '-n', init_pid, '--',
                          '/bin/ls', dir_name, run_as_root=True, 
                          check_exit_code=False) 
            if err:
                utils.execute('lxc-attach', '-n', init_pid, '--',
                              '/bin/mkdir', dir_name, run_as_root=True)
                found = 1
                break
        if found == 0:
            utils.execute('lxc-attach', '-n', init_pid, '--',
                          '/bin/rm', lxc_device, run_as_root=True)
            raise Exception(_('cannot find mounting directories'))

        lxc_mounts[dev_key] = dir_name
        utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/chmod', '777', lxc_device,
                      run_as_root=True)

        try:
            out, err = utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/mount', lxc_device, dir_name,
                      run_as_root=True, check_exit_code=[0])

        except Exception as exc:
        # mount returns 32 for "No records found"
            if exc.exit_code in [32]:
                if "mount: you must specify the filesystem type" in err:
                    LOG.info("New volume. A Ext3 file system is created in it.");
#                    utils.execute('mkfs.ext3', host_dev)

                out, err = utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/mount', lxc_device, dir_name,
                      run_as_root=True, check_exit_code=[0]) 
            else:
                raise Exception(_('cannot mount volume in the guest'))

        # change owner
        user = CONF.user
        user = user.rsplit("/")
        user = user[len(user) - 1]
        utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/chown', user, '/vmnt',
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/chown', user, dir_name,
                      run_as_root=True)

        utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/chmod', 'og+w', dir_name,
                      run_as_root=True)

    @exception.wrap_exception()
    def _umount_lxc_volume(self, init_pid, lxc_device):
        global lxc_mounts
        LOG.info(_('umounting LXC block device'))
        dev_key = init_pid + lxc_device
        if dev_key not in lxc_mounts:
            raise Exception(_('no such process(%(init_pid)s) or '
                  'mount point(%(lxc_device)s)') % locals())
        dir_name = lxc_mounts[dev_key]

        utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/umount', '%s' % dir_name,
                      run_as_root=True)

        # remove the directory
        utils.execute('lxc-attach', '-n', init_pid, '--',
                      '/bin/rmdir', '%s' % dir_name,
                      run_as_root=True)

        del lxc_mounts[dev_key]  # delete dictionary entry
'''

class HeteroHostState(driver.HostState):
    """Manages information about the compute node through libvirt"""
    def __init__(self, driver):
        super(HeteroHostState, self).__init__(driver)
        self._stats = {}
        self.update_status()

    def get_host_stats(self, refresh=False):
        """Return the current state of the host.

        If 'refresh' is True, run update the stats first.
        """
        if refresh or not self._stats:
            self.update_status()
        return self._stats

    def update_status(self):
        data = super(HeteroHostState, self).update_status()
        data = gpu_utils.update_status(data)

        extra_specs = {}
        for pair in CONF.instance_type_extra_specs:
            keyval = pair.split(':', 1)
            keyval[0] = keyval[0].strip()
            keyval[1] = keyval[1].strip()
            extra_specs[keyval[0]] = keyval[1]
        data['extra_specs'] = jsonutils.dumps(extra_specs)

        self._stats = data
        return data
