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
from nova import compute
from nova import context
from nova import db
from nova import exception
from nova import test
from nova import rpc
from nova.compute import api as compute_api
from nova.scheduler import driver
from nova.scheduler import manager


class HeteroSchedulerTestCase(test.TestCase):
    """Test case for heterogeneous scheduler"""

    def setUp(self):
        super(HeteroSchedulerTestCase, self).setUp()
        driver = 'nova.scheduler.host_filter.HostFilterScheduler'
        self.context = context.get_admin_context()
        self.flags(scheduler_driver=driver)
        self.filter_name = 'nova.scheduler.host_filter.InstanceTypeFilter'
        specs = dict(cpu_arch="x86_64",
                     xpu_arch="fermi",
                     xpu_model="Tesla S2050")
        self.instance_type = dict(vcpus=1,
                                  memory_mb=10,
                                  local_gb=2,
                                  flavorid=999,
                                  extra_specs=specs)
        ref = db.instance_type_create(self.context, self.instance_type)
        self.instance = dict(user_id='admin',
                             project_id='fake',
                             vcpus=1,
                             memory_mb=10,
                             local_gb=2,
                             instance_type_id=ref.id)
        instance = dict(user_id='admin',
                        project_id='fake',
                        vcpus=1,
                        memory_mb=10,
                        local_gb=2,
                        instance_type_id=ref.id)
        self.inst_ref = db.instance_create(self.context, instance)

    def tearDown(self):
        super(HeteroSchedulerTestCase, self).tearDown()

    def test_no_hosts(self):
        scheduler = manager.SchedulerManager()
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything=True)
        self.mox.ReplayAll()
        self.assertRaises(driver.NoValidHost,
                          scheduler.run_instance,
                          context=self.context,
                          topic='compute',
                          instance_id=self.inst_ref.id,
                          request_spec={'instance_type': self.instance_type,
                                        'instance_properties': {},
                                        'filter': self.filter_name,
                                        'num_instances': 1})

    def test_one_host_no_match_cap(self):
        scheduler = manager.SchedulerManager()
        caps = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'disk_available': 5,
               'xpu_arch': 'radeon', 'xpu_model': "ATI x345"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           caps)
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything=True)
        self.mox.ReplayAll()

        self.assertRaises(driver.NoValidHost,
                          scheduler.run_instance,
                          context=self.context,
                          topic='compute',
                          instance_id=self.inst_ref.id,
                          request_spec={'instance_type': self.instance_type,
                                        'instance_properties': {},
                                        'filter': self.filter_name,
                                        'num_instances': 1})

    def test_one_host_match_cap(self):
        scheduler = manager.SchedulerManager()
        caps = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'disk_available': 5,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_arch': "x86_64",
               'cpu_model': "Nehalem",
               'xpu_arch': 'fermi', 'xpu_model': "Tesla S2050"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           caps)
        instance_id = 1
        instance_properties = {}
        request_spec = {'instance_type': self.instance_type,
                        'instance_properties': instance_properties,
                        'filter': self.filter_name,
                        'num_instances': 1}
        self.mox.StubOutWithMock(compute.api.API,
                                 "create_db_entry_for_new_instance")
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything=True)
        compute.api.API().create_db_entry_for_new_instance(\
            mox.IsA(context.RequestContext), instance_properties, None, []).\
            AndReturn({'id': instance_id})
        rpc.cast(mox.IsA(context.RequestContext),
                'compute.host1',
                 {'method': 'run_instance',
                  'args': {'instance_id': instance_id},
                  'method': 'run_instance'})
        self.mox.ReplayAll()
        scheduler.run_instance(self.context,
                           topic='compute',
                           instance_id=self.inst_ref.id,
                           request_spec=request_spec)

    def test_two_host_one_match_cap(self):
        scheduler = manager.SchedulerManager()
        caps_host1 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'disk_available': 5,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_arch': "x86_6"}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           caps_host1)
        caps_host2 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'disk_available': 5,
               'cpu_arch': "x86_64",
               'cpu_model': "Nehalem",
               'xpu_arch': 'fermi', 'xpu_model': "Tesla S2050"}
        instance_id = 1
        instance_properties = {}
        request_spec = {'instance_type': self.instance_type,
                        'instance_properties': instance_properties,
                        'filter': self.filter_name,
                        'num_instances': 1}

        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host2",
                                                           caps_host2)
        self.mox.StubOutWithMock(compute.api.API,
                                 "create_db_entry_for_new_instance")
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything=True)
        compute.api.API().create_db_entry_for_new_instance(\
            mox.IsA(context.RequestContext), instance_properties, None, []).\
            AndReturn({'id': instance_id})
        rpc.cast(mox.IsA(context.RequestContext),
                'compute.host2',
                 {'method': 'run_instance',
                  'args': {'instance_id': instance_id},
                  'method': 'run_instance'})
        self.mox.ReplayAll()
        scheduler.run_instance(self.context,
                               topic='compute',
                               instance_id=self.inst_ref.id,
                               request_spec=request_spec)

    def test_two_host_two_match_cap(self):
        scheduler = manager.SchedulerManager()
        caps_host1 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'disk_available': 5,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_arch': "x86_64",
               'cpu_model': "Nehalem",
               'xpu_arch': 'fermi', 'xpu_model': "Tesla S2050"}
        caps_host2 = {'vcpus': 16, 'memory_mb': 32, 'local_gb': 100,
               'vcpus_used': 1, 'local_gb_used': 10, 'host_memory_free': 21651,
               'host_memory_total': 23640, 'disk_total': 97, 'disk_used': 92,
               'disk_available': 5,
               'hypervisor_type': 'qemu', 'hypervisor_version': 12003,
               'cpu_arch': "x86_64",
               'cpu_model': "Nehalem",
               'xpu_arch': 'fermi', 'xpu_model': "Tesla S2050"}
        instance_id = 1
        instance_properties = {}
        request_spec = {'instance_type': self.instance_type,
                        'instance_properties': instance_properties,
                        'filter': self.filter_name,
                        'num_instances': 1}
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host1",
                                                           caps_host1)
        scheduler.zone_manager.update_service_capabilities("compute",
                                                           "host2",
                                                           caps_host2)
        self.mox.StubOutWithMock(compute.api.API,
                                 "create_db_entry_for_new_instance")
        self.mox.StubOutWithMock(rpc, 'cast', use_mock_anything=True)
        compute.api.API().create_db_entry_for_new_instance(\
            mox.IsA(context.RequestContext), instance_properties, None, []).\
            AndReturn({'id': instance_id})
        rpc.cast(mox.IsA(context.RequestContext),
                'compute.host2',
                 {'method': 'run_instance',
                  'args': {'instance_id': instance_id},
                  'method': 'run_instance'})
        self.mox.ReplayAll()
        scheduler.run_instance(self.context,
                               topic='compute',
                               instance_id=self.inst_ref.id,
                               request_spec=request_spec)
