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

    def hosts_up_with_arch(self, context, topic, instance_id):
        """Return the list of hosts that have a running service
        for topic and arch (if defined).
        """

        if instance_id is None:
            return self.hosts_up(context, topic)

        instances = db.instance_get_all_by_instance_id(context,
                                                       instance_id)
        LOG.debug(_("##\tRLK - instances %s"),
                  instances)

        services = db.service_get_all_by_topic(context, topic)

        LOG.debug(_("##\tRLK - services %s"),
                  services)
        LOG.debug(_("##\tRLK - instance.id %s"),
                  instances[0].id)
        LOG.debug(_("##\tRLK - instance.cpu_arch %s"),
                  instances[0].cpu_arch)
        LOG.debug(_("##\tRLK - instance.xpu_arch %s"),
                  instances[0].xpu_arch)
        """Select first compute_node available where cpu_arch and xpu_arch
        match the instance. extend to selecting compute_node only if it is
        available.
        """
        compute_nodes = db.compute_node_get_by_arch(context,
                                                    instances[0].cpu_arch,
                                                    instances[0].xpu_arch)
        LOG.debug(_("##\tRLK - compute_nodes.service_id %d"),
            compute_nodes.service_id)
        #LOG.debug(_("##\tRLK - compute_nodes.length %d"),
        # len(compute_nodes))
        #for node in compute_nodes:
        #    LOG.debug(_("##\tRLK - node %s"), node)
        #compute_node = compute_nodes[int(random.random() *
        # len(compute_nodes))]
        services = db.service_get_all_by_topic(context, topic)
        LOG.debug(_("##\tRLK - services %s"), services)
        return [service.host
                for service in services
                if self.service_is_up(service)
                and service.id == compute_nodes.service_id]

    def schedule(self, context, topic, *_args, **_kwargs):
        """Picks a host that is up at random in selected
        arch (if defined).
        """

        instance_id = _kwargs.get('instance_id')
        LOG.debug(_("##\tRLK - instance_id %s"), instance_id)
        hosts = self.hosts_up_with_arch(context, topic, instance_id)
        if not hosts:
            raise driver.NoValidHost(_("No hosts found with instance_id %s"
                % instance_id))
        LOG.debug(_("##\tRLK - host(s) %(hosts)s available "),
                {'hosts': hosts})
        return hosts[int(random.random() * len(hosts))]
