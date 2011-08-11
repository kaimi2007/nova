# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# Copyright (c) 2010 Citrix Systems, Inc.
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

"""
A connection to a hypervisor through baremetal.

Supports KVM, LXC, QEMU, UML, and XEN.

**Related Flags**

:baremetal_type:  Libvirt domain type.  Can be kvm, qemu, uml, xen
                (default: kvm).
:baremetal_uri:  Override for the default baremetal URI (baremetal_type).
:baremetal_xml_template:  Libvirt XML Template.
:rescue_image_id:  Rescue ami image (default: ami-rescue).
:rescue_kernel_id:  Rescue aki image (default: aki-rescue).
:rescue_ramdisk_id:  Rescue ari image (default: ari-rescue).
:injected_network_template:  Template file for injected network
:allow_project_net_traffic:  Whether to allow in project network traffic

"""

import multiprocessing
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from xml.dom import minidom
from xml.etree import ElementTree

from eventlet import greenthread
from eventlet import tpool

from nova import context as nova_context
from nova import db
from nova import exception
from nova import flags
from nova import ipv6
from nova import log as logging
from nova import utils
from nova import vnc
from nova.auth import manager
from nova.compute import instance_types
from nova.compute import power_state
from nova.virt import disk
from nova.virt import driver
from nova.virt import images
from nova.virt.libvirt import netutils
from nova.virt.baremetal import nodes
from nova.virt.baremetal import dom


Template = None

LOG = logging.getLogger('nova.virt.baremetal.proxy')

FLAGS = flags.FLAGS
flags.DEFINE_string('baremetal_injected_network_template',
                    utils.abspath('virt/baremetal_interfaces.template'),
                    'Template file for injected network')
flags.DEFINE_string('baremetal_xml_template',
                    utils.abspath('virt/baremetal.xml.template'),
                    'baremetal XML Template')
flags.DEFINE_string('baremetal_type',
                    'baremetal',
                    'baremetal domain type')
flags.DEFINE_string('baremetal_uri',
                    '',
                    'Override the default baremetal URI')
flags.DEFINE_bool('baremetal_allow_project_net_traffic',
                  True,
                  'Whether to allow in project network traffic')


def get_connection(read_only):
    # These are loaded late so that there's no need to install these
    # libraries when not using baremetal.
    # Cheetah is separate because the unit tests want to load Cheetah,
    # but not baremetal.
    _late_load_cheetah()
    return ProxyConnection(read_only)


def _late_load_cheetah():
    global Template
    if Template is None:
        t = __import__('Cheetah.Template', globals(), locals(),
                       ['Template'], -1)
        Template = t.Template


