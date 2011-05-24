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
A connection to a hypervisor through tilera.

Supports KVM, LXC, QEMU, UML, and XEN.

**Related Flags**

:tilera_type:  Libvirt domain type.  Can be kvm, qemu, uml, xen
                (default: kvm).
:tilera_uri:  Override for the default tilera URI (depends on tilera_type).
:tilera_xml_template:  Libvirt XML Template.
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
# MK
import pickle
# _MK
from xml.dom import minidom
from xml.etree import ElementTree

from eventlet import greenthread
from eventlet import tpool

import IPy

from nova import context
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

libxml2 = None
Template = None

LOG = logging.getLogger('nova.virt.tilera')

FLAGS = flags.FLAGS
flags.DEFINE_string('tilera_injected_network_template',
                    utils.abspath('virt/tilera_interfaces.template'),
                    'Template file for injected network')
flags.DEFINE_string('tilera_xml_template',
                    utils.abspath('virt/tilera.xml.template'),
                    'tilera XML Template')
flags.DEFINE_string('tilera_type',
                    'tilera',
                    'tilera domain type')
flags.DEFINE_string('tilera_uri',
                    '',
                    'Override the default tilera URI')
flags.DEFINE_bool('tilera_allow_project_net_traffic',
                  True,
                  'Whether to allow in project network traffic')


# MK
global tilera_boards
global fake_doms


class _tilera_board(object):
    """Manages tilera board information"""
    file_name = "/tftpboot/tilera_boards"
    boards = []
    BOARD_ID = 0
    IP_ADDR = 1
    MAC_ADDR = 2
    #BOARD_STATUS = 3
    VCPUS = 3
    MEMORY_MB = 4
    LOCAL_GB = 5
    MEMORY_MB_USED = 6
    LOCAL_GB_USED = 7
    HYPERVISOR_TYPE = 8
    HYPERVISOR_VER = 9
    CPU_INFO = 10

    def __init__(self):
        self.fp = open(self.file_name, "r")
        for item in self.fp:
            l = item.split()
            if l[0] == '#':
                continue
            l_d = {'board_id': int(l[self.BOARD_ID]),
                    'ip_addr': l[self.IP_ADDR],
                    'mac_addr': l[self.MAC_ADDR],
                    'status': power_state.NOSTATE,
                    'vcpus': int(l[self.VCPUS]),
                    'memory_mb': int(l[self.MEMORY_MB]),
                    'local_gb': int(l[self.LOCAL_GB]),
                    'memory_mb_used': int(l[self.MEMORY_MB_USED]),
                    'local_gb_used': int(l[self.LOCAL_GB_USED]),
                    'hypervisor_type': l[self.HYPERVISOR_TYPE],
                    'hypervisor_version': l[self.HYPERVISOR_VER],
                    'cpu_info': l[self.CPU_INFO]
                  }
            self.boards.append(l_d)
        #print self.boards

    def get_tilera_hw_info(self, field):
        for board in self.boards:
            if board['board_id'] == 9:
                if field == 'vcpus':
                    return board['vcpus']
                elif field == 'memory_mb':
                    return board['memory_mb']
                elif field == 'local_gb':
                    return board['local_gb']
                elif field == 'memory_mb_used':
                    return board['memory_mb_used']
                elif field == 'local_gb_used':
                    return board['local_gb_used']
                elif field == 'hypervisor_type':
                    return board['hypervisor_type']
                elif field == 'hypervisor_version':
                    return board['hypervisor_version']
                elif field == 'cpu_info':
                    return board['cpu_info']

    def set_status(self, board_id, status):
        for board in self.boards:
            if board['board_id'] == board_id:
                board['board_id'] = status
                return 1
        return 0

    def check_idle_board(self):
        """check an idle board"""
        for item in self.boards:
            if item['status'] == 0:
                return item['board_id']
        return -1

    def get_idle_board(self):
        """get an idle board"""
        for item in self.boards:
            if item['status'] == 0:
                item['status'] = 1      # make status RUNNING
                return item['board_id']
        return -1

    def find_ip_w_id(self, id):
        for item in self.boards:
            if item['board_id'] == id:
                return item['ip_addr']

    def free_board(self, board_id):
        print("free_board....\n")
        for item in self.boards:
            if item['board_id'] == str(board_id):
                item['status'] = 0  # make status IDLE
                return
        return -1

    def deactivate_board(self, board_id):
        board_ip = tilera_boards.find_ip_w_id(board_id)
        #print("deactivate_board is not implemented yet, \
        print("deactivate_board is called for \
               board_id = %s board_ip = %s\n", str(board_id), board_ip)
        for item in self.boards:
            if item['board_id'] == board_id:
                print "status of board is set to 0"
                item['status'] = 0

        if board_id < 5:
            pdu_num = 1
            pdu_outlet_num = board_id + 5
        else:
            pdu_num = 2
            pdu_outlet_num = board_id
        cmd = "/tftpboot/pdu_mgr 10.0.100." + str(pdu_num) + " " \
            + str(pdu_outlet_num) + " 2 >> pdu_output"
        print cmd
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            '2', '>>', 'pdu_output')

        return []
        #raise

    #def activate_board(self, board_id, board_ip, name, mac_address):
    def activate_board(self, board_id, board_ip, name, mac_address, \
        ip_address):
        print("activate_board \n")

        target = os.path.join(FLAGS.instances_path, name)
        print target

        cmd = "cp /tftpboot/vmlinux_" + str(board_id) + \
            "_1 /tftpboot/vmlinux_" + str(board_id)
        print cmd
        path1 = "/tftpboot/vmlinux_" + str(board_id) + "_1"
        path2 = "/tftpboot/vmlinux_" + str(board_id)
        utils.execute('cp', path1, path2)

        if board_id < 5:
            pdu_num = 1
            pdu_outlet_num = board_id + 5
        else:
            pdu_num = 2
            pdu_outlet_num = board_id
        cmd = "/tftpboot/pdu_mgr 10.0.100." + str(pdu_num) + " " \
        + str(pdu_outlet_num) + " 3 >> pdu_output"
        print cmd
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            str(3), '>>', 'pdu_output')

        cmd = "sleep 60"
        print cmd
        utils.execute('sleep', str(60))
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --upload /tftpboot/tilera_fs_" \
            + str(board_id) + ".tar.gz /tilera_fs.tar.gz --quit"
        print cmd
        path1 = "/tftpboot/tilera_fs_" + str(board_id) + ".tar.gz"
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--upload', path1, \
            '/tilera_fs.tar.gz', '--quit')
        utils.execute('rm', path1)
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - mount /dev/sda1 /mnt - --wait " \
            + "--run - tar -xzpf /tilera_fs.tar.gz -C /mnt/ " \
            + "- --wait --quit"
        print cmd
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', 'mount', \
            '/dev/sda1', '/mnt', '-', '--wait', '--run', '-', 'tar', \
            '-xzpf', '/tilera_fs.tar.gz', '-C', '/mnt/', '-', \
            '--wait', '--quit')

        cmd = "cp /tftpboot/vmlinux_" + str(board_id) + \
            "_2 /tftpboot/vmlinux_" + str(board_id)
        print cmd
        path1 = "/tftpboot/vmlinux_" + str(board_id) + "_2"
        path2 = "/tftpboot/vmlinux_" + str(board_id)
        utils.execute('cp', path1, path2)
        cmd = "/tftpboot/pdu_mgr 10.0.100." + str(pdu_num) + " " \
            + str(pdu_outlet_num) + " 3 >> pdu_output"
        print cmd
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            '3', '>>', 'pdu_output')
        cmd = "sleep 80"
        print cmd
        utils.execute('sleep', str(80))

        #cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net "
        # + board_ip + " --run - /usr/sbin/sshd - --wait -- ls
        #| grep bin >> tile_output"
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - /usr/sbin/sshd - --wait --quit"
        print cmd
        #utils.execute('/usr/local/TileraMDE/bin/tile-monitor',
        #'--resume', '--net', board_ip, '--run', '-', '/usr/sbin/sshd', \
        #'-', '--wait', '--', 'ls', '|', 'grep', 'bin', \
        #'>>', 'tile_output')
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', \
            '/usr/sbin/sshd', '-', '--wait', '--quit')

        #file = open("./tile_output")
        #out_msg = file.readline()
        #print "tile_output: " + out_msg
        #utils.execute('rm', './tile_output')
        #file.close()
        #if out_msg.find("bin") < 0:
        #    cmd = "TILERA_BOARD_#" + str(board_id) + " " \
        #+ board_ip + " is not ready, out_msg=" + out_msg
        #    print cmd
        #    return power_state.NOSTATE
        #else:
        cmd = "TILERA_BOARD_#" + str(board_id) + " " + board_ip \
            + " is ready"
        print cmd
        cmd = "rm /tftpboot/vmlinux_" + str(board_id)
        print cmd
        path1 = "/tftpboot/vmlinux_" + str(board_id)
        utils.execute('rm', path1)
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - ifconfig xgbe0 hw ether " \
            + mac_address + " - --wait --run - ifconfig xgbe0 " \
            + ip_address + " - --wait --quit"
        print cmd
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', \
            'ifconfig', 'xgbe0', 'hw', 'ether', mac_address, '-', \
            '--wait', '--run', '-', 'ifconfig', 'xgbe0', ip_address, \
            '-', '--wait', '--quit')
        cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net " \
            + board_ip + " --run - iptables -A INPUT -p tcp " \
            + "! -s 10.0.11.1 --dport 963 -j DROP - --wait " \
            + "--quit"
            #+ "--run - rm -rf /usr/sbin/iptables* - --wait \
        print cmd
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', board_ip, '--run', '-', \
            'iptables', '-A', 'INPUT', '-p', 'tcp', '!', '-s', \
            '10.0.11.1', '--dport', '963', '-j', 'DROP', '-', '--wait', \
            #'--run', '-', 'rm', '-rf', '/usr/sbin/iptables*', \
            #'-', '--wait', \
            '--quit')
        return power_state.RUNNING


