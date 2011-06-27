# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 University of Southern California
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
Heterogeneous scheduler implementation
"""

import random

from nova import log as logging

LOG = logging.getLogger('nova.scheduler.HeterogeneousScheduler')

from nova.scheduler import driver
from nova import db


class HeterogeneousScheduler(driver.Scheduler):
    """Very simple heterogeneous scheduler that selects at random
    from nodes that satisfy the instance requirements"""

    def schedule_run_instance(self, context, instance_id, request_spec,
                              *args, **kwargs):
        """This method is called from nova.compute.api to provision
        an instance."""                    
        instance_type = request_spec['instance_type']
        it_filter = InstanceTypeFilter()
        name, cooked = it_filter.instance_type_to_filter(instance_type)
        hosts = hf.filter_hosts(self.zone_manager, cooked)
        if not hosts:
            return hosts
        else:
            return hosts[int(random.random() * len(hosts))]
        

