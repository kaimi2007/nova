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
#from nova.virt.baremetal import tilera
from nova.virt.baremetal import nodes

FLAGS = flags.FLAGS

LOG = logging.getLogger('nova.virt.baremetal.dom')


class BareMetalDom(object):
    """Fake domain for bare metal back ends.
    Implements the singleton pattern"""

    _instance = None
    _is_init = False

    def __new__(cls, *args, **kwargs):
        """Returns the BareMetalDom singleton"""
        if not cls._instance or ('new' in kwargs and kwargs['new']):
            cls._instance = super(BareMetalDom, cls).__new__(cls)
        return cls._instance

    def __init__(self,
                 fake_dom_file="/tftpboot/test_fake_dom_file"):
        # Only call __init__ the first time object is instantiated
        if self._is_init:
            return
        self._is_init = True

        self.fake_dom_file = fake_dom_file
        self.domains = []
        self.fake_dom_nums = 0
        self.fp = 0
        self.baremetal_nodes = nodes.get_baremetal_nodes()

        utils.execute('rm', self.fake_dom_file)
        LOG.debug(_("open %s"), self.fake_dom_file)
        try:
            self.fp = open(self.fake_dom_file, "r+")
            LOG.debug(_("fp = %s"), self.fp)
        except IOError:
            LOG.debug(_("%s file does not exist, will create it"),
                      self.fake_dom_file)
            self.fp = open(self.fake_dom_file, "w")
            self.fp.close()
            self.fp = open(self.fake_dom_file, "r+")
        self._read_domain_from_file()
        # (TODO) read pre-existing fake domains

    def _read_domain_from_file(self):
        """
        Read the domains from a pickled representation.
        """
        try:
            self.domains = pickle.load(self.fp)
            self.fp.close()
            self.fp = open(self.fake_dom_file, "w")
        except EOFError:
            dom = []
            self.fp.close()
            self.fp = open(self.fake_dom_file, "w")
            LOG.debug(_("No domains exist."))
            return
        LOG.debug(_("============= initial domains ==========="))
        LOG.debug(_("%s"), self.domains)
        LOG.debug(_("========================================="))
        for dom in self.domains[:]:
            if dom['status'] != power_state.RUNNING:
                LOG.debug(_("Not running domain: remove"))
                self.domains.remove(dom)
                continue
            res = self.baremetal_nodes.set_status(dom['node_id'], \
                                    dom['status'])
            if res > 0:  # no such node exixts
                self.fake_dom_nums = self.fake_dom_nums + 1
            else:
                LOG.debug(_("domain running on an unknown node: discarded"))
                self.domains.remove(dom)
                continue

        LOG.debug(_("--> domains after reading"))
        LOG.debug(_(self.domains))

    def reboot_domain(self, name):
        fd = self.find_domain(name)
        if fd == []:
            raise exception.NotFound("No such domain (%s)" % name)
        node_ip = self.baremetal_nodes.find_ip_w_id(fd['node_id'])

        try:
            self.baremetal_nodes.deactivate_node(fd['node_id'])
        except:
            raise exception.NotFound("Failed power down \
                                      Bare-metal node %s" % fd['node_id'])
        self.change_domain_state(name, power_state.BUILDING)  # NOSTATE)
        try:
            state = self.baremetal_nodes.activate_node(fd['node_id'], \
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
            LOG.debug(_("destroy_domain: no such domain"))
            raise exception.NotFound("No such domain %s" % name)

        try:
            self.baremetal_nodes.deactivate_node(fd['node_id'])
            LOG.debug(_("--> after deactivate node"))

            self.baremetal_nodes.delete_kmsg(fd['node_id'])
            self.domains.remove(fd)
            LOG.debug(_("domains: "))
            LOG.debug(_(self.domains))
            LOG.debug(_("nodes: "))
            LOG.debug(_(self.baremetal_nodes.nodes))
            self.store_domain()
            LOG.debug(_("after storing domains"))
            LOG.debug(_(self.domains))
        except:
            LOG.debug(_("what to do?"))
            raise

    def create_domain(self, xml_dict, bpath):
        """add a domain to domains list
           and activate a idle Bare-metal node"""
        LOG.debug(_("1////////////////////"))
        fd = self.find_domain(xml_dict['name'])
        if fd != []:
            LOG.debug(_("domain with the same name already exists"))
            raise
            #raise exception.NotFound("same name already exists")
        LOG.debug(_("create_domain: before get_idle_node"))

        node_id = self.baremetal_nodes.get_idle_node()
        if node_id == -1:
            LOG.debug(_("No idle bare-metal node exits"))
            raise exception.NotFound("No free nodes available")

        self.baremetal_nodes.init_kmsg(node_id)
        node_ip = self.baremetal_nodes.find_ip_w_id(node_id)

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
                     'status': power_state.BUILDING}  # NOSTATE}
        self.domains.append(new_dom)
        LOG.debug(_(new_dom))
        self.change_domain_state(new_dom['name'], power_state.BUILDING)

        self.baremetal_nodes.set_image(bpath, node_id)

        try:
            state = self.baremetal_nodes.activate_node(node_id,
                node_ip, new_dom['name'], new_dom['mac_address'], \
                new_dom['ip_address'])
                #node_ip, new_dom['name'], new_dom['mac_address']) #MK
        except:
            self.domains.remove(new_dom)
            self.baremetal_nodes.free_node(node_id)
            raise exception.NotFound("Failed to boot Bare-metal node %s" \
                % node_id)

        LOG.debug(_("BEFORE last self.change_domain_state +++++++++++++++++"))
        self.change_domain_state(new_dom['name'], state)
        return state

    def change_domain_state(self, name, state):
        l = self.find_domain(name)
        if l == []:
            raise exception.NotFound("No such domain exists")
        i = self.domains.index(l)
        self.domains[i]['status'] = state
        LOG.debug(_("change_domain_state: to new state %s"), str(state))
        self.store_domain()

    def store_domain(self):
        # store fake domains to the file
        LOG.debug(_("store fake domains to the file"))
        LOG.debug(_("-------"))
        LOG.debug(_(self.domains))
        LOG.debug(_("-------"))
        LOG.debug(_(self.fp))
        self.fp.seek(0)
        pickle.dump(self.domains, self.fp)
        LOG.debug(_("after successful pickle.dump"))

    def find_domain(self, name):
        #LOG.debug(_("find_domain: self.domains %s"), name)
        #LOG.debug(_(self.domains))
        for item in self.domains:
            if item['name'] == name:
                return item
        LOG.debug(_("domain does not exist"))
        return []

    def list_domains(self):
        if self.domains == []:
            return []
        return [x['name'] for x in self.domains]

    def get_domain_info(self, instance_name):
        domain = self.find_domain(instance_name)
        if domain != []:
            return [domain['status'], domain['memory_kb'], \
                    domain['memory_kb'], \
                    domain['vcpus'], \
                    100]
        else:
            return [power_state.NOSTATE, '', '', '', '']
            #raise exception.NotFound("get_domain_info: No such doamin %s" \
            #                          % instance_name)