class _fake_dom(object):
    """Fake domain for Tilera to avoid using tilera"""
    fake_dom_file = "/tftpboot/test_fake_dom_file"
    fake_dom_nums = 0
    domains = []
    fp = 0

    def __init__(self):
        self.domains = []
        utils.execute('rm', self.fake_dom_file)
        print "open %s" % self.fake_dom_file
        try:
            self.fp = open(self.fake_dom_file, "r+")
            print "fp = "
            print self.fp
        except IOError:
            print ("%s file does not exist, but is created\n" \
                % self.fake_dom_file)
            self.fp = open(self.fake_dom_file, "w")
            self.fp.close()
            self.fp = open(self.fake_dom_file, "r+")
        self.read_domain_from_file()
        # (TODO) read pre-existing fake domains

    def read_domain_from_file(self):
        try:
            self.domains = pickle.load(self.fp)
            self.fp.close()
            self.fp = open(self.fake_dom_file, "w")
        except EOFError:
            dom = []
            self.fp.close()
            self.fp = open(self.fake_dom_file, "w")
            print "No domains exist."
            return
        print "============= initial domains ==========="
        print self.domains
        print "========================================="
        for dom in self.domains:
            if dom['status'] != power_state.RUNNING:
                print "Not running domain: remove"
                self.domains.remove(dom)
                continue
            res = tilera_boards.set_status(dom['board_id'], \
                                    dom['status'])
            if res > 0:  # no such board exixts
                self.fake_dom_nums = self.fake_dom_nums + 1
            else:
                print "domain running on an unknown board: discarded"
                self.domains.remove(dom)
                continue

        print "--> domains after reading"
        print self.domains

    def reboot_domain(self, name):
        fd = self.find_domain(name)
        if fd == []:
            raise exception.NotFound("No such domain (%s)" % name)
        board_ip = tilera_boards.find_ip_w_id(fd['board_id'])

        try:
            tilera_boards.deactivate_board(fd['board_id'])
        except:
            raise exception.NotFound("Failed power down \
                                      Tilera board %s" % fd['board_id'])
        self.change_domain_state(name, power_state.NOSTATE)
        try:
            state = tilera_boards.activate_board(fd['board_id'], \
                board_ip, name, fd['mac_address'], fd['ip_address'])
                #board_ip, name, fd['mac_address']) #MK
                #fd['ip_addr'], name)
            self.change_domain_state(name, state)
            return state
        except:
            LOG.debug(_("deactivate -> activate fails"))
            self.destroy_domain(name)
            raise

    def destroy_domain(self, name):
        """remove name instance from domains list
           and power down the corresponding Tilera board"""
        fd = self.find_domain(name)
        if fd == []:
            print "destroy_domain: no such domain"
            raise exception.NotFound("No such domain %s" % name)

        try:
            tilera_boards.deactivate_board(fd['board_id'])
            print "--> after deactivate board"
            kmsg_dump_file = "/tftpboot/kmsg_dump_0"  # + str(fd['board_id'])
            utils.execute('rm', kmsg_dump_file)
            self.domains.remove(fd)
            print "domains: "
            print self.domains
            print "boards: "
            print tilera_boards.boards
            self.store_domain()
            print "after storing domains"
            print self.domains
        except:
            print "what to do?"
            raise

    def create_domain(self, xml_dict, bpath):
        """add a domain to domains list
           and activate a idle Tilera board"""
        LOG.debug(_("1////////////////////"))
        fd = self.find_domain(xml_dict['name'])
        if fd != []:
            print 'domain with the same name already exists'
            raise
            #raise exception.NotFound("same name already exists")
        print "create_domain: before get_idle_board"

        board_id = tilera_boards.get_idle_board()
        if board_id == -1:
            print ('No idle tilera board exits')
            raise exception.NotFound("No free boards available")

        board_ip = tilera_boards.find_ip_w_id(board_id)

        new_dom = {'board_id': board_id,
                    'name': xml_dict['name'],
                    'memory_kb': xml_dict['memory_kb'], \
                    'vcpus': xml_dict['vcpus'], \
                    'mac_address': xml_dict['mac_address'], \
                    'ip_address': xml_dict['ip_address'], \
                    #'dhcp_server': xml_dict['dhcp_server'], \
                    'image_id': xml_dict['image_id'], \
                    'kernel_id': xml_dict['kernel_id'], \
                    'ramdisk_id': xml_dict['ramdisk_id'], \
                     'status': power_state.NOSTATE}
        self.domains.append(new_dom)
        print new_dom
        self.change_domain_state(new_dom['name'], power_state.NOSTATE)

        cmd = "mount -o loop " + bpath + "/root /tftpboot/fs_" \
            + str(board_id)
        print cmd
        path1 = bpath + "/root"
        path2 = "/tftpboot/fs_" + str(board_id)
        utils.execute('mount', '-o', 'loop', path1, path2)
        cmd = "cd /tftpboot/fs_" + str(board_id) + \
            "; tar -czpf ../tilera_fs_" + str(board_id) + ".tar.gz ."
        print cmd
        path1 = "/tftpboot/fs_" + str(board_id)
        os.chdir(path1)
        path2 = "../tilera_fs_" + str(board_id) + ".tar.gz"
        utils.execute('tar', '-czpf', path2, '.')
        path1 = bpath + "/../../.."
        os.chdir(path1)
        cmd = "umount -l /tftpboot/fs_" + str(board_id)
        print cmd
        path4 = "/tftpboot/fs_" + str(board_id)
        utils.execute('umount', '-l', path4)

        try:
            state = tilera_boards.activate_board(board_id,
                board_ip, new_dom['name'], new_dom['mac_address'], \
                new_dom['ip_address'])
                #board_ip, new_dom['name'], new_dom['mac_address']) #MK
        except:
            self.domains.remove(new_dom)
            tilera_boards.free_board(board_id)
            raise exception.NotFound("Failed to boot Tilera board %s" \
                % board_id)

        print "BEFORE last self.change_domain_state +++++++++++++++++"
        self.change_domain_state(new_dom['name'], state)
        return state

    def change_domain_state(self, name, state):
        l = self.find_domain(name)
        if l == []:
            raise exception.NotFound("No such domain exists")
        i = self.domains.index(l)
        self.domains[i]['status'] = state
        print "change_domain_state: to new state %s" % str(state)
        self.store_domain()

    def store_domain(self):
        # store fake domains to the file
        print "store fake domains to the file"
        print "-------"
        print self.domains
        print "-------"
        print self.fp
        self.fp.seek(0)
        pickle.dump(self.domains, self.fp)
        print "after successful pickle.dump"

    def find_domain(self, name):
        print "find_domain: self.domains %s" % name
        print self.domains
        for item in self.domains:
            if item['name'] == name:
                return item
        print "domain does not exist\n"
        return []

    def list_domains(self):
        if self.domains == []:
            return []
        return [x['name'] for x in self.domains]

    def get_domain_info(self, instance_name):
        domain = self.find_domain(instance_name)
        if domain != []:
            return [domain['status'], domain['memory_mb'], \
                    domain['memory_mb'], \
                    domain['vcpus'], \
                    100]
        else:
            return [power_state.NOSTATE, '', '', '', '']
            #raise exception.NotFound("get_domain_info: No such doamin %s" \
            #                          % instance_name)
