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

from lxml import etree
from oslo.config import cfg

from nova.compute import power_state
from nova import context as nova_context
from nova import exception
from nova.openstack.common import excutils
from nova.openstack.common import log as logging
from nova import utils
from nova.virt.gpu import utils as gpu_utils
from nova.virt.libvirt import blockinfo
from nova.virt.libvirt import driver
from nova.virt.libvirt import utils as libvirt_utils

libvirt = None

LOG = logging.getLogger(__name__)

CONF = cfg.CONF



class GPULibvirtDriver(driver.LibvirtDriver):
    def __init__(self, virtapi, read_only=False):
        super(GPULibvirtDriver, self).__init__(virtapi)

        global libvirt
        if libvirt is None:
            libvirt = __import__('libvirt')

        gpu_utils.get_instance_type_extra_specs_capabilities()
        if CONF.libvirt_type.lower() == 'lxc':
            gpu_utils.init_host_gpu(self.list_live_instance_uuids())

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
            self._host_state = GPUHostState(self)
        return self._host_state

    def destroy(self, instance, network_info, block_device_info=None):
        super(GPULibvirtDriver, self).destroy(instance, network_info,
              block_device_info)
        if CONF.libvirt_type.lower() != 'lxc':
            return
        gpu_utils.deallocate_gpus(instance)

    @exception.wrap_exception()
    def reboot(self, instance, network_info, reboot_type='SOFT',
               block_device_info=None):
        if CONF.libvirt_type.lower() != 'lxc':
            return super(GPULibvirtDriver, self).reboot(instance, 
                         network_info, reboot_type, block_device_info)
        gpu_utils.deallocate_gpus(instance)
        t = super(GPULibvirtDriver, self).reboot(instance, network_info,
                  reboot_type, block_device_info)
        ctxt = nova_context.get_admin_context()
        inst_path = libvirt_utils.get_instance_path(instance)
        container_dir = os.path.join(inst_path, 'rootfs')
        inst_type = self.virtapi.instance_type_get(
            nova_context.get_admin_context(read_deleted='yes'),
            instance['instance_type_id'])
        extra_specs = inst_type['extra_specs']
        virt_dom = self._lookup_by_name(instance['name'])
        gpu_utils.allocate_gpus(ctxt, instance, extra_specs, virt_dom) 
        return t

    @exception.wrap_exception()
    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=None, block_device_info=None):
        super(GPULibvirtDriver, self).spawn(context, instance,
                  image_meta, injected_files, admin_password,
                  network_info, block_device_info)
        if CONF.libvirt_type.lower() != 'lxc':
            return 
        try:
            virt_dom = self._lookup_by_name(instance['name'])
            inst_type = self.virtapi.instance_type_get(
                nova_context.get_admin_context(read_deleted='yes'),
                instance['instance_type_id'])
            extra_specs = inst_type['extra_specs']
            gpu_utils.allocate_gpus(context, instance, extra_specs, 
                                    virt_dom)
            gpu_utils.restart_sshd(virt_dom)

        except Exception as Exn:
            LOG.error(_("Error in GPU allocation, overcommitted."))
            self.destroy(instance, network_info, block_device_info)
            #db.instance_update(context, instance['uuid'],
            #        {'vm_state': vm_states.DELETED})
            raise Exception(_('Error in GPU allocation, overcommitted.'))
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

    def attach_volume(self, connection_info, instance, mountpoint):
        if CONF.libvirt_type.lower() != 'lxc':
            super(GPULibvirtDriver, self).attach_volume(
                     connection_info, instance, mountpoint)
            return
        instance_name = instance['name']
        virt_dom = self._lookup_by_name(instance_name)
        disk_dev = mountpoint.rpartition("/")[2]
        disk_info = {
            'dev': disk_dev,
            'bus': blockinfo.get_disk_bus_for_disk_dev(CONF.libvirt_type,
                                                       disk_dev),
            'type': 'disk',
            }
        conf = self.volume_driver_method('connect_volume',
                                         connection_info,
                                         disk_info)
        self.set_cache_mode(conf)

        source_dev = self.get_guest_disk_path(conf.to_xml())
        try:
            # NOTE(vish): We can always affect config because our
            #             domains are persistent, but we should only
            #             affect live if the domain is running.
            flags = libvirt.VIR_DOMAIN_AFFECT_CONFIG
            state = driver.LIBVIRT_POWER_STATE[virt_dom.info()[0]]
            if state == power_state.RUNNING:
                flags |= libvirt.VIR_DOMAIN_AFFECT_LIVE
            if CONF.libvirt_type.lower() == 'lxc':
                gpu_utils._attach_lxc_volume(source_dev, 
                                   '/dev/%s' % disk_info['dev'],
                                   virt_dom, instance)
            else:
                virt_dom.attachDeviceFlags(conf.to_xml(), flags)
        except Exception, ex:
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


    def detach_volume(self, connection_info, instance, mountpoint):
        if CONF.libvirt_type.lower() != 'lxc':
            super(GPULibvirtDriver, self).detach_volume(
                    connection_info, instance, mountpoint)
            return
        instance_name = instance['name']
        disk_dev = mountpoint.rpartition("/")[2]
        try:
            virt_dom = self._lookup_by_name(instance_name)
            if CONF.libvirt_type.lower() == 'lxc':
                gpu_utils._detach_lxc_volume(disk_dev, virt_dom, 
                                        instance_name)
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

class GPUHostState(driver.HostState):
    """Manages information about the compute node through libvirt"""
    def __init__(self, driver):
        super(GPUHostState, self).__init__(driver)

    def update_status(self):
        data = super(GPUHostState, self).update_status()
        data = gpu_utils.update_status(data)
        return data
