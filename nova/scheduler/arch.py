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

#    def hosts_up_with_arch(self, context, topic, instance_id):
    def hosts_up_with_arch(self, context, topic,  \
        wanted_cpu_arch, wanted_vcpus, wanted_xpu_arch, wanted_xpus,
        wanted_memory_mb, wanted_local_gb):

        """Return the list of hosts that have a running service
        for cpu_arch and xpu_arch.
        """

#        if instance_id is None:
#            return self.hosts_up(context, topic)

#        """Figure out what is requested for cpu_arch and xpu_arch.
#        """
#        instances = db.instance_get_all_by_instance_id(context,
#                                                       instance_id)

#        LOG.debug(_("##\tRLK - instances %s"), instances)
#        LOG.debug(_("##\tRLK - instance.id %s"), instances[0].id)
#        LOG.debug(_("##\tRLK - instance.cpu_arch %s"), instances[0].cpu_arch)
#        LOG.debug(_("##\tRLK - instance.xpu_arch %s"), instances[0].xpu_arch)

        services = db.service_get_all_by_topic(context, topic)
        LOG.debug(_("##\tRLK - services %s"), services)

        """Select all compute_node available where cpu_arch and xpu_arch
        match the instance available.
        """
#        compute_nodes = db.compute_node_get_all_by_arch(context,
#                instances[0].cpu_arch, instances[0].xpu_arch)
#        LOG.debug(_("##\tRLK - compute_nodes.length %d"), len(compute_nodes))
#        services = db.service_get_all_by_topic(context, topic)

        hosts = []

#        wanted_cpu_arch = instances[0].cpu_arch
#        wanted_xpu_arch = instances[0].xpu_arch
#        wanted_memory_mb = instances[0].memory_mb
#        wanted_local_gb = instances[0].local_gb
        LOG.debug(_("##\tJSUH - wanted-cpu-arch=%s"), wanted_cpu_arch)
        LOG.debug(_("##\tJSUH - wanted-xpu-arch=%s"), wanted_xpu_arch)
        LOG.debug(_("##\tJSUH - wanted-vcpus=%s"), wanted_vcpus)
        LOG.debug(_("##\tJSUH - wanted-xpus=%s"), wanted_xpus)
        LOG.debug(_("##\tJSUH - wanted-memory=%s"), wanted_memory_mb)
        LOG.debug(_("##\tJSUH - wanted-hard=%s"), wanted_local_gb)

        """Get capability from zone_manager and match cpu_arch and xpu_arch,
        """
        cap = self.zone_manager.get_zone_capabilities(context)
        LOG.debug(_("##\tJSUH - cap=%s"), cap)

#        for host, host_dict in cap.iteritems():
#            LOG.debug(_("##\tJSUH - host=%s"), host)
#            LOG.debug(_("##\tJSUH - host-dc=%s"), host_dict)
#            for service_name, service_dict in host_dict.iteritems():
#                LOG.debug(_("##\tJSUH - servname=%s"), service_name)
#                LOG.debug(_("##\tJSUH - servnval=%s"), service_dict)
#                for cap, value in service_dict.iteritems():
#                    LOG.debug(_("##\tJSUH - cap=%s"), cap)
#                    LOG.debug(_("##\tJSUH - val=%s"), value)

        for host, host_dict_cap in cap.iteritems():
#            LOG.debug(_("##\tJSUH - host=%s"), host)
            for service_name_cap, service_dict_cap in \
                host_dict_cap.iteritems():
                if (service_name_cap != 'compute'):
                    continue
#                LOG.debug(_("##\tJSUH - servname=%s"), service_name_cap)
#                LOG.debug(_("##\tJSUH - servnval=%s"), service_dict_cap)

                resource_cap = {}
                for cap, value in service_dict_cap.iteritems():
#                    LOG.debug(_("##\tJSUH - cap=%s"), cap)
#                    LOG.debug(_("##\tJSUH - val=%s"), value)
                    resource_cap[cap] = value

                if (wanted_cpu_arch == resource_cap['cpu_arch']):
                    if (wanted_xpu_arch == resource_cap['xpu_arch']):

                        LOG.debug(_("##\tJSUH - ***** found  **********="))
