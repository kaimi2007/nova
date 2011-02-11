# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2010 Openstack, LLC.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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
Archtecture Scheduler implementation
"""

import random


from nova import log as logging

LOG = logging.getLogger('nova.scheduler.ArchitectureScheduler')

from nova.scheduler import driver
from nova import db


class ArchitectureScheduler(driver.Scheduler):
    """Implements Scheduler as a random node selector."""

    def hosts_up_with_arch(self, context, topic, arch):
        """Return the list of hosts that have a running service
        for topic and arch (if defined).
        """

        if arch is None:
            return self.hosts_up(context, topic)

        services = db.service_get_all_by_topic(context, topic)
        return [service.host
                for service in services
                if self.service_is_up(service)
                and service.arch == arch]

    def schedule(self, context, topic, *_args, **_kwargs):
        """Picks a host that is up at random in selected
        arch (if defined).
        """

        arch = _kwargs.get('arch')
        hosts = self.hosts_up_with_arch(context, topic, arch)
        if not hosts:
            raise driver.NoValidHost(_("No hosts found with arch %s"
                % arch))
        LOG.debug(_("##\tRLK - host(s) %(hosts)s available for arch %(arch)s"), 
                {'hosts':hosts, 'arch':arch})
        return hosts[int(random.random() * len(hosts))]
