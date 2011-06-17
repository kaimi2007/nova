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

LOG = logging.getLogger('nova.virt.tilera')


class _baremetal_nodes(object):
    """Manages node information"""
    file_name = "/tftpboot/tilera_boards"
    nodes = []
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
            l_d = {'node_id': int(l[self.BOARD_ID]),
                    'ip_addr': l[self.IP_ADDR],
                    'mac_addr': l[self.MAC_ADDR],
                    'status': power_state.NOSTATE,
                    'vcpus': int(l[self.VCPUS]),
                    'memory_mb': int(l[self.MEMORY_MB]),
                    'local_gb': int(l[self.LOCAL_GB]),
                    'memory_mb_used': int(l[self.MEMORY_MB_USED]),
                    'local_gb_used': int(l[self.LOCAL_GB_USED]),
                    'hypervisor_type': l[self.HYPERVISOR_TYPE],
                    'hypervisor_version': int(l[self.HYPERVISOR_VER]),
                    'cpu_info': l[self.CPU_INFO]
                  }
            self.nodes.append(l_d)
        #print self.nodes

    def get_hw_info(self, field):
        for node in self.nodes:
            if node['node_id'] == 9:
                if field == 'vcpus':
                    return node['vcpus']
                elif field == 'memory_mb':
                    return node['memory_mb']
                elif field == 'local_gb':
                    return node['local_gb']
                elif field == 'memory_mb_used':
                    return node['memory_mb_used']
                elif field == 'local_gb_used':
                    return node['local_gb_used']
                elif field == 'hypervisor_type':
                    return node['hypervisor_type']
                elif field == 'hypervisor_version':
                    return node['hypervisor_version']
                elif field == 'cpu_info':
                    return node['cpu_info']

    def set_status(self, node_id, status):
        for node in self.nodes:
            if node['node_id'] == node_id:
                node['node_id'] = status
                return 1
        return 0

    def check_idle_node(self):
        """check an idle node"""
        for item in self.nodes:

            if item['status'] == 0:
                return item['node_id']
        return -1

    def get_status(self):
        return

    def get_idle_node(self):
        """get an idle node"""
        for item in self.nodes:
            if item['status'] == 0:
                item['status'] = 1      # make status RUNNING
                return item['node_id']
        return -1

    def find_ip_w_id(self, id):
        for item in self.nodes:
            if item['node_id'] == id:
                return item['ip_addr']

    def free_node(self, node_id):
        print("free_node....\n")
        for item in self.nodes:
            if item['node_id'] == str(node_id):
                item['status'] = 0  # make status IDLE
                return
        return -1

    #PDU mode: 1-ON, 2-OFF, 3-REBOOT
    def power_mgr(self, node_id, mode):
        if node_id < 5:
            pdu_num = 1
            pdu_outlet_num = node_id + 5
        else:
            pdu_num = 2
            pdu_outlet_num = node_id
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num), \
            str(mode), '>>', 'pdu_output')
        return

    def deactivate_node(self, node_id):
        node_ip = baremetal_nodes.find_ip_w_id(node_id)
        print("deactivate_node is called for \
               node_id = %s node_ip = %s\n", str(node_id), node_ip)
        for item in self.nodes:
            if item['node_id'] == node_id:
                print "status of node is set to 0"
                item['status'] = 0

        baremetal_nodes.power_mgr(node_id, 2)
        return []

    def network_set(self, node_ip, mac_address, ip_address):
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', node_ip, '--run', '-', \
            'ifconfig', 'xgbe0', 'hw', 'ether', mac_address, '-', \
            '--wait', '--run', '-', 'ifconfig', 'xgbe0', ip_address, \
            '-', '--wait', '--quit')
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', node_ip, '--run', '-', \
            'iptables', '-A', 'INPUT', '-p', 'tcp', '!', '-s', \
            '10.0.11.1', '--dport', '963', '-j', 'DROP', '-', '--wait', \
            #'--run', '-', 'rm', '-rf', '/usr/sbin/iptables*', \
            #'-', '--wait', \
            '--quit')
        return

    def check_activated(self, node_id, node_ip):
        #cmd = "/usr/local/TileraMDE/bin/tile-monitor --resume --net "
        # + node_ip + " --run - /usr/sbin/sshd - --wait -- ls
        #| grep bin >> tile_output"
        #utils.execute('/usr/local/TileraMDE/bin/tile-monitor',
        #'--resume', '--net', node_ip, '--run', '-', '/usr/sbin/sshd', \
        #'-', '--wait', '--', 'ls', '|', 'grep', 'bin', \
        #'>>', 'tile_output')
        #file = open("./tile_output")
        #out_msg = file.readline()
        #print "tile_output: " + out_msg
        #utils.execute('rm', './tile_output')
        #file.close()
        #if out_msg.find("bin") < 0:
        #    cmd = "TILERA_BOARD_#" + str(node_id) + " " \
        #+ node_ip + " is not ready, out_msg=" + out_msg
        #    print cmd
        #    return power_state.NOSTATE
        #else:
        cmd = "TILERA_BOARD_#" + str(node_id) + " " + node_ip \
            + " is ready"
        print cmd
        return

    #vmlinux mode: 0-NoSet, 1-FirstVmlinux, 2-SecondVmlinux, 9-RemoveVmlinux
    def vmlinux_set(self, mode, node_id):
        if mode == 1:
            path1 = "/tftpboot/vmlinux_" + str(node_id) + "_1"
            path2 = "/tftpboot/vmlinux_" + str(node_id)
            utils.execute('cp', path1, path2)
        elif mode == 2:
            path1 = "/tftpboot/vmlinux_" + str(node_id) + "_2"
            path2 = "/tftpboot/vmlinux_" + str(node_id)
            utils.execute('cp', path1, path2)
        elif mode == 9:
            path1 = "/tftpboot/vmlinux_" + str(node_id)
            utils.execute('rm', path1)
        else:
            cmd = "Noting to do"
            print cmd
        return

    def sleep_mgr(self, time):
        utils.execute('sleep', time)
        return

    def ssh_set(self, node_ip):
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', node_ip, '--run', '-', \
            '/usr/sbin/sshd', '-', '--wait', '--quit')
        return

    def fs_set(self, node_id, node_ip):
        path1 = "/tftpboot/tilera_fs_" + str(node_id) + ".tar.gz"
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', node_ip, '--upload', path1, \
            '/tilera_fs.tar.gz', '--quit')
        utils.execute('rm', path1)
        utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
            '--resume', '--net', node_ip, '--run', '-', 'mount', \
            '/dev/sda1', '/mnt', '-', '--wait', '--run', '-', 'rm', \
            '-rf', '/mnt/*', '-', '--wait', \
            #'-rf', '/mnt/root/.ssh/authorized_keys', '-', '--wait', \
            '--run', '-', 'tar', \
            '-xzpf', '/tilera_fs.tar.gz', '-C', '/mnt/', '-', \
            '--wait', '--quit')
        return

    #def activate_node(self, node_id, node_ip, name, mac_address):
    def activate_node(self, node_id, node_ip, name, mac_address, \
        ip_address):
        print("activate_node \n")

        #target = os.path.join(FLAGS.instances_path, name)
        #print target

        baremetal_nodes.vmlinux_set(1, node_id)
        baremetal_nodes.power_mgr(node_id, 3)
        baremetal_nodes.sleep_mgr(60)

        baremetal_nodes.fs_set(node_id, node_ip)
        baremetal_nodes.vmlinux_set(2, node_id)
        baremetal_nodes.power_mgr(node_id, 3)
        baremetal_nodes.sleep_mgr(80)

        baremetal_nodes.check_activated(node_id, node_ip)
        baremetal_nodes.ssh_set(node_ip)
        baremetal_nodes.vmlinux_set(9, node_id)
        baremetal_nodes.network_set(node_ip, mac_address, ip_address)

        return power_state.RUNNING

    def get_console_output(self, console_log):
        kmsg_dump_file = "/tftpboot/kmsg_dump_0"  # + str(fd['node_id'])
        size = os.path.getsize(kmsg_dump_file)
        head_cmd = "head -400 /proc/kmsg >> /etc/kmsg_dump"
        if size <= 0:
            utils.execute('/usr/local/TileraMDE/bin/tile-monitor', \
                '--resume', '--net', node_ip, \
                '--run', '-', head_cmd, '-', '--wait', \
                '--download', '/etc/kmsg_dump', console_log, '--quit')
                #'--download', '/proc/tile/hvconfig', console_log, '--quit')
            utils.execute('cp', console_log, kmsg_dump_file)
        else:
            utils.execute('cp', kmsg_dump_file, console_log)

    def get_image(self, bp):
        node_id = baremetal_nodes.check_idle_node()
        path_fs = "/tftpboot/tilera_fs_" + str(node_id)
        path_root = bp + "/root"
        utils.execute('cp', path_fs, path_root)

    def init_kmsg(self):
        kmsg_dump_file = "kmsg_dump_0"  # + str(node_id)
        utils.execute('touch', kmsg_dump_file)

baremetal_nodes = _baremetal_nodes()
#_MK
