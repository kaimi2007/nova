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

from nova import db
from nova.scheduler import host_filter
from nova.scheduler import driver


class HeterogeneousScheduler(driver.Scheduler):
    """Very simple heterogeneous scheduler that selects at random
    from nodes that satisfy the instance requirements"""

    def schedule_run_instance(self, context, instance_id, request_spec,
                              *args, **kwargs):
        """This method is called from nova.compute.api to provision
        an instance."""
        instance_type = request_spec['instance_type']
        filter = host_filter.InstanceTypeFilter()
        name, cooked = filter.instance_type_to_filter(instance_type)
        # filter_hosts returns a list of (host, cap) pairs
        host_cap_pairs = filter.filter_hosts(self.zone_manager, cooked)
        hosts = [x[0] for x in host_cap_pairs]
        if len(hosts) > 0:
            return hosts[int(random.random() * len(hosts))]
        else:
            raise driver.NoValidHost(_("No hosts satisfy requirements"))
