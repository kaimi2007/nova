# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
#    Copyright 2010 OpenStack LLC
#    Copyright 2012 University Of Minho
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

import errno
import os
import shutil

from nova.compute import instance_types
from nova import context
from nova import db
from nova import exception
from nova import flags
from nova.openstack.common import importutils
from nova.openstack.common import log as logging
from nova import test
from nova import utils
from nova.virt.gpu import driver as gpulibvirt_driver
from nova.virt.gpu import utils as gpu_utils

from nova.virt.libvirt import driver as libvirt_driver

try:
    import libvirt
except ImportError:
    import nova.tests.fakelibvirt as libvirt
libvirt_driver.libvirt = libvirt


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


COMMON_FLAGS = dict(

    instance_type_extra_specs=['cpu_arch:x86_64',
                               'gpus:1', 'gpu_arch:fermi',
                               'hypervisor_type:LXC'],
    libvirt_type='lxc',
    dev_cgroups_path='/test/cgroup'
)


class GPULibvirtDriverTestCase(test.TestCase):
    """Test for nova.virt.gpu.gpulibvirt_driver.LibvirtDriver."""
    def setUp(self):
        super(GPULibvirtDriverTestCase, self).setUp()

        self.flags(**COMMON_FLAGS)
        self.flags(fake_call=True)
        self.user_id = 'fake'
        self.project_id = 'fake'
        self.context = context.get_admin_context()
        self.gpulibvirtconnection = \
                gpulibvirt_driver.GPULibvirtDriver(read_only=True)
        self.root_fs = './test-gpu'
        self.cgroup_path = self.root_fs + '/cgroup/fake'
        self.etc_path = self.root_fs + '/etc'
        flavor_id = \
            instance_types.get_instance_type_by_name('m1.small')['flavorid']
        extra_specs = {}
        extra_specs['cpu_arch'] = 's== x86_64'
        extra_specs['gpus'] = '= 1'
        extra_specs['gpu_arch'] = 's== fermi'
        extra_specs['hypervisor_type'] = 's== LXC'

        db.instance_type_extra_specs_update_or_create(
                  context.get_admin_context(), flavor_id, extra_specs)

    def tearDown(self):
        super(GPULibvirtDriverTestCase, self).tearDown()

    inst_meta = {'gpus': 1}
    test_instance = {'memory_kb': '1024000',
                     'basepath': '/some/path',
                     'bridge_name': 'br100',
                     'vcpus': 2,
                     'name': 'fake',
                     'project_id': 'fake',
                     'bridge': 'br101',
                     'image_ref': '155d900f-4e14-4e4c-a73d-069cbf4541e6',
                     'root_gb': 10,
                     'ephemeral_gb': 20,
                     'metadata': inst_meta,
                     'instance_type_id': '5'}  # m1.small

    def testInitGPU(self):
        extra_specs = gpu_utils.get_instance_type_extra_specs_capabilities()
        init_gpus = extra_specs['gpus']
        self.assertEquals(1, int(init_gpus))
        self.assertEquals(1, gpu_utils.get_gpu_total())

    def testAssignDeassignGPU(self):
        if os.path.isdir(self.root_fs):
            shutil.rmtree(self.root_fs)
        os.makedirs(self.cgroup_path)
        os.makedirs(self.etc_path)
        gpu_utils.assign_gpus(self.context, self.test_instance,
                              self.root_fs)
        self.assertEquals(0, gpu_utils.get_gpu_total())

        gpu_utils.deassign_gpus(self.test_instance)
        self.assertEquals(1, gpu_utils.get_gpu_total())
        shutil.rmtree(self.root_fs)

    def testOverAllocationGPU(self):
        if os.path.isdir(self.root_fs):
            shutil.rmtree(self.root_fs)
        os.makedirs(self.cgroup_path)
        os.makedirs(self.etc_path)
        gpu_utils.assign_gpus(self.context, self.test_instance, self.root_fs)
        try:
            gpu_utils.assign_gpus(self.context, self.test_instance,
                                  self.root_fs)
        except Exception as Exn:
            gpu_utils.deassign_gpus(self.test_instance)
            shutil.rmtree(self.root_fs)
            return
        shutil.rmtree(self.root_fs)
        assert false, "Cannot detect over-allocation"
