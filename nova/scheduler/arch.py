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
        for cpu_arch and xpu_arch.
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
        """Select all compute_node available where cpu_arch and xpu_arch
        match the instance available.
        """
        compute_nodes = db.compute_node_get_all_by_arch(context,
                instances[0].cpu_arch, instances[0].xpu_arch)
        LOG.debug(_("##\tRLK - compute_nodes.length %d"), len(compute_nodes))
        services = db.service_get_all_by_topic(context, topic)
        hosts = []
        for compute_node in compute_nodes:
            LOG.debug(_("##\tRLK - found matching compute_node.id = %s"),
                    compute_node.id)
            for service in services:
                if (self.service_is_up(service)
                        and service.id == compute_node.service_id):
                    LOG.debug(_("##\tRLK - found matching service.id = %s"),
                        service.id)

                    # JSUH: Check resource availability

                    host = service.host
                    compute_ref = db.service_get_all_compute_by_host(
                        context, host)
                    compute_ref = compute_ref[0]

                    # Getting physical resource information
                    compute_node_ref = compute_ref['compute_node'][0]
                    resource = {'vcpus': compute_node_ref['vcpus'],
                                'memory_mb': compute_node_ref['memory_mb'],
                                'local_gb': compute_node_ref['local_gb'],
                                'vcpus_used': compute_node_ref['vcpus_used'],
                                'memory_mb_used':
                                    compute_node_ref['memory_mb_used'],
                                'local_gb_used':
                                    compute_node_ref['local_gb_used']}

                    # Getting usage resource information
                    usage = {}
                    instance_refs = db.instance_get_all_by_host(context,
                        compute_ref['host'])
                    LOG.debug(_("##\tJSUH - instance_ref = %s"), instance_refs)
                    if instance_refs:
                        LOG.debug(_("##\tJSUH - instance_ref = true"))
                        project_ids = [i['project_id'] for i in instance_refs]
                        project_ids = list(set(project_ids))
                        for project_id in project_ids:
                            LOG.debug(_("##\tJSUH - proj id = %s"), project_id)
                            vcpus = \
                                db.instance_get_vcpu_sum_by_host_and_project(
                                context, host, project_id)
                            mem = \
                                db.instance_get_memory_sum_by_host_and_project(
                                context, host, project_id)
                            hdd = \
                                db.instance_get_disk_sum_by_host_and_project(
                                context, host, project_id)
                            LOG.debug(_("##\tJSUH - vcpu used = %s"), vcpus)
                            LOG.debug(_("##\tJSUH - vpu total  = %s"),
                                resource['vcpus'])
                            LOG.debug(_("##\tJSUH - vpu needed  = %s"),
                                instances[0].vcpus)
                            LOG.debug(_("##\tJSUH - mem used = %s"), mem)
                            LOG.debug(_("##\tJSUH - mem total  = %s"),
                                resource['memory_mb'])
                            LOG.debug(_("##\tJSUH - mem needed  = %s"),
                                instances[0].memory_mb)
                            LOG.debug(_("##\tJSUH - hdd used = %s"), hdd)
                            LOG.debug(_("##\tJSUH - hdd total  = %s"),
                                resource['local_gb'])
                            LOG.debug(_("##\tJSUH - hdd needed  = %s"),
                                instances[0].local_gb)

                            append_decision = 1
                            if (vcpus + instances[0].vcpus) > \
                                resource['vcpus']:
                                append_decision = 0
                                LOG.debug(_("##\tJSUH - lack of vcpus"))
                            if (mem + instances[0].memory_mb) > \
                                 resource['memory_mb']:
                                append_decision = 0
                                LOG.debug(_("##\tJSUH - lack of memory"))
                            if (hdd + instances[0].local_gb) > \
                                 resource['local_gb']:
                                append_decision = 0
                                LOG.debug(_("##\tJSUH - lack of hard disk"))

                            if append_decision == 1:
                                hosts.append(service.host)
                                LOG.debug(_("##\tJSUH - appended"))
                            else:  # cannot allow
                                db.instance_destroy(context, instance_id)
                                LOG.debug(_("##\tJSUH - inst id= %s deleted"),
                                 instance_id)
                    else:
                        LOG.debug(_("##\tJSUH - no previous instance_ref"))
                        LOG.debug(_("##\tJSUH - vpu total  = %s"),
                                 resource['vcpus'])
                        LOG.debug(_("##\tJSUH - vpu needed  = %s"),
                                 instances[0].vcpus)
                        LOG.debug(_("##\tJSUH - mem total  = %s"),
                                 resource['memory_mb'])
                        LOG.debug(_("##\tJSUH - mem needed  = %s"),
                                 instances[0].memory_mb)
                        LOG.debug(_("##\tJSUH - hdd total  = %s"),
                                 resource['local_gb'])
                        LOG.debug(_("##\tJSUH - hdd needed  = %s"),
                                 instances[0].local_gb)

                        append_decision = 1
                        if (instances[0].vcpus) > resource['vcpus']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH - lack of vcpus"))
                        if (instances[0].memory_mb) > resource['memory_mb']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH - lack of memory"))
                        if (instances[0].local_gb) > resource['local_gb']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH - lack of hard disk"))

                        if append_decision == 1:
                            hosts.append(service.host)
                            LOG.debug(_("##\tJSUH - appended"))
                        else:  # cannot allow
                            db.instance_destroy(context, instance_id)
                            LOG.debug(_("##\tJSUH - inst id= %s deleted"),
                                instance_id)
                    # JSUH: end

        LOG.debug(_("##\tJSUH - hosts = %s"), hosts)
        return hosts

    def schedule(self, context, topic, *_args, **_kwargs):
        """Picks a host that is up at random in selected
        arch (if defined).
        """

        instance_id = _kwargs.get('instance_id')
        LOG.debug(_("##\tRLK - instance_id %s"), instance_id)
        hosts = self.hosts_up_with_arch(context, topic, instance_id)
# JSUH
#        if not hosts:
#            raise driver.NoValidHost(_("No hosts found with instance_id %s"
#                % instance_id))
        LOG.debug(_("##\tRLK - host(s) %(hosts)s available "),
                {'hosts': hosts})
        if not hosts:
            return hosts
        else:
            return hosts[int(random.random() * len(hosts))]
