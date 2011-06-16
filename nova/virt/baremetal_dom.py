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

FLAGS = flags.FLAGS
if FLAGS.baremetal_driver == 'tilera':
    from nova.virt.tilera import *
#    __all__ = ['baremetal_nodes', 'baremetal_dom']
#global baremetal_nodes

LOG = logging.getLogger('nova.virt.baremetal_dom')


class _baremetal_dom(object):
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
            res = baremetal_nodes.set_status(dom['node_id'], \
                                    dom['status'])
            if res > 0:  # no such node exixts
                self.fake_dom_nums = self.fake_dom_nums + 1
            else:
                print "domain running on an unknown node: discarded"
                self.domains.remove(dom)
                continue

        print "--> domains after reading"
        print self.domains

    def reboot_domain(self, name):
        fd = self.find_domain(name)
        if fd == []:
            raise exception.NotFound("No such domain (%s)" % name)
        node_ip = baremetal_nodes.find_ip_w_id(fd['node_id'])

        try:
            baremetal_nodes.deactivate_node(fd['node_id'])
        except:
            raise exception.NotFound("Failed power down \
                                      Bare-metal node %s" % fd['node_id'])
        self.change_domain_state(name, power_state.NOSTATE)
        try:
            state = baremetal_nodes.activate_node(fd['node_id'], \
                node_ip, name, fd['mac_address'], fd['ip_address'])
                #node_ip, name, fd['mac_address']) #MK
                #fd['ip_addr'], name)
            self.change_domain_state(name, state)
            return state
        except:
            LOG.debug(_("deactivate -> activate fails"))
            self.destroy_domain(name)
            raise

    def destroy_domain(self, name):
        """remove name instance from domains list
           and power down the corresponding bare-metal node"""
        fd = self.find_domain(name)
        if fd == []:
            print "destroy_domain: no such domain"
            raise exception.NotFound("No such domain %s" % name)

        try:
            baremetal_nodes.deactivate_node(fd['node_id'])
            print "--> after deactivate node"

            kmsg_dump_file = "/tftpboot/kmsg_dump_0"  # + str(fd['node_id'])
            utils.execute('rm', kmsg_dump_file)
            self.domains.remove(fd)
            print "domains: "
            print self.domains
            print "nodes: "
            print baremetal_nodes.nodes
            self.store_domain()
            print "after storing domains"
            print self.domains
        except:
            print "what to do?"
            raise

    def create_domain(self, xml_dict, bpath):
        """add a domain to domains list
           and activate a idle Bare-metal node"""
        LOG.debug(_("1////////////////////"))
        fd = self.find_domain(xml_dict['name'])
        if fd != []:
            print 'domain with the same name already exists'
            raise
            #raise exception.NotFound("same name already exists")
        print "create_domain: before get_idle_node"

        node_id = baremetal_nodes.get_idle_node()
        if node_id == -1:
            print ('No idle bare-metal node exits')
            raise exception.NotFound("No free nodes available")

        node_ip = baremetal_nodes.find_ip_w_id(node_id)

        new_dom = {'node_id': node_id,
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
            + str(node_id)
        print cmd
        path1 = bpath + "/root"
        path2 = "/tftpboot/fs_" + str(node_id)
        utils.execute('mount', '-o', 'loop', path1, path2)
        cmd = "cd /tftpboot/fs_" + str(node_id) + \
            "; tar -czpf ../tilera_fs_" + str(node_id) + ".tar.gz ."
        print cmd
        path1 = "/tftpboot/fs_" + str(node_id)
        os.chdir(path1)
        path2 = "../tilera_fs_" + str(node_id) + ".tar.gz"
        utils.execute('tar', '-czpf', path2, '.')
        path1 = bpath + "/../../.."
        os.chdir(path1)
        cmd = "umount -l /tftpboot/fs_" + str(node_id)
        print cmd
        path4 = "/tftpboot/fs_" + str(node_id)
        utils.execute('umount', '-l', path4)

        try:
            state = baremetal_nodes.activate_node(node_id,
                node_ip, new_dom['name'], new_dom['mac_address'], \
                new_dom['ip_address'])
                #node_ip, new_dom['name'], new_dom['mac_address']) #MK
        except:
            self.domains.remove(new_dom)
            baremetal_nodes.free_node(node_id)
            raise exception.NotFound("Failed to boot Bare-metal node %s" \
                % node_id)

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

baremetal_dom = _baremetal_dom()
#_MK