#                        for key, val in resource.iteritems():
#                            LOG.debug(_("##\tJSUH - cap=%s"), cap)
#                            LOG.debug(_("##\tJSUH - val=%s"), value)

                        # JSUH: Check resource availability
                        resource = {'vcpus': resource_cap['vcpus'],
                                    'xpus': resource_cap['xpus'] \
                                        - resource_cap['xpus_used'],
                                    'memory_mb':
                                        resource_cap['host_memory_free'],
                                    'local_gb': resource_cap['disk_total']
                                        - resource_cap['disk_used']}

                        # Getting usage resource information
                        LOG.debug(_("##\tJSUH - vpu total  = %s"),
                                 resource['vcpus'])
                        LOG.debug(_("##\tJSUH - vpu needed  = %s"),
                                 wanted_vcpus)
                        LOG.debug(_("##\tJSUH - xpu total  = %s"),
                                 resource['xpus'])
                        LOG.debug(_("##\tJSUH - xpu needed  = %s"),
                                wanted_xpus)
                        LOG.debug(_("##\tJSUH - mem total  = %s"),
                                 resource['memory_mb'])
                        LOG.debug(_("##\tJSUH - mem needed  = %s"),
                                 wanted_memory_mb)
                        LOG.debug(_("##\tJSUH - hdd total  = %s"),
                                 resource['local_gb'])
                        LOG.debug(_("##\tJSUH - hdd needed  = %s"),
                                 wanted_local_gb)

                        append_decision = 1
                        if wanted_vcpus > resource['vcpus']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of vcpus"))
                        if wanted_xpus > resource['xpus']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of xpus"))
                        if wanted_memory_mb > resource['memory_mb']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of memory"))
                        if wanted_local_gb > resource['local_gb']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of hard disk"))

                        if append_decision == 1:
                            hosts.append(host)
                            LOG.debug(_("##\tJSUH - appended"))
#                        else: # cannot allow
#                            db.instance_destroy(context,instance_id)
#                            LOG.debug(_("##\tJSUH - inst id= %s deleted"),
#                                instance_id)
                        # JSUH: end
                    elif (wanted_xpu_arch is None):
                        LOG.debug(_("##\tJSUH - ***** found  **********="))

                        # JSUH: Check resource availability
                        resource = {'vcpus': resource_cap['vcpus'],
                                    'memory_mb':
                                        resource_cap['host_memory_free'],
                                    'local_gb': resource_cap['disk_total']
                                        - resource_cap['disk_used']}

                        # Getting usage resource information
                        LOG.debug(_("##\tJSUH - vpu total  = %s"),
                                 resource['vcpus'])
                        LOG.debug(_("##\tJSUH - vpu needed  = %s"),
                                 wanted_vcpus)
                        LOG.debug(_("##\tJSUH - mem total  = %s"),
                                 resource['memory_mb'])
                        LOG.debug(_("##\tJSUH - mem needed  = %s"),
                                 wanted_memory_mb)
                        LOG.debug(_("##\tJSUH - hdd total  = %s"),
                                 resource['local_gb'])
                        LOG.debug(_("##\tJSUH - hdd needed  = %s"),
                                 wanted_local_gb)

                        append_decision = 1
                        if wanted_vcpus > resource['vcpus']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of vcpus"))
                        if wanted_memory_mb > resource['memory_mb']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of memory"))
                        if wanted_local_gb > resource['local_gb']:
                            append_decision = 0
                            LOG.debug(_("##\tJSUH *** LACK of hard disk"))

                        if append_decision == 1:
                            hosts.append(host)
                            LOG.debug(_("##\tJSUH - appended"))
#                        else: # cannot allow
#                            db.instance_destroy(context,instance_id)
#                            LOG.debug(_("##\tJSUH - inst id= %s deleted"),
#                                instance_id)
                        # JSUH: end

        LOG.debug(_("##\tJSUH - hosts = %s"), hosts)
        return hosts

    def schedule(self, context, topic, *_args, **_kwargs):
        """Picks a host that is up at random in selected
        arch (if defined).
        """

#        instance_id = _kwargs.get('instance_id')
        wanted_cpu_arch = _kwargs.get('wanted_cpu_arch')
        wanted_xpu_arch = _kwargs.get('wanted_xpu_arch')
        wanted_vcpus = _kwargs.get('wanted_vcpus')
        wanted_xpus = _kwargs.get('wanted_xpus')
        wanted_memory_mb = _kwargs.get('wanted_memory_mb')
        wanted_local_gb = _kwargs.get('wanted_local_gb')
#        LOG.debug(_("##\tRLK - instance_id %s"), instance_id)
#        hosts = self.hosts_up_with_arch(context, topic, instance_id)
        hosts = self.hosts_up_with_arch(context, topic, wanted_cpu_arch,
            wanted_vcpus, wanted_xpu_arch, wanted_xpus, wanted_memory_mb,
            wanted_local_gb)
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