#_MK


def get_connection(read_only):
    # These are loaded late so that there's no need to install these
    # libraries when not using tilera.
    # Cheetah is separate because the unit tests want to load Cheetah,
    # but not tilera.
    global libxml2
    if libxml2 is None:
        libxml2 = __import__('libxml2')
    _late_load_cheetah()
    return tileraConnection(read_only)


def _late_load_cheetah():
    global Template
    if Template is None:
        t = __import__('Cheetah.Template', globals(), locals(),
                       ['Template'], -1)
        Template = t.Template


def _get_net_and_mask(cidr):
    net = IPy.IP(cidr)
    return str(net.net()), str(net.netmask())


def _get_net_and_prefixlen(cidr):
    net = IPy.IP(cidr)
    return str(net.net()), str(net.prefixlen())


def _get_ip_version(cidr):
    net = IPy.IP(cidr)
    return int(net.version())


def _get_network_info(instance):
    # TODO(adiantum) If we will keep this function
    # we should cache network_info
    admin_context = context.get_admin_context()

    ip_addresses = db.fixed_ip_get_all_by_instance(admin_context,
                                                   instance['id'])
    networks = db.network_get_all_by_instance(admin_context,
                                              instance['id'])
    flavor = db.instance_type_get_by_id(admin_context,
                                        instance['instance_type_id'])
    network_info = []

    for network in networks:
        network_ips = [ip for ip in ip_addresses
                       if ip['network_id'] == network['id']]

        def ip_dict(ip):
            return {
                'ip': ip['address'],
                'netmask': network['netmask'],
                'enabled': '1'}

        def ip6_dict():
            prefix = network['cidr_v6']
            mac = instance['mac_address']
            project_id = instance['project_id']
            return  {
                'ip': ipv6.to_global(prefix, mac, project_id),
                'netmask': network['netmask_v6'],
                'enabled': '1'}

        mapping = {
            'label': network['label'],
            'gateway': network['gateway'],
            'broadcast': network['broadcast'],
            'mac': instance['mac_address'],
            'rxtx_cap': flavor['rxtx_cap'],
            'dns': [network['dns']],
            'ips': [ip_dict(ip) for ip in network_ips]}

        if FLAGS.use_ipv6:
            mapping['ip6s'] = [ip6_dict()]
            mapping['gateway6'] = network['gateway_v6']

        network_info.append((network, mapping))
    return network_info


