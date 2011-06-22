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

import mox

import pickle
import StringIO
import stubout

from nova import flags
from nova import test
from nova.compute import power_state
from nova.tests import fake_utils

from nova.virt.baremetal import proxy
from nova.virt.baremetal import dom

FLAGS = flags.FLAGS
FLAGS.baremetal_driver = 'fake'


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

        fake_file = StringIO.StringIO()

        def fake_open(filename, mode='r', bufsuze=0):
            return fake_file

        # Stub out the _read_domain_from_file function
        self.mox.StubOutWithMock(dom.BareMetalDom, "_read_domain_from_file")

        # We expect one _read_domain_from_file call
        dom.BareMetalDom._read_domain_from_file(fake_open)

        self.mox.ReplayAll()

        # Instantiate multiple instances
        x = dom.BareMetalDom(open=fake_open)
        x = dom.BareMetalDom(open=fake_open)
        x = dom.BareMetalDom(open=fake_open)

    def test_init_no_domains(self):

        # Create the mock objects
        mock_open = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(pickle, 'load')
        fake_file = StringIO.StringIO()

        # Here's the sequence of events we expect
        mock_open("/tftpboot/test_fake_dom_file", "r+").AndReturn(fake_file)
        pickle.load(fake_file).AndReturn([])
        mock_open("/tftpboot/test_fake_dom_file", "w").AndReturn(fake_file)

        self.mox.ReplayAll()

        # Code under test
        bmdom = dom.BareMetalDom(open=mock_open)

        self.assertEqual(bmdom.fake_dom_nums, 0)

    def test_init_no_file(self):

        # Create the mock objects
        mock_open = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(pickle, 'load')
        fake_file = StringIO.StringIO()

        # Here's the sequence of events we expect
        mock_open("/tftpboot/test_fake_dom_file", "r+").AndRaise(\
            IOError("file not found"))
        mock_open("/tftpboot/test_fake_dom_file", "w").AndReturn(fake_file)
        mock_open("/tftpboot/test_fake_dom_file", "r+").AndReturn(fake_file)

        pickle.load(fake_file).AndReturn([])
        mock_open("/tftpboot/test_fake_dom_file", "w").AndReturn(fake_file)

        self.mox.ReplayAll()

        # Code under test
        bmdom = dom.BareMetalDom(open=mock_open)

        self.assertEqual(bmdom.fake_dom_nums, 0)

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


class ProxyBareMetalTestCase(test.TestCase):
    pass
