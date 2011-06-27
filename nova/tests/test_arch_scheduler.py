# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 University of Southern California
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
Tests for architecture-aware scheduler
"""

import mox
import random
from nova import context
from nova import db
from nova import exception
from nova import test
from nova import rpc
from nova.scheduler import manager

instance_type = dict()

class ArchSchedulerTestCase(test.TestCase):
    """Test case for Archscheduler"""
    def setUp(self):
        super(ArchSchedulerTestCase, self).setUp()
        driver = 'nova.scheduler.hetero.HeterogeneousScheduler'
        self.context = context.get_admin_context()
        self.flags(scheduler_driver = driver)
        self.inst_1 = self._create_instance()
        values = dict(name="cg1.4xlarge",
                      memory_mb=22000,
                      vcpus=8,
                      local_gb=1690,
                      flavorid=105)
        specs = dict(cpu_arch="x86_64",
                        cpu_model="Nehalem",
                        xpu_arch="fermi",
                        xpus=2,
                        xpu_model="Tesla 2050")
        values['extra_specs'] = specs
        ref = db.api.instance_type_create(self.context,
                                          values)
        self.instance_type_id = ref.id
        


    def tearDown(self):
        db.instance_destroy(self.context,self.inst_1)  
        super(ArchSchedulerTestCase, self).tearDown()

    def _create_instance(self, **kwargs):
        """Create a test instance"""
        inst = {}
        inst['user_id'] = 'admin'
        inst['project_id'] = kwargs.get('project_id', 'fake')
        inst['vcpus'] = kwargs.get('vcpus', 1)
        inst['memory_mb'] = kwargs.get('memory_mb', 10)
        inst['local_gb'] = kwargs.get('local_gb', 2)
        inst['flavorid'] = kwargs.get('flavorid', 999)
        inst['extra_specs'] = specs
        ref = db.api.instance_type_create(self.context,
                                          inst)
        inst['instance_type_id'] = kwargs.get('inst_type_id', ref.id)
        return db.instance_create(self.context, inst)['id']

    def test_archschedule_no_hosts(self):
        scheduler = manager.SchedulerManager()  
        host = scheduler.schedule(self.context,
                                  topic = 'compute',
                                  instance_id = self.inst_1)
    
    def test_archschedule_one_host_no_match_cap(self):
        scheduler = manager.SchedulerManager()  
        dict1 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_info': '{"vendor": "Intel", "model": "Nehalem", \
               "arch": "x86_64", "features": ["rdtscp", "dca", "xtpr", "tm2",\
               "est", "vmx", "ds_cpl", "monitor", "pbe", "tm", "ht", "ss", \
               "acpi", "ds", "vme"], "topology": {"cores": "4", "threads": "1",\
               "sockets": "2"}}', 'cpu_arch': 'x86_64', 'xpus_used': 1,
               'xpu_arch': '', 'xpus': 1, 'xpu_model': "Tesla S2050"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           dict1)
        host = scheduler.run_instance(self.context,
                                               topic = 'compute',
                                               instance_id = self.inst_1,
                                               request_spec={'instance_type': })
    
    def test_archschedule_one_host_match_cap(self):
        scheduler = manager.SchedulerManager()  
        dict1 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_info': '{"vendor": "Intel", "model": "Nehalem", \
               "arch": "x86_64", "features": ["rdtscp", "dca", "xtpr", "tm2",\
               "est", "vmx", "ds_cpl", "monitor", "pbe", "tm", "ht", "ss", \
               "acpi", "ds", "vme"], "topology": {"cores": "4", "threads": "1",\
               "sockets": "2"}}', 'cpu_arch': 'x86_64', 'xpus_used': 1,
               'xpu_arch': 'fermi', 'xpus': 1, 'xpu_model': "Tesla S2050"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           dict1)
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything = True)
        rpc.cast(self.context,
                 'compute.host1',
                 {'method': 'run',
                  'args': {'instance_id': self.inst_1}})
        self.mox.ReplayAll()
        host = scheduler.run(self.context,
                           topic = 'compute',
                           instance_id = self.inst_1)
    
    def test_archschedule_two_host_one_match_cap(self):
        scheduler = manager.SchedulerManager()  
        dict1 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_info': '{"vendor": "Intel", "model": "Nehalem", \
               "arch": "x86_64", "features": ["rdtscp", "dca", "xtpr", "tm2",\
               "est", "vmx", "ds_cpl", "monitor", "pbe", "tm", "ht", "ss", \
               "acpi", "ds", "vme"], "topology": {"cores": "4", "threads": "1",\
               "sockets": "2"}}', 'cpu_arch': 'x86_64', 'xpus_used': 1,
               'xpu_arch': 'fermi', 'xpus': 1, 'xpu_model': ""}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           dict1)
        dict2 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_info': '{"vendor": "Intel", "model": "Nehalem", \
               "arch": "x86_64", "features": ["rdtscp", "dca", "xtpr", "tm2",\
               "est", "vmx", "ds_cpl", "monitor", "pbe", "tm", "ht", "ss", \
               "acpi", "ds", "vme"], "topology": {"cores": "4", "threads": "1",\
               "sockets": "2"}}', 'cpu_arch': 'x86_64', 'xpus_used': 1,
               'xpu_arch': 'fermi', 'xpus': 1, 'xpu_model': "Tesla S2050"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host2",
                                                           dict2)
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything = True)
        rpc.cast(self.context,
                 'compute.host2',
                 {'method': 'run',
                  'args': {'instance_id': self.inst_1}})
        self.mox.ReplayAll()
        host = scheduler.run(self.context,
                             topic = 'compute',
                             instance_id = self.inst_1)
    
    def test_archschedule_two_host_two_match_cap(self):
        scheduler = manager.SchedulerManager()  
        dict1 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_info': '{"vendor": "Intel", "model": "Nehalem", \
               "arch": "x86_64", "features": ["rdtscp", "dca", "xtpr", "tm2",\
               "est", "vmx", "ds_cpl", "monitor", "pbe", "tm", "ht", "ss", \
               "acpi", "ds", "vme"], "topology": {"cores": "4", "threads": "1",\
               "sockets": "2"}}', 'cpu_arch': 'x86_64', 'xpus_used': 1,
               'xpu_arch': 'fermi', 'xpus': 1, 'xpu_model': "Tesla S2050"}
        dict2 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_info': '{"vendor": "Intel", "model": "Nehalem", \
               "arch": "x86_64", "features": ["rdtscp", "dca", "xtpr", "tm2",\
               "est", "vmx", "ds_cpl", "monitor", "pbe", "tm", "ht", "ss", \
               "acpi", "ds", "vme"], "topology": {"cores": "4", "threads": "1",\
               "sockets": "2"}}', 'cpu_arch': 'x86_64', 'xpus_used': 1,
               'xpu_arch': 'fermi', 'xpus': 1, 'xpu_model': "Tesla S2050"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           dict1)
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host2",
                                                           dict2)
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything = True)
        self.mox.StubOutWithMock(random, 'random', use_mock_anything = True)
        random.random().AndReturn(0)
        rpc.cast(self.context,
                 'compute.host2',
                 {'method': 'run',
                  'args': {'instance_id': self.inst_1}})
        self.mox.ReplayAll()
        host = scheduler.run(self.context,
                           topic = 'compute',
                           instance_id = self.inst_1)