class tileraConnection(driver.ComputeDriver):

    def __init__(self, read_only):
        super(tileraConnection, self).__init__()
        #self.tilera_uri = self.get_uri()

        self.tilera_xml = open(FLAGS.tilera_xml_template).read()
        self.cpuinfo_xml = open(FLAGS.cpuinfo_xml_template).read()
        self._wrapped_conn = None
        self.read_only = read_only

        fw_class = utils.import_class(FLAGS.firewall_driver)
        self.firewall_driver = fw_class(get_connection=self._get_connection)
        self._host_state = None
#        self.session = None

    @property
    def HostState(self):
        if not self._host_state:
            self._host_state = HostState(self.read_only)
        return self._host_state

    def init_host(self, host):
        # Adopt existing VM's running here
        ctxt = context.get_admin_context()
        for instance in db.instance_get_all_by_host(ctxt, host):
            try:
                LOG.debug(_('Checking state of %s'), instance['name'])
                state = self.get_info(instance['name'])['state']
            except exception.NotFound:
                state = power_state.SHUTOFF

            LOG.debug(_('Current state of %(name)s was %(state)s.'),
                          {'name': instance['name'], 'state': state})
            db.instance_set_state(ctxt, instance['id'], state)

            # NOTE(justinsb): We no longer delete SHUTOFF instances,
            # the user may want to power them back on

            if state != power_state.RUNNING:
                continue
            self.firewall_driver.prepare_instance_filter(instance)
            self.firewall_driver.apply_instance_filter(instance)

    def _get_connection(self):
        #if not self._wrapped_conn or not self._test_connection():
        #    LOG.debug(_('Connecting to tilera: %s'), self.tilera_uri)
        #    self._wrapped_conn = self._connect(self.tilera_uri,
        #                               self.read_only)
        # MK
        self._wrapped_conn = fake_doms
        # _MK
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
        return self._conn.list_domains()  # MK

    def _map_to_instance_info(self, domain):
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
            = self.get_info(domain_name)
        name = domain_name

        return driver.InstanceInfo(name, state)

    def list_instances_detail(self):
        infos = []
        #for domain_id in self._conn.listDomainsID():
        #    domain = self._conn.lookupByID(domain_id)
        #    info = self._map_to_instance_info(domain)
        #    infos.append(info)
        for domain in self._conn.list_domains():
            info = self._map_to_instance_info(domain['name'])
            infos.append(info)
        return infos

    def destroy(self, instance, cleanup=True):
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

        #self.firewall_driver.unfilter_instance(instance)

        if cleanup:
            self._cleanup(instance)

        return True

    def _cleanup(self, instance):
        target = os.path.join(FLAGS.instances_path, instance['name'])
        instance_name = instance['name']
        LOG.info(_('instance %(instance_name)s: deleting instance files'
                ' %(target)s') % locals())
        if FLAGS.tilera_type == 'lxc':
            disk.destroy_container(target, instance, nbd=FLAGS.use_cow_images)
        if os.path.exists(target):
            shutil.rmtree(target)

    @exception.wrap_exception
    def attach_volume(self, instance_name, device_path, mountpoint):
        raise exception.APIError("attach_volume not supported for tilera.")

    @exception.wrap_exception
    def detach_volume(self, instance_name, mountpoint):
        raise exception.APIError("detach_volume not supported for tilera.")

    @exception.wrap_exception
    def snapshot(self, instance, image_id):
        raise exception.APIError("snapshot not supported for tilera.")
        """Create snapshot from a running VM instance.

        This command only works with qemu 0.14+, the qemu_img flag is
        provided so that a locally compiled binary of qemu-img can be used
        to support this command.
        """

    @exception.wrap_exception
    def reboot(self, instance):
        timer = utils.LoopingCall(f=None)

        def _wait_for_reboot():
            try:
                state = self._conn.reboot_domain(instance['name'])
                db.instance_set_state(context.get_admin_context(),
                                  instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: rebooted'), instance['name'])
                    timer.stop()
            except:
                LOG.exception(_('_wait_for_reboot failed'))
                db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_reboot
        return timer.start(interval=0.5, now=True)

    @exception.wrap_exception
    def pause(self, instance, callback):
        raise exception.ApiError("pause not supported for tilera.")

    @exception.wrap_exception
    def unpause(self, instance, callback):
        raise exception.ApiError("unpause not supported for tilera.")

    @exception.wrap_exception
    def suspend(self, instance, callback):
        raise exception.ApiError("suspend not supported for tilera")

    @exception.wrap_exception
    def resume(self, instance, callback):
        raise exception.ApiError("resume not supported for tilera")

    @exception.wrap_exception
    def rescue(self, instance):
        """Loads a VM using rescue images.

        A rescue is normally performed when something goes wrong with the
        primary images and data needs to be corrected/recovered. Rescuing
        should not edit or over-ride the original image, only allow for
        data recovery.

        """
        self.destroy(instance, False)

        xml_dict = self.to_xml_dict(instance, rescue=True)
        rescue_images = {'image_id': FLAGS.tilera_rescue_image_id,
                         'kernel_id': FLAGS.tilera_rescue_kernel_id,
                         'ramdisk_id': FLAGS.tilera_rescue_ramdisk_id}
        #self._create_image(instance, xml, '.rescue', rescue_images)
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
            except:
                LOG.exception(_('_wait_for_rescue failed'))
                db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.SHUTDOWN)
                timer.stop()
        timer.f = _wait_for_reboot
        return timer.start(interval=0.5, now=True)

    @exception.wrap_exception
    def unrescue(self, instance):
        """Reboot the VM which is being rescued back into primary images.

        Because reboot destroys and re-creates instances, unresue should
        simply call reboot.

        """
        self.reboot(instance)

    @exception.wrap_exception
    def poll_rescued_instances(self, timeout):
        pass

    # NOTE(ilyaalekseyev): Implementation like in multinics
    # for xenapi(tr3buchet)
    @exception.wrap_exception
    def spawn(self, instance, network_info=None):
        LOG.debug(_("<============= spawn of tilera =============>"))  # MK
        xml_dict = self.to_xml_dict(instance, network_info)
        db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.NOSTATE,
                              'launching')
        #self.firewall_driver.setup_basic_filtering(instance, network_info)
        #self.firewall_driver.prepare_instance_filter(instance, network_info)
        self._create_image(instance, xml_dict, network_info=network_info)
        #domain = self._create_new_domain(xml)
        LOG.debug(_("instance %s: is running"), instance['name'])
        #self.firewall_driver.apply_instance_filter(instance)

        #if FLAGS.start_guests_on_host_boot:
        #    LOG.debug(_("instance %s: setting autostart ON") %
        #              instance['name'])
        #    domain.setAutostart(1)

        def basepath(fname='', suffix=''):
            return os.path.join(FLAGS.instances_path,
                                instance['name'],
                                fname + suffix)
        bpath = basepath(suffix='')
        timer = utils.LoopingCall(f=None)

        def _wait_for_boot():
            try:
                print xml_dict  # MK
                state = self._conn.create_domain(xml_dict, bpath)
                LOG.debug(_('~~~~~~ current state = %s ~~~~~~') % state)  # MK
                db.instance_set_state(context.get_admin_context(),
                                      instance['id'], state, 'running')
                if state == power_state.RUNNING:
                    LOG.debug(_('instance %s: booted'), instance['name'])
                    timer.stop()
            except:
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
        board_ip = tilera_boards.find_ip_w_id(fd['board_id'])

        kmsg_dump_file = "/tftpboot/kmsg_dump_0"  # + str(fd['board_id'])
        size = os.path.getsize(kmsg_dump_file)
        head_cmd = "head -400 /proc/kmsg >> /etc/kmsg_dump"
        if size <= 0:
            utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
                '--resume', '--net', board_ip, \
                '--run', '-', head_cmd, '-', '--wait', \
                '--download', '/etc/kmsg_dump', console_log, '--quit')
                #'--download', '/proc/tile/hvconfig', console_log, '--quit')
            utils.execute('cp', console_log, kmsg_dump_file)
        else:
            utils.execute('cp', kmsg_dump_file, console_log)

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
        raise NotImplementedError()
        """Wrapper for a method that creates an image that caches the image.

        This wrapper will save the image into a common store and create a
        copy for use by the hypervisor.

        The underlying method should specify a kwarg of target representing
        where the image will be saved.

        fname is used as the filename of the base image.  The filename needs
        to be unique to a given image.

        If cow is True, it will make a CoW image instead of a copy.
        """

    def _fetch_image(self, target, image_id, user, project, size=None):
        raise NotImplementedError()

    def _create_local(self, target, local_gb):
        raise NotImplementedError()

    def _create_image(self, inst, tilera_xml, suffix='', disk_images=None,
                        network_info=None):
        if not network_info:
            network_info = _get_network_info(inst)

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
        f = open(basepath('tilera.xml'), 'w')
        #f.write(tilera_xml)
        f.close()

        if FLAGS.tilera_type == 'lxc':
            container_dir = '%s/rootfs' % basepath(suffix='')
            utils.execute('mkdir', '-p', container_dir)

        # NOTE(vish): No need add the suffix to console.log
        os.close(os.open(basepath('console.log', ''),
                         os.O_CREAT | os.O_WRONLY, 0660))

        user = manager.AuthManager().get_user(inst['user_id'])
        project = manager.AuthManager().get_project(inst['project_id'])

        if not disk_images:
            disk_images = {'image_id': inst['image_id'],
                           'kernel_id': inst['kernel_id'],
                           'ramdisk_id': inst['ramdisk_id']}

        #MK
        #Test: copying original tilera images
        board_id = tilera_boards.check_idle_board()
        path_fs = "/tftpboot/tilera_fs_" + str(board_id)
        path_root = basepath(suffix='') + "/root"
        utils.execute('cp', path_fs, path_root)
        kmsg_dump_file = "/tftpboot/kmsg_dump_0"  # + str(board_id)
        utils.execute('touch', kmsg_dump_file)
        #_MK

        # For now, we assume that if we're not using a kernel, we're using a
        # partitioned disk image where the target partition is the first
        # partition
        target_partition = None
        if not inst['kernel_id']:
            target_partition = "1"

        if FLAGS.tilera_type == 'lxc':
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
        admin_context = context.get_admin_context()
        for (network_ref, mapping) in network_info:
            ifc_num += 1

            if not network_ref['injected']:
                continue

            have_injected_networks = True
            address = mapping['ips'][0]['ip']
            address_v6 = None
            if FLAGS.use_ipv6:
                address_v6 = mapping['ip6s'][0]['ip']
            net_info = {'name': 'eth%d' % ifc_num,
                   'address': address,
                   'netmask': network_ref['netmask'],
                   'gateway': network_ref['gateway'],
                   'broadcast': network_ref['broadcast'],
                   'dns': network_ref['dns'],
                   'address_v6': address_v6,
                   'gateway_v6': network_ref['gateway_v6'],
                   'netmask_v6': network_ref['netmask_v6']}
            nets.append(net_info)

        if have_injected_networks:
            net = str(Template(ifc_template,
                               searchList=[{'interfaces': nets,
                                            'use_ipv6': FLAGS.use_ipv6}]))

        if key or net:
            inst_name = inst['name']
            img_id = inst.image_id
            if key:
                LOG.info(_('instance %(inst_name)s: injecting key into'
                        ' image %(img_id)s') % locals())
            if net:
                LOG.info(_('instance %(inst_name)s: injecting net into'
                        ' image %(img_id)s') % locals())
            try:
                #disk.inject_data(basepath('disk'), key, net,
                disk.inject_data(basepath('root'), key, net,
                                 partition=target_partition,
                                 nbd=FLAGS.use_cow_images)

                if FLAGS.tilera_type == 'lxc':
                    disk.setup_container(basepath('disk'),
                                        container_dir=container_dir,
                                        nbd=FLAGS.use_cow_images)
            except Exception as e:
                # This could be a windows image, or a vmdk format disk
                LOG.warn(_('instance %(inst_name)s: ignoring error injecting'
                        ' data into image %(img_id)s (%(e)s)') % locals())

        if FLAGS.tilera_type == 'uml':
            utils.execute('sudo', 'chown', 'root', basepath('disk'))

    def _get_nic_for_xml(self, network, mapping):
        # Assume that the gateway also acts as the dhcp server.
        dhcp_server = network['gateway']
        gateway_v6 = network['gateway_v6']
        mac_id = mapping['mac'].replace(':', '')

        if FLAGS.allow_project_net_traffic:
            template = "<parameter name=\"%s\"value=\"%s\" />\n"
            net, mask = _get_net_and_mask(network['cidr'])
            values = [("PROJNET", net), ("PROJMASK", mask)]
            if FLAGS.use_ipv6:
                net_v6, prefixlen_v6 = _get_net_and_prefixlen(
                                           network['cidr_v6'])
                values.extend([("PROJNETV6", net_v6),
                               ("PROJMASKV6", prefixlen_v6)])

            extra_params = "".join([template % value for value in values])
        else:
            extra_params = "\n"

        result = {
            'id': mac_id,
            'bridge_name': network['bridge'],
            'mac_address': mapping['mac'],
            'ip_address': mapping['ips'][0]['ip'],
            'dhcp_server': dhcp_server,
            'extra_params': extra_params,
        }

        if gateway_v6:
            result['gateway_v6'] = gateway_v6 + "/128"

        return result

    def _prepare_xml_info(self, instance, rescue=False, network_info=None):
        # TODO(adiantum) remove network_info creation code
        # when multinics will be completed
        if not network_info:
            network_info = _get_network_info(instance)

        nics = []
        for (network, mapping) in network_info:
            nics.append(self._get_nic_for_xml(network, mapping))
        # FIXME(vish): stick this in db
        inst_type_id = instance['instance_type_id']
        inst_type = instance_types.get_instance_type(inst_type_id)

        if FLAGS.use_cow_images:
            driver_type = 'qcow2'
        else:
            driver_type = 'raw'

        xml_info = {'type': FLAGS.tilera_type,
                    'name': instance['name'],
                    'basepath': os.path.join(FLAGS.instances_path,
                                             instance['name']),
                    'memory_kb': inst_type['memory_mb'] * 1024,
                    'vcpus': inst_type['vcpus'],
                    'rescue': rescue,
                    'local': inst_type['local_gb'],
                    'driver_type': driver_type,
                    'nics': nics,
                    'ip_address': mapping['ips'][0]['ip'],  # MK
                    'mac_address': instance['mac_address'],  # MK
                    'image_id': instance['image_id'],  # MK
                    'kernel_id': instance['kernel_id'],  # MK
                    'ramdisk_id': instance['ramdisk_id']}  # MK

        if FLAGS.vnc_enabled:
            if FLAGS.tilera_type != 'lxc':
                xml_info['vncserver_host'] = FLAGS.vncserver_host
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
        xml = str(Template(self.tilera_xml, searchList=[xml_info]))
        LOG.debug(_('instance %s: finished toXML method'), instance['name'])
        #return xml
        return xml_info

    def get_info(self, instance_name):
        """Retrieve information from tilera for a specific instance name.

        If a tilera error is encountered during lookup, we might raise a
        NotFound exception or Error exception depending on how severe the
        tilera error is.

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
                                   "for tilera"))

    def get_disks(self, instance_name):
        raise NotImplementedError()
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.

        Returns a list of all block devices for this domain.
        """

    def get_interfaces(self, instance_name):
        raise NotImplementedError()
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.

        Returns a list of all network interfaces for this instance.
        """

    def get_vcpu_total(self):
        """Get vcpu number of physical computer.

        :returns: the number of cpu core.

        """

        # On certain platforms, this will raise a NotImplementedError.
        try:
            #return multiprocessing.cpu_count()
            return tilera_boards.get_tilera_hw_info('vcpus')  # 10
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
        return tilera_boards.get_tilera_hw_info('memory_mb')  # 16218

    def get_local_gb_total(self):
        """Get the total hdd size(GB) of physical computer.

        :returns:
            The total amount of HDD(GB).
            Note that this value shows a partition where
            NOVA-INST-DIR/instances mounts.

        """

        #hddinfo = os.statvfs(FLAGS.instances_path)
        #return hddinfo.f_frsize * hddinfo.f_blocks / 1024 / 1024 / 1024
        return tilera_boards.get_tilera_hw_info('local_gb')  # 917

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
        return tilera_boards.get_tilera_hw_info('memory_mb_used')  # 476

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
        return tilera_boards.get_tilera_hw_info('local_gb_used')  # 1

    def get_hypervisor_type(self):
        """Get hypervisor type.

        :returns: hypervisor type (ex. qemu)

        """

        #return self._conn.getType()
        return tilera_boards.get_tilera_hw_info('hypervisor_type')

    def get_hypervisor_version(self):
        """Get hypervisor version.

        :returns: hypervisor version (ex. 12003)

        """

        # NOTE(justinsb): getVersion moved between tilera versions
        # Trying to do be compatible with older versions is a lost cause
        # But ... we can at least give the user a nice message
        #method = getattr(self._conn, 'getVersion', None)
        #if method is None:
        #    raise exception.Error(_("tilera version is too old"
        #                            " (does not support getVersion)"))
            # NOTE(justinsb): If we wanted to get the version, we could:
            # method = getattr(tilera, 'getVersion', None)
            # NOTE(justinsb): This would then rely on a proper version check

        #return method()
        return tilera_boards.get_tilera_hw_info('hypervisor_version')  # 1

    def get_cpu_info(self):
        """Get cpuinfo information.

        Obtains cpu feature from virConnect.getCapabilities,
        and returns as a json string.

        :return: see above description

        """

        """xml = self._conn.getCapabilities()
        xml = libxml2.parseDoc(xml)
        nodes = xml.xpathEval('//host/cpu')
        if len(nodes) != 1:
            reason = _("'<cpu>' must be 1, but %d\n") % len(nodes)
            reason += xml.serialize()
            raise exception.InvalidCPUInfo(reason=reason)

        cpu_info = dict()

        arch_nodes = xml.xpathEval('//host/cpu/arch')
        if arch_nodes:
            cpu_info['arch'] = arch_nodes[0].getContent()

        model_nodes = xml.xpathEval('//host/cpu/model')
        if model_nodes:
            cpu_info['model'] = model_nodes[0].getContent()

        vendor_nodes = xml.xpathEval('//host/cpu/vendor')
        if vendor_nodes:
            cpu_info['vendor'] = vendor_nodes[0].getContent()

        topology_nodes = xml.xpathEval('//host/cpu/topology')
        topology = dict()
        if topology_nodes:
            topology_node = topology_nodes[0].get_properties()
            while topology_node:
                name = topology_node.get_name()
                topology[name] = topology_node.getContent()
                topology_node = topology_node.get_next()

            keys = ['cores', 'sockets', 'threads']
            tkeys = topology.keys()
            if set(tkeys) != set(keys):
                ks = ', '.join(keys)
                reason = _("topology (%(topology)s) must have %(ks)s")
                raise exception.InvalidCPUInfo(reason=reason % locals())

        feature_nodes = xml.xpathEval('//host/cpu/feature')
        features = list()
        for nodes in feature_nodes:
            features.append(nodes.get_properties().getContent())

        cpu_info['topology'] = topology
        cpu_info['features'] = features
        return utils.dumps(cpu_info)"""
        return tilera_boards.get_tilera_hw_info('cpu_info')  # 'TILEPro64'

    def block_stats(self, instance_name, disk):
        raise NotImplementedError()
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.
        """

    def interface_stats(self, instance_name, interface):
        raise NotImplementedError()
        """
        Note that this function takes an instance name, not an Instance, so
        that it can be called by monitor.
        """

    def get_console_pool_info(self, console_type):
        #TODO(mdragon): console proxy should be implemented for tilera,
        #               in case someone wants to use it with kvm or
        #               such. For now return fake data.
        return  {'address': '127.0.0.1',
                 'username': 'fakeuser',
                 'password': 'fakepassword'}

    def refresh_security_group_rules(self, security_group_id):
        self.firewall_driver.refresh_security_group_rules(security_group_id)

    def refresh_security_group_members(self, security_group_id):
        self.firewall_driver.refresh_security_group_members(security_group_id)

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
               'net_mbps': FLAGS.net_mbps
               }

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
        """Checks the host cpu is compatible to a cpu given by xml.

        "xml" must be a part of tilera.openReadonly().getCapabilities().
        return values follows by virCPUCompareResult.
        if 0 > return value, do live migration.

        :param cpu_info: json string that shows cpu feature(see get_cpu_info())
        :returns:
            None. if given cpu info is not compatible to this server,
            raise exception.

        """

    def ensure_filtering_rules_for_instance(self, instance_ref,
                                            time=None):
        """Setting up filtering rules and waiting for its completion.

        To migrate an instance, filtering rules to hypervisors
        and firewalls are inevitable on destination host.
        ( Waiting only for filterling rules to hypervisor,
        since filtering rules to firewall rules can be set faster).

        Concretely, the below method must be called.
        - setup_basic_filtering (for nova-basic, etc.)
        - prepare_instance_filter(for nova-instance-instance-xxx, etc.)

        to_xml may have to be called since it defines PROJNET, PROJMASK.
        but tilera migrates those value through migrateToURI(),
        so , no need to be called.

        Don't use thread for this method since migration should
        not be started when setting-up filtering rules operations
        are not completed.

        :params instance_ref: nova.db.sqlalchemy.models.Instance object

        """

        if not time:
            time = greenthread

        # If any instances never launch at destination host,
        # basic-filtering must be set here.
        self.firewall_driver.setup_basic_filtering(instance_ref)
        # setting up n)ova-instance-instance-xx mainly.
        self.firewall_driver.prepare_instance_filter(instance_ref)

        # wait for completion
        timeout_count = range(FLAGS.live_migration_retry_count)
        while timeout_count:
            if self.firewall_driver.instance_filter_exists(instance_ref):
                break
            timeout_count.pop()
            if len(timeout_count) == 0:
                msg = _('Timeout migrating for %s. nwfilter not found.')
                raise exception.Error(msg % instance_ref.name)
            time.sleep(1)

    def live_migration(self, ctxt, instance_ref, dest,
                       post_method, recover_method):
        """Spawning live_migration operation for distributing high-load.

        :params ctxt: security context
        :params instance_ref:
            nova.db.sqlalchemy.models.Instance object
            instance object that is migrated.
        :params dest: destination host
        :params post_method:
            post operation method.
            expected nova.compute.manager.post_live_migration.
        :params recover_method:
            recovery method when any exception occurs.
            expected nova.compute.manager.recover_live_migration.

        """

        greenthread.spawn(self._live_migration, ctxt, instance_ref, dest,
                          post_method, recover_method)

    def _live_migration(self, ctxt, instance_ref, dest,
                        post_method, recover_method):
        """Do live migration.

        :params ctxt: security context
        :params instance_ref:
            nova.db.sqlalchemy.models.Instance object
            instance object that is migrated.
        :params dest: destination host
        :params post_method:
            post operation method.
            expected nova.compute.manager.post_live_migration.
        :params recover_method:
            recovery method when any exception occurs.
            expected nova.compute.manager.recover_live_migration.

        """

        # Do live migration.
        try:
            flaglist = FLAGS.live_migration_flag.split(',')
            flagvals = [getattr(tilera, x.strip()) for x in flaglist]
            logical_sum = reduce(lambda x, y: x | y, flagvals)

            if self.read_only:
                tmpconn = self._connect(self.tilera_uri, False)
                dom = tmpconn.lookupByName(instance_ref.name)
                dom.migrateToURI(FLAGS.live_migration_uri % dest,
                                 logical_sum,
                                 None,
                                 FLAGS.live_migration_bandwidth)
                tmpconn.close()
            else:
                dom = self._conn.lookupByName(instance_ref.name)
                dom.migrateToURI(FLAGS.live_migration_uri % dest,
                                 logical_sum,
                                 None,
                                 FLAGS.live_migration_bandwidth)

        except Exception:
            recover_method(ctxt, instance_ref, dest=dest)
            raise

        # Waiting for completion of live_migration.
        timer = utils.LoopingCall(f=None)

        def wait_for_live_migration():
            """waiting for live migration completion"""
            try:
                self.get_info(instance_ref.name)['state']
            except exception.NotFound:
                timer.stop()
                post_method(ctxt, instance_ref, dest)

        timer.f = wait_for_live_migration
        timer.start(interval=0.5, now=True)

    def unfilter_instance(self, instance_ref):
        """See comments of same method in firewall_driver."""
        self.firewall_driver.unfilter_instance(instance_ref)

    def update_host_status(self):
        """Update the status info of the host, and return those values
            to the calling program."""
        return self.HostState.update_status()

    def get_host_stats(self, refresh=False):
        """Return the current state of the host. If 'refresh' is
           True, run the update first."""
        print 'Updating!'
        return self.HostState.get_host_stats(refresh=refresh)
#        """See xenapi_conn.py implementation."""
#        print 'UPDATING!'
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
#        return data


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
        print 'Updating statistics!!'
        connection = get_connection(self.read_only)
        data = {}
        data["vcpus"] = connection.get_vcpu_total()
        data["vcpus_used"] = connection.get_vcpu_used()
        data["cpu_info"] = connection.get_cpu_info()
        data["cpu_arch"] = FLAGS.cpu_arch
        data["xpus"] = FLAGS.xpus
        data["xpu_arch"] = FLAGS.xpu_arch
        data["xpus_used"] = 0  # len(gvirtus_pids)
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

#MK
tilera_boards = _tilera_board()
fake_doms = _fake_dom()
#_MK
