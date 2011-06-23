# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 University of Southern California
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

import __builtin__

import mox

import pickle
import StringIO
import stubout

from nova import flags
from nova import test
from nova.compute import power_state
from nova import context
from nova import db
from nova.tests import fake_utils

from nova.virt.baremetal import proxy
from nova.virt.baremetal import dom

FLAGS = flags.FLAGS
FLAGS.baremetal_driver = 'fake'



fake_domains = [{'status': 1, 'name': 'instance-00000001', 
                 'memory_kb': 16777216, 'kernel_id': '1896115634', 
                 'ramdisk_id': '', 'image_id': '1552326678', 
                 'vcpus': 1, 'node_id': 6, 
                 'mac_address': '02:16:3e:01:4e:c9', 
                 'ip_address': '10.5.1.2'}]



class BareMetalDomTestCase(test.TestCase):
    def setUp(self):
        super(BareMetalDomTestCase, self).setUp()
        # Stub out utils.execute
        self.stubs = stubout.StubOutForTesting()
        fake_utils.stub_out_utils_execute(self.stubs)

    def tearDown(self):
        self.stubs.UnsetAll()
        super(BareMetalDomTestCase, self).tearDown()

        # Reset the singleton state
        dom.BareMetalDom._instance = None
        dom.BareMetalDom._is_init = False

    def test_read_domain_only_once(self):
        """Confirm that the domain is read from a file only once,
        even if the object is instantiated multiple times"""
        try:
            self.mox.StubOutWithMock(__builtin__, 'open')
            self.mox.StubOutWithMock(dom.BareMetalDom, "_read_domain_from_file")

            # We expect one _read_domain_from_file call
            open('/tftpboot/test_fake_dom_file', 'r+')
            dom.BareMetalDom._read_domain_from_file()


            self.mox.ReplayAll()

            # Instantiate multiple instances
            x = dom.BareMetalDom()
            x = dom.BareMetalDom()
            x = dom.BareMetalDom()
        finally:
            self.mox.UnsetStubs()            
            

    def test_init_no_domains(self):

        # Create the mock objects
        try:
            self.mox.StubOutWithMock(__builtin__, 'open')
            fake_file = StringIO.StringIO()
            
            # Here's the sequence of events we expect
            open('/tftpboot/test_fake_dom_file', 'r+').AndReturn(fake_file)
            open('/tftpboot/test_fake_dom_file', 'w')

            self.mox.ReplayAll()
            
            # Code under test
            bmdom = dom.BareMetalDom()
            
            self.assertEqual(bmdom.fake_dom_nums, 0)
        finally:
            self.mox.UnsetStubs()


    def test_init_remove_non_running_domain(self):

        fake_file = StringIO.StringIO()

        domains = [dict(node_id=1, status=power_state.NOSTATE),
                   dict(node_id=2, status=power_state.RUNNING),
                   dict(node_id=3, status=power_state.BLOCKED),
                   dict(node_id=4, status=power_state.PAUSED),
                   dict(node_id=5, status=power_state.SHUTDOWN),
                   dict(node_id=6, status=power_state.SHUTOFF),
                   dict(node_id=7, status=power_state.CRASHED),
                   dict(node_id=8, status=power_state.SUSPENDED),
                   dict(node_id=9, status=power_state.FAILED),
                   dict(node_id=10, status=power_state.BUILDING)]

        # Here we use a fake open function instead of a mock because we
        # aren't testing explicitly for open being called
        def fake_open(filename, mode='r', bufsuze=0):
            return fake_file

        pickle.dump(domains, fake_file)

        self.mox.StubOutWithMock(pickle, 'load')
        pickle.load(fake_file).AndReturn(domains)
        self.mox.ReplayAll()

        bmdom = dom.BareMetalDom(open=fake_open)
        self.assertEqual(bmdom.domains, [{'node_id': 2,
                                          'status': power_state.RUNNING}])
        self.assertEqual(bmdom.fake_dom_nums, 1)
        
    def test_find_domain(self):
        domain = {'status': 1, 'name': 'instance-00000001', 
                    'memory_kb': 16777216, 'kernel_id': '1896115634', 
                    'ramdisk_id': '', 'image_id': '1552326678', 
                    'vcpus': 1, 'node_id': 6, 
                    'mac_address': '02:16:3e:01:4e:c9', 
                    'ip_address': '10.5.1.2'}
        
        def fake_open(filename, mode='r', bufsuze=0):
            return StringIO.StringIO(pickle.dumps(fake_domains))

        bmdom = dom.BareMetalDom(open=fake_open)

        self.assertEquals(bmdom.find_domain('instance-00000001'), domain)
        


class ProxyBareMetalTestCase(test.TestCase):
    
    test_ip = '10.11.12.13'
    test_instance = {'memory_kb':     '1024000',
                     'basepath':      '/some/path',
                     'bridge_name':   'br100',
                     'mac_address':   '02:12:34:46:56:67',
                     'vcpus':         2,
                     'project_id':    'fake',
                     'bridge':        'br101',
                     'image_ref':     '123456',
                     'instance_type_id': '5'}  # m1.small
                     
    def setUp(self):
        super(ProxyBareMetalTestCase, self).setUp()        
        self.context = context.get_admin_context()
        fake_utils.stub_out_utils_execute(self.stubs)
        
    def test_get_info(self):
        baremetal_xml_template = open(FLAGS.baremetal_xml_template)
        try:
            self.mox.StubOutWithMock(__builtin__, 'open')
            open(mox.StrContains('baremetal.xml.template')).AndReturn(baremetal_xml_template)
            open('/tftpboot/test_fake_dom_file', 'r+').AndReturn(StringIO.StringIO(pickle.dumps(fake_domains)))
            open('/tftpboot/test_fake_dom_file', 'w')            
            self.mox.ReplayAll()

            conn = proxy.get_connection(True)
            info = conn.get_info('instance-00000001')

            self.assertEquals(info['mem'], 16777216)
            self.assertEquals(info['state'], 1)
            self.assertEquals(info['num_cpu'], 1)
            self.assertEquals(info['cpu_time'], 100)
            self.assertEquals(info['max_mem'], 16777216)
            
        finally:
            self.mox.UnsetStubs()            

                     
    
   ### def test_init_host(self):
   ### # Upon init, should set the state of the running instances
   ###
   ### # Need to populate the database here
   ###     instance_ref = db.instance_create(self.context, self.test_instance)        
   ###
   ###     conn = proxy.get_connection(True)
   ###     conn.init_host(host=???)
   ###     
    