class ProxyConnection(driver.ComputeDriver):

    def __init__(self, read_only):
        super(ProxyConnection, self).__init__()
        self.baremetal_nodes = nodes.get_baremetal_nodes()
        self.baremetal_xml = open(FLAGS.baremetal_xml_template).read()
        self._wrapped_conn = None
        self.read_only = read_only

        self._host_state = None

    @property
    def HostState(self):
        if not self._host_state:
            self._host_state = HostState(self.read_only)
        return self._host_state

    def init_host(self, host):
        # NOTE(nsokolov): moved instance restarting to ComputeManager
        pass

    def _get_connection(self):
        self._wrapped_conn = dom.BareMetalDom()
        return self._wrapped_conn
    _conn = property(_get_connection)

    def get_pty_for_instance(self, instance_name):
        virt_dom = self._conn.lookupByName(instance_name)
        xml = virt_dom.XMLDesc(0)
        dom = minidom.parseString(xml)
        for serial in dom.getElementsByTagName('serial'):
            if serial.getAttribute('type') == 'pty':
                source = serial.getElementsByTagName('source')[0]
                return source.getAttribute('path')

    def list_instances(self):
        #return [self._conn.lookupByID(x).name()
        #        for x in self._conn.listDomainsID()]
        return self._conn.list_domains()

    def _map_to_instance_info(self, domain_name):
        """Gets info from a virsh domain object into an InstanceInfo"""

        # domain.info() returns a list of:
        #    state:       one of the state values (virDomainState)
        #    maxMemory:   the maximum memory used by the domain
        #    memory:      the current amount of memory used by the domain
        #    nbVirtCPU:   the number of virtual CPU
        #    puTime:      the time used by the domain in nanoseconds

        #(state, _max_mem, _mem, _num_cpu, _cpu_time) = domain.info()
        #name = domain.name()
        (state, _max_mem, _mem, _num_cpu, _cpu_time) \
            = self._conn.get_domain_info(domain_name)
        name = domain_name
        return driver.InstanceInfo(name, state)

    def list_instances_detail(self):
        infos = []
        #for domain_id in self._conn.listDomainsID():
        #    domain = self._conn.lookupByID(domain_id)
        #    info = self._map_to_instance_info(domain)
        #    infos.append(info)
        for domain_name in self._conn.list_domains():
            info = self._map_to_instance_info(domain_name)
            #info = self._map_to_instance_info(domain['name'])
            infos.append(info)
        return infos

    def destroy(self, instance, network_info, cleanup=True):
        timer = utils.LoopingCall(f=None)

        while True:
            try:
                self._conn.destroy_domain(instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                  instance['id'], power_state.SHUTOFF)
                break
                time.sleep(1)
            except Exception as ex:
                msg = _("Error encountered when destroying instance '%(id)s': "
                        "%(ex)s") % {"id": instance["id"], "ex": ex}
                LOG.debug(msg)
                db.instance_set_state(context.get_admin_context(),
                                      instance['id'],
                                      power_state.SHUTOFF)
                break

        if cleanup:
            self._cleanup(instance)

        return True

    def _cleanup(self, instance):
        target = os.path.join(FLAGS.instances_path, instance['name'])
        instance_name = instance['name']
        LOG.info(_('instance %(instance_name)s: deleting instance files'
                ' %(target)s') % locals())
        if FLAGS.baremetal_type == 'lxc':
            disk.destroy_container(target, instance, nbd=FLAGS.use_cow_images)
        if os.path.exists(target):
            shutil.rmtree(target)

    @exception.wrap_exception
    def attach_volume(self, instance_name, device_path, mountpoint):
        raise exception.APIError("attach_volume not supported for baremetal.")

    @exception.wrap_exception
    def detach_volume(self, instance_name, mountpoint):
        raise exception.APIError("detach_volume not supported for baremetal.")

    @exception.wrap_exception
    def snapshot(self, context, instance, image_href):
        raise exception.APIError("snapshot not supported for baremetal.")
        """Create snapshot from a running VM instance.

        This command only works with qemu 0.14+, the qemu_img flag is
        provided so that a locally compiled binary of qemu-img can be used
        to support this command.
        """

    @exception.wrap_exception
    def reboot(self, instance, network_info):
        timer = utils.LoopingCall(f=None)

        def _wait_for_reboot():
            try:
                state = self._conn.reboot_domain(instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                  instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: rebooted'), instance['name'])
                    timer.stop()
            except Exception:
                LOG.exception(_('_wait_for_reboot failed'))
                db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_reboot
        return timer.start(interval=0.5, now=True)

    @exception.wrap_exception
    def pause(self, instance, callback):
        raise exception.ApiError("pause not supported for baremetal.")

    @exception.wrap_exception
    def unpause(self, instance, callback):
        raise exception.ApiError("unpause not supported for baremetal.")

    @exception.wrap_exception
    def suspend(self, instance, callback):
        raise exception.ApiError("suspend not supported for baremetal")

    @exception.wrap_exception
    def resume(self, instance, callback):
        raise exception.ApiError("resume not supported for baremetal")

    @exception.wrap_exception
    def rescue(self, context, instance, callback, network_info):
        """Loads a VM using rescue images.

        A rescue is normally performed when something goes wrong with the
        primary images and data needs to be corrected/recovered. Rescuing
        should not edit or over-ride the original image, only allow for
        data recovery.

        """
        self.destroy(instance, network_info, cleanup=False)

        xml_dict = self.to_xml_dict(instance, rescue=True)
        rescue_images = {'image_id': FLAGS.baremetal_rescue_image_id,
                         'kernel_id': FLAGS.baremetal_rescue_kernel_id,
                         'ramdisk_id': FLAGS.baremetal_rescue_ramdisk_id}
        #self._create_image(context, instance, xml, '.rescue', rescue_images)
        #self._create_new_domain(xml)

        timer = utils.LoopingCall(f=None)

        def _wait_for_rescue():
            try:
                state = self._conn.reboot_domain(instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                  instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: rescued'), instance['name'])
                    timer.stop()
            except Exception:
                LOG.exception(_('_wait_for_rescue failed'))
                db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_reboot
        return timer.start(interval=0.5, now=True)

    @exception.wrap_exception
    def unrescue(self, instance, network_info):
        """Reboot the VM which is being rescued back into primary images.

        Because reboot destroys and re-creates instances, unresue should
        simply call reboot.

        """
        self.reboot(instance, network_info)

    @exception.wrap_exception
    def poll_rescued_instances(self, timeout):
        pass

    # NOTE(ilyaalekseyev): Implementation like in multinics
    # for xenapi(tr3buchet)
    @exception.wrap_exception
    def spawn(self, context, instance, network_info,
              block_device_mapping=None):
        LOG.debug(_("<============= spawn of baremetal =============>"))
        xml_dict = self.to_xml_dict(instance, network_info)
        db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.BUILDING,  # NOSTATE,
                              'launching')
        self._create_image(context, instance, xml_dict,
                           network_info=network_info,
                           block_device_mapping=block_device_mapping)
        LOG.debug(_("instance %s: is running"), instance['name'])

        def basepath(fname='', suffix=''):
            return os.path.join(FLAGS.instances_path,
                                instance['name'],
                                fname + suffix)
        bpath = basepath(suffix='')
        timer = utils.LoopingCall(f=None)

        def _wait_for_boot():
            try:
                LOG.debug(_(xml_dict))
                state = self._conn.create_domain(xml_dict, bpath)
                LOG.debug(_('~~~~~~ current state = %s ~~~~~~'), state)
                db.instance_set_state(context.get_admin_context(),
                                      instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: booted'), instance['name'])
                    timer.stop()
            except Exception:
                LOG.exception(_('instance %s: failed to boot'),
                              instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                      instance['id'],
                                      power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_boot
        return timer.start(interval=0.5, now=True)

    def _flush_xen_console(self, virsh_output):
        LOG.info(_('virsh said: %r'), virsh_output)
        virsh_output = virsh_output[0].strip()

        if virsh_output.startswith('/dev/'):
            LOG.info(_("cool, it's a device"))
            out, err = utils.execute('sudo', 'dd',
                                     "if=%s" % virsh_output,
                                     'iflag=nonblock',
                                     check_exit_code=False)
            return out
        else:
            return ''

    def _append_to_file(self, data, fpath):
        LOG.info(_('data: %(data)r, fpath: %(fpath)r') % locals())
        fp = open(fpath, 'a+')
        fp.write(data)
        return fpath

    def _dump_file(self, fpath):
        fp = open(fpath, 'r+')
        contents = fp.read()
        LOG.info(_('Contents of file %(fpath)s: %(contents)r') % locals())
        return contents

    @exception.wrap_exception
    def get_console_output(self, instance):
        console_log = os.path.join(FLAGS.instances_path, instance['name'],
                                   'console.log')

        utils.execute('sudo', 'chown', os.getuid(), console_log)

        fd = self._conn.find_domain(instance['name'])

        self.baremetal_nodes.get_console_output(console_log, fd['node_id'])

        fpath = console_log

        return self._dump_file(fpath)

    @exception.wrap_exception
    def get_ajax_console(self, instance):
        raise NotImplementedError()

    @exception.wrap_exception
    def get_vnc_console(self, instance):
        raise NotImplementedError()

    @staticmethod
    def _cache_image(fn, target, fname, cow=False, *args, **kwargs):
        """Wrapper for a method that creates an image that caches the image.

        This wrapper will save the image into a common store and create a
        copy for use by the hypervisor.

        The underlying method should specify a kwarg of target representing
        where the image will be saved.

        fname is used as the filename of the base image.  The filename needs
        to be unique to a given image.

        If cow is True, it will make a CoW image instead of a copy.
        """
        if not os.path.exists(target):
            base_dir = os.path.join(FLAGS.instances_path, '_base')
            if not os.path.exists(base_dir):
                os.mkdir(base_dir)
            base = os.path.join(base_dir, fname)

            @utils.synchronized(fname)
            def call_if_not_exists(base, fn, *args, **kwargs):
                if not os.path.exists(base):
                    fn(target=base, *args, **kwargs)

            call_if_not_exists(base, fn, *args, **kwargs)

            if cow:
                utils.execute('qemu-img', 'create', '-f', 'qcow2', '-o',
                              'cluster_size=2M,backing_file=%s' % base,
                              target)
            else:
                utils.execute('cp', base, target)

    def _fetch_image(self, context, target, image_id, user_id, project_id,
                     size=None):
        """Grab image and optionally attempt to resize it"""
        images.fetch(context, image_id, target, user_id, project_id)

    def _create_local(self, target, local_gb):
        """Create a blank image of specified size"""
        utils.execute('truncate', target, '-s', "%dG" % local_gb)
        # TODO(vish): should we format disk by default?

    def _create_image(self, context, inst, baremetal_xml, suffix='',
                      disk_images=None, network_info=None,
                      block_device_mapping=None):
        if not network_info:
            network_info = netutils.get_network_info(inst)

        if not suffix:
            suffix = ''

        # syntactic nicety
        def basepath(fname='', suffix=suffix):
            return os.path.join(FLAGS.instances_path,
                                inst['name'],
                                fname + suffix)

        # ensure directories exist and are writable
        utils.execute('mkdir', '-p', basepath(suffix=''))
        utils.execute('chmod', '0777', basepath(suffix=''))

        LOG.info(_('instance %s: Creating image'), inst['name'])
        f = open(basepath('baremetal.xml'), 'w')
        #f.write(baremetal_xml)
        f.close()

        if FLAGS.baremetal_type == 'lxc':
            container_dir = '%s/rootfs' % basepath(suffix='')
            utils.execute('mkdir', '-p', container_dir)

        # NOTE(vish): No need add the suffix to console.log
        os.close(os.open(basepath('console.log', ''),
                         os.O_CREAT | os.O_WRONLY, 0660))

        #Test: copying original baremetal images
        bp = basepath(suffix='')
        self.baremetal_nodes.get_image(bp)

        if not disk_images:
            disk_images = {'image_id': inst['image_ref'],
                           'kernel_id': inst['kernel_id'],
                           'ramdisk_id': inst['ramdisk_id']}

        if disk_images['kernel_id']:
            fname = '%08x' % int(disk_images['kernel_id'])
            self._cache_image(fn=self._fetch_image,
                              context=context,
                              target=basepath('kernel'),
                              fname=fname,
                              image_id=disk_images['kernel_id'],
                              user_id=inst['user_id'],
                              project_id=inst['project_id'])
            if disk_images['ramdisk_id']:
                fname = '%08x' % int(disk_images['ramdisk_id'])
                self._cache_image(fn=self._fetch_image,
                                  context=context,
                                  target=basepath('ramdisk'),
                                  fname=fname,
                                  image_id=disk_images['ramdisk_id'],
                                  user_id=inst['user_id'],
                                  project_id=inst['project_id'])

        root_fname = '%08x' % int(disk_images['image_id'])
        size = FLAGS.minimum_root_size

        inst_type_id = inst['instance_type_id']
        inst_type = instance_types.get_instance_type(inst_type_id)
        if inst_type['name'] == 'm1.tiny' or suffix == '.rescue':
            size = None
            root_fname += "_sm"

        self._cache_image(fn=self._fetch_image,
                          context=context,
                          target=basepath('disk'),
                          fname=root_fname,
                          cow=FLAGS.use_cow_images,
                          image_id=disk_images['image_id'],
                          user_id=inst['user_id'],
                          project_id=inst['project_id'],
                          size=size)

        """if inst_type['local_gb']:
            self._cache_image(fn=self._create_local,
                              target=basepath('disk.local'),
                              fname="local_%s" % inst_type['local_gb'],
                              cow=FLAGS.use_cow_images,
                              local_gb=inst_type['local_gb'])"""

        # For now, we assume that if we're not using a kernel, we're using a
        # partitioned disk image where the target partition is the first
        # partition
        target_partition = None
        if not inst['kernel_id']:
            target_partition = "1"

        if FLAGS.baremetal_type == 'lxc':
            target_partition = None

        if inst['key_data']:
            key = str(inst['key_data'])
        else:
            key = None
        net = None

        nets = []
        ifc_template = open(FLAGS.injected_network_template).read()
        ifc_num = -1
        have_injected_networks = False
        admin_context = nova_context.get_admin_context()
        for (network_ref, mapping) in network_info:
            ifc_num += 1

            if not network_ref['injected']:
                continue

            have_injected_networks = True
            address = mapping['ips'][0]['ip']
            address_v6 = None
            gateway_v6 = None
            netmask_v6 = None
            if FLAGS.use_ipv6:
                address_v6 = mapping['ip6s'][0]['ip']
                netmask_v6 = mapping['ip6s'][0]['netmask']
                gateway_v6 = mapping['gateway6']
            net_info = {'name': 'eth%d' % ifc_num,
                   'address': address,
                   'netmask': network_ref['netmask'],
                   'gateway': network_ref['gateway'],
                   'broadcast': network_ref['broadcast'],
                   'dns': network_ref['dns'],
                   'address_v6': address_v6,
                   'gateway_v6': gateway_v6,
                   'netmask_v6': netmask_v6}
            nets.append(net_info)

        if have_injected_networks:
            net = str(Template(ifc_template,
                               searchList=[{'interfaces': nets,
                                            'use_ipv6': FLAGS.use_ipv6}]))

        if key or net:
            inst_name = inst['name']
            img_id = inst.image_ref
            if key:
                LOG.info(_('instance %(inst_name)s: injecting key into'
                        ' image %(img_id)s') % locals())
            if net:
                LOG.info(_('instance %(inst_name)s: injecting net into'
                        ' image %(img_id)s') % locals())
            try:
                disk.inject_data(basepath('root'), key, net,
                                 partition=target_partition,
                                 nbd=FLAGS.use_cow_images)

                if FLAGS.baremetal_type == 'lxc':
                    disk.setup_container(basepath('disk'),
                                        container_dir=container_dir,
                                        nbd=FLAGS.use_cow_images)
            except Exception as e:
                # This could be a windows image, or a vmdk format disk
                LOG.warn(_('instance %(inst_name)s: ignoring error injecting'
                        ' data into image %(img_id)s (%(e)s)') % locals())

        if FLAGS.baremetal_type == 'uml':
            utils.execute('sudo', 'chown', 'root', basepath('disk'))

    def _prepare_xml_info(self, instance, rescue=False, network_info=None):
        # TODO(adiantum) remove network_info creation code
        # when multinics will be completed
        if not network_info:
            network_info = netutils.get_network_info(instance)

        nics = []
        #for (network, mapping) in network_info:
        #    nics.append(self.vif_driver.plug(instance, network, mapping))
        # FIXME(vish): stick this in db
        inst_type_id = instance['instance_type_id']
        inst_type = instance_types.get_instance_type(inst_type_id)

        if FLAGS.use_cow_images:
            driver_type = 'qcow2'
        else:
            driver_type = 'raw'

        xml_info = {'type': FLAGS.baremetal_type,
                    'name': instance['name'],
                    'basepath': os.path.join(FLAGS.instances_path,
                                             instance['name']),
                    'memory_kb': inst_type['memory_mb'] * 1024,
                    'vcpus': inst_type['vcpus'],
                    'rescue': rescue,
                    'local': inst_type['local_gb'],
                    'driver_type': driver_type,
                    'vif_type': FLAGS.libvirt_vif_type,
                    'nics': nics,
                    'ip_address': mapping['ips'][0]['ip'],
                    'mac_address': instance['mac_address'],
                    'image_id': instance['image_ref'],
                    'kernel_id': instance['kernel_id'],
                    'ramdisk_id': instance['ramdisk_id']}

        if FLAGS.vnc_enabled and FLAGS.libvirt_type not in ('lxc', 'uml'):
            xml_info['vncserver_host'] = FLAGS.vncserver_host
            xml_info['vnc_keymap'] = FLAGS.vnc_keymap
        if not rescue:
            if instance['kernel_id']:
                xml_info['kernel'] = xml_info['basepath'] + "/kernel"

            if instance['ramdisk_id']:
                xml_info['ramdisk'] = xml_info['basepath'] + "/ramdisk"

            xml_info['disk'] = xml_info['basepath'] + "/disk"
        return xml_info

    def to_xml_dict(self, instance, rescue=False, network_info=None):
        # TODO(termie): cache?
        LOG.debug(_('instance %s: starting toXML method'), instance['name'])
        xml_info = self._prepare_xml_info(instance, rescue, network_info)
        xml = str(Template(self.baremetal_xml, searchList=[xml_info]))
        LOG.debug(_('instance %s: finished toXML method'), instance['name'])
        #return xml
        return xml_info

    def get_info(self, instance_name):
        """Retrieve information from baremetal for a specific instance name.

        If a baremetal error is encountered during lookup, we might raise a
        NotFound exception or Error exception depending on how severe the
        baremetal error is.

        """
        #virt_dom = self._lookup_by_name(instance_name)
        #(state, max_mem, mem, num_cpu, cpu_time) = virt_dom.info()
        (state, max_mem, mem, num_cpu, cpu_time) \
                = self._conn.get_domain_info(instance_name)
        return {'state': state,
                'max_mem': max_mem,
                'mem': mem,
                'num_cpu': num_cpu,
                'cpu_time': cpu_time}

    def _create_new_domain(self, xml, persistent=True, launch_flags=0):
        raise NotImplementedError()

    def get_diagnostics(self, instance_name):
        raise exception.ApiError(_("diagnostics are not supported "
                                   "for baremetal"))

    def get_disks(self, instance_name):
        raise NotImplementedError()
        """
        Note that this function takes an instance name.

        Returns a list of all block devices for this domain.
        """

    def get_interfaces(self, instance_name):
        raise NotImplementedError()
        """
        Note that this function takes an instance name.

        Returns a list of all network interfaces for this instance.
        """

    def get_vcpu_total(self):
        """Get vcpu number of physical computer.

        :returns: the number of cpu core.

        """

        # On certain platforms, this will raise a NotImplementedError.
        try:
            #return multiprocessing.cpu_count()
            return self.baremetal_nodes.get_hw_info('vcpus')  # 10
        except NotImplementedError:
            LOG.warn(_("Cannot get the number of cpu, because this "
                       "function is not implemented for this platform. "
                       "This error can be safely ignored for now."))
            return 0

    def get_memory_mb_total(self):
        """Get the total memory size(MB) of physical computer.

        :returns: the total amount of memory(MB).

        """

        #if sys.platform.upper() != 'LINUX2':
        #    return 0

        #meminfo = open('/proc/meminfo').read().split()
        #idx = meminfo.index('MemTotal:')
        ## transforming kb to mb.
        #return int(meminfo[idx + 1]) / 1024
        return self.baremetal_nodes.get_hw_info('memory_mb')  # 16218

    def get_local_gb_total(self):
        """Get the total hdd size(GB) of physical computer.

        :returns:
            The total amount of HDD(GB).
            Note that this value shows a partition where
            NOVA-INST-DIR/instances mounts.

        """

        #hddinfo = os.statvfs(FLAGS.instances_path)
        #return hddinfo.f_frsize * hddinfo.f_blocks / 1024 / 1024 / 1024
        return self.baremetal_nodes.get_hw_info('local_gb')  # 917

    def get_vcpu_used(self):
        """ Get vcpu usage number of physical computer.

        :returns: The total number of vcpu that currently used.

        """

        total = 0
        #for dom_id in self._conn.listDomainsID():
        #    dom = self._conn.lookupByID(dom_id)
        #    total += len(dom.vcpus()[1])
        for dom_id in self._conn.list_domains():
            total += 1
        return total

    def get_memory_mb_used(self):
        """Get the free memory size(MB) of physical computer.

        :returns: the total usage of memory(MB).

        """

        #if sys.platform.upper() != 'LINUX2':
        #    return 0

        #m = open('/proc/meminfo').read().split()
        #idx1 = m.index('MemFree:')
        #idx2 = m.index('Buffers:')
        #idx3 = m.index('Cached:')
        #avail = (int(m[idx1 + 1]) + int(m[idx2 + 1]) + int(m[idx3 + 1]))/1024
        #return  self.get_memory_mb_total() - avail
        return self.baremetal_nodes.get_hw_info('memory_mb_used')  # 476

    def get_local_gb_used(self):
        """Get the free hdd size(GB) of physical computer.

        :returns:
           The total usage of HDD(GB).
           Note that this value shows a partition where
           NOVA-INST-DIR/instances mounts.

        """

        #hddinfo = os.statvfs(FLAGS.instances_path)
        #avail = hddinfo.f_frsize * hddinfo.f_bavail / 1024 / 1024 / 1024
        #return self.get_local_gb_total() - avail
        return self.baremetal_nodes.get_hw_info('local_gb_used')  # 1

    def get_hypervisor_type(self):
        """Get hypervisor type.

        :returns: hypervisor type (ex. qemu)

        """

        #return self._conn.getType()
        return self.baremetal_nodes.get_hw_info('hypervisor_type')

    def get_hypervisor_version(self):
        """Get hypervisor version.

        :returns: hypervisor version (ex. 12003)

        """

        # NOTE(justinsb): getVersion moved between baremetal versions
        # Trying to do be compatible with older versions is a lost cause
        # But ... we can at least give the user a nice message
        #method = getattr(self._conn, 'getVersion', None)
        #if method is None:
        #    raise exception.Error(_("baremetal version is too old"
        #                            " (does not support getVersion)"))
            # NOTE(justinsb): If we wanted to get the version, we could:
            # method = getattr(baremetal, 'getVersion', None)
            # NOTE(justinsb): This would then rely on a proper version check

        #return method()
        return self.baremetal_nodes.get_hw_info('hypervisor_version')  # 1

    def get_cpu_info(self):
        """Get cpuinfo information.

        Obtains cpu feature from virConnect.getCapabilities,
        and returns as a json string.

        :return: see above description

        """
        return self.baremetal_nodes.get_hw_info('cpu_info')

    def block_stats(self, instance_name, disk):
        raise NotImplementedError()
        """
        Note that this function takes an instance name.
        """

    def interface_stats(self, instance_name, interface):
        raise NotImplementedError()
        """
        Note that this function takes an instance name.
        """

    def get_console_pool_info(self, console_type):
        #TODO(mdragon): console proxy should be implemented for baremetal,
        #               in case someone wants to use it with kvm or
        #               such. For now return fake data.
        return  {'address': '127.0.0.1',
                 'username': 'fakeuser',
                 'password': 'fakepassword'}

    def refresh_security_group_rules(self, security_group_id):
        # Bare metal doesn't currently support security groups
        pass

    def refresh_security_group_members(self, security_group_id):
        # Bare metal doesn't currently support security groups
        pass

    def update_available_resource(self, ctxt, host):
        """Updates compute manager resource info on ComputeNode table.

        This method is called when nova-coompute launches, and
        whenever admin executes "nova-manage service update_resource".

        :param ctxt: security context
        :param host: hostname that compute manager is currently running

        """

        try:
            service_ref = db.service_get_all_compute_by_host(ctxt, host)[0]
        except exception.NotFound:
            raise exception.ComputeServiceUnavailable(host=host)

        # Updating host information
        dic = {'vcpus': self.get_vcpu_total(),
               'memory_mb': self.get_memory_mb_total(),
               'local_gb': self.get_local_gb_total(),
               'vcpus_used': self.get_vcpu_used(),
               'memory_mb_used': self.get_memory_mb_used(),
               'local_gb_used': self.get_local_gb_used(),
               'hypervisor_type': self.get_hypervisor_type(),
               'hypervisor_version': self.get_hypervisor_version(),
               'cpu_info': self.get_cpu_info(),
               #RLK
               'cpu_arch': FLAGS.cpu_arch,
               'xpu_arch': FLAGS.xpu_arch,
               'xpus': FLAGS.xpus,
               'xpu_info': FLAGS.xpu_info,
               'net_arch': FLAGS.net_arch,
               'net_info': FLAGS.net_info,
               'net_mbps': FLAGS.net_mbps}

        compute_node_ref = service_ref['compute_node']
        LOG.info(_('#### RLK: cpu_arch = %s ') % FLAGS.cpu_arch)
        if not compute_node_ref:
            LOG.info(_('Compute_service record created for %s ') % host)
            dic['service_id'] = service_ref['id']
            db.compute_node_create(ctxt, dic)
        else:
            LOG.info(_('Compute_service record updated for %s ') % host)
            db.compute_node_update(ctxt, compute_node_ref[0]['id'], dic)

    def compare_cpu(self, cpu_info):
        raise NotImplementedError()

    def ensure_filtering_rules_for_instance(self, instance_ref,
                                            time=None):
        raise NotImplementedError()

    def live_migration(self, ctxt, instance_ref, dest,
                       post_method, recover_method):
        raise NotImplementedError()

    def unfilter_instance(self, instance_ref, network_info):
        """See comments of same method in firewall_driver."""
        pass

    def update_host_status(self):
        """Update the status info of the host, and return those values
            to the calling program."""
        return self.HostState.update_status()

    def get_host_stats(self, refresh=False):
        """Return the current state of the host. If 'refresh' is
           True, run the update first."""
        LOG.debug(_("Updating!"))
        return self.HostState.get_host_stats(refresh=refresh)


class HostState(object):
    """Manages information about the XenServer host this compute
    node is running on.
    """

    def __init__(self, read_only):
        super(HostState, self).__init__()
        self.read_only = read_only
        self._stats = {}
        self.update_status()

    def get_host_stats(self, refresh=False):
        """Return the current state of the host. If 'refresh' is
        True, run the update first.
        """
        if refresh:
            self.update_status()
        return self._stats

    def update_status(self):
        """Since under Xenserver, a compute node runs on a given host,
        we can get host status information using xenapi.
        """
#        data = {'vcpus': self.get_vcpu_total(),
#               'memory_mb': self.get_memory_mb_total(),
#               'local_gb': self.get_local_gb_total(),
#               'vcpus_used': self.get_vcpu_used(),
#               'memory_mb_used': self.get_memory_mb_used(),
#               'local_gb_used': self.get_local_gb_used(),
#               'hypervisor_type': self.get_hypervisor_type(),
#               'hypervisor_version': self.get_hypervisor_version(),
#               'cpu_info': self.get_cpu_info(),
#               #RLK
#               'cpu_arch': FLAGS.cpu_arch,
#               'xpu_arch': FLAGS.xpu_arch,
#               'xpus': FLAGS.xpus,
#               'xpu_info': FLAGS.xpu_info,
#               'net_arch': FLAGS.net_arch,
#               'net_info': FLAGS.net_info,
#               'net_mbps': FLAGS.net_mbps}
        LOG.debug(_("Updating host stats"))
        #LOG.debug(_("Updating statistics!!"))
        connection = get_connection(self.read_only)
        data = {}
        data["vcpus"] = connection.get_vcpu_total()
        data["vcpus_used"] = connection.get_vcpu_used()
        data["cpu_info"] = connection.get_cpu_info()
        data["cpu_arch"] = FLAGS.cpu_arch
        data["xpus"] = FLAGS.xpus
        data["xpu_arch"] = FLAGS.xpu_arch
        #  data["xpus_used"] = 0
        data["xpu_info"] = FLAGS.xpu_info
        data["net_arch"] = FLAGS.net_arch
        data["net_info"] = FLAGS.net_info
        data["net_mbps"] = FLAGS.net_mbps
        data["disk_total"] = connection.get_local_gb_total()
        data["disk_used"] = connection.get_local_gb_used()
        data["disk_available"] = data["disk_total"] - data["disk_used"]
        data["host_memory_total"] = connection.get_memory_mb_total()
        data["host_memory_free"] = data["host_memory_total"] - \
            connection.get_memory_mb_used()
        data["hypervisor_type"] = connection.get_hypervisor_type()
        data["hypervisor_version"] = connection.get_hypervisor_version()
        self._stats = data
