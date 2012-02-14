# Copyright (c) 2011 Openstack, LLC.
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
Manage communication with child zones and keep state for them.
"""

import datetime
import traceback

from eventlet import greenpool
from novaclient import v1_1 as novaclient

from nova import db
from nova import flags
from nova import log as logging
from nova.openstack.common import cfg
from nova import utils


zone_manager_opts = [
    cfg.IntOpt('zone_db_check_interval',
               default=60,
               help='Seconds between getting fresh zone info from db.'),
    cfg.IntOpt('zone_failures_to_offline',
               default=3,
               help='Number of consecutive errors before offlining a zone'),
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(zone_manager_opts)

LOG = logging.getLogger(__name__)


class ZoneState(object):
    """Holds state for a particular zone."""
    def __init__(self):
        self.is_active = True
        self.capabilities = {}
        self.attempt = 0
        self.last_seen = datetime.datetime.min
        self.last_exception = None
        self.last_exception_time = None
        self.zone_info = {}

    def update_zone_info(self, zone):
        """Update zone credentials from db"""
        self.zone_info = dict(zone.iteritems())

    def update_metadata(self, zone_metadata):
        """Update zone metadata after successful communications with
           child zone."""
        self.last_seen = utils.utcnow()
        self.attempt = 0
        self.capabilities = dict(
                [(k, v) for k, v in zone_metadata.iteritems() if k != 'name'])
        self.is_active = True

    def get_zone_info(self):
        db_fields_to_return = ['api_url', 'id', 'weight_scale',
                'weight_offset']
        zone_info = dict(is_active=self.is_active,
                capabilities=self.capabilities)
        for field in db_fields_to_return:
            zone_info[field] = self.zone_info[field]
        return zone_info

    def log_error(self, exception):
        """Something went wrong. Check to see if zone should be
           marked as offline."""
        self.last_exception = exception
        self.last_exception_time = utils.utcnow()
        api_url = self.zone_info['api_url']
        LOG.warning(_("'%(exception)s' error talking to "
                          "zone %(api_url)s") % locals())

        max_errors = FLAGS.zone_failures_to_offline
        self.attempt += 1
        if self.attempt >= max_errors:
            self.is_active = False
            LOG.error(_("No answer from zone %(api_url)s "
                            "after %(max_errors)d "
                            "attempts. Marking inactive.") % locals())

    def call_novaclient(self):
        """Call novaclient. Broken out for testing purposes. Note that
        we have to use the admin credentials for this since there is no
        available context."""
        username = self.zone_info['username']
        password = self.zone_info['password']
        api_url = self.zone_info['api_url']
        region_name = self.zone_info['name']
        client = novaclient.Client(username, password, None, api_url,
                region_name)
        return client.zones.info()._info

    def poll(self):
        """Eventlet worker to poll a self."""
        if 'api_url' not in self.zone_info:
            return
        name = self.zone_info['name']
        api_url = self.zone_info['api_url']
        LOG.debug(_("Polling zone: %(name)s @ %(api_url)s") % locals())
        try:
            self.update_metadata(self.call_novaclient())
        except Exception, e:
            self.log_error(traceback.format_exc())


class ZoneManager(object):
    """Keeps the zone states updated."""
    def __init__(self):
        self.last_zone_db_check = datetime.datetime.min
        self.zone_states = {}  # { <zone_id> : ZoneState }
        self.green_pool = greenpool.GreenPool()
        self.service_states = {}  # { <host> : { <service> : { cap k : v }}}
        self.service_time_stamp = {}  # reported time

    def get_zone_list(self):
        """Return the list of zones we know about."""
        return [zone.get_zone_info() for zone in self.zone_states.values()]

    def get_hosts_capabilities(self, context):
        """Return the capabilities of the individual hosts within a zone.

        Returns a dict: { <host> : {<service> : {<cap_key> : <cap_value>}}}
        """

        hosts_dict = self.service_states

        allowed_time_diff = FLAGS.periodic_interval * 3

        combined = {}  # { <service>_<cap> : (min, max), ... }
        for host, host_dict in hosts_dict.iteritems():
#            print "TIME CHECK: now = " , utils.utcnow()
#            print "TIME CHECK: time_stamp=", self.service_time_stamp[host]
#            print "TIME CHECK: a_diff= " , allowed_time_diff
            if (utils.utcnow() - self.service_time_stamp[host]) <= \
                datetime.timedelta(seconds=allowed_time_diff):

                combined[host] = host_dict

        return combined

    def _refresh_from_db(self, context):
        """Make our zone state map match the db."""
        # Add/update existing zones ...
        zones = db.zone_get_all(context)
        existing = self.zone_states.keys()
        db_keys = []
        for zone in zones:
            zone_id = zone['id']
            db_keys.append(zone_id)
            if zone_id not in existing:
                self.zone_states[zone_id] = ZoneState()
            self.zone_states[zone_id].update_zone_info(zone)

        # Cleanup zones removed from db ...
        keys = self.zone_states.keys()  # since we're deleting
        for zone_id in keys:
            if zone_id not in db_keys:
                del self.zone_states[zone_id]

    def _poll_zones(self):
        """Try to connect to each child zone and get update."""
        def _worker(zone_state):
            zone_state.poll()
        self.green_pool.imap(_worker, self.zone_states.values())

    def update(self, context):
        """Update status for all zones.  This should be called
        periodically to refresh the zone states.
        """
        diff = utils.utcnow() - self.last_zone_db_check
        if diff.seconds >= FLAGS.zone_db_check_interval:
            LOG.debug(_("Updating zone cache from db."))
            self.last_zone_db_check = utils.utcnow()
            self._refresh_from_db(context)
        self._poll_zones()

    def update_service_capabilities(self, service_name, host, capabilities):
        """Update the per-service capabilities based on this notification."""
        logging.debug(_("Received %(service_name)s service update from "
                "%(host)s.") % locals())
        service_caps = self.service_states.get(host, {})
        capabilities["timestamp"] = utils.utcnow()  # Reported time
        service_caps[service_name] = capabilities
        self.service_states[host] = service_caps
        self.service_time_stamp[host] = utils.utcnow()

    def host_service_caps_stale(self, host, service):
        """Check if host service capabilites are not recent enough."""
        allowed_time_diff = FLAGS.periodic_interval * 3
        caps = self.service_states[host][service]
        if (utils.utcnow() - caps["timestamp"]) <= \
            datetime.timedelta(seconds=allowed_time_diff):
            return False
        return True

    def delete_expired_host_services(self, host_services_dict):
        """Delete all the inactive host services information."""
        for host, services in host_services_dict.iteritems():
            service_caps = self.service_states[host]
            for service in services:
                del service_caps[service]
                if len(service_caps) == 0:  # Delete host if no services
                    del self.service_states[host]
