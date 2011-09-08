# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    License TBD

"""Handles all requests sent to DCNS."""

from nova import context
from nova import exception
from nova import flags
from nova import log as logging
from nova import rpc
from nova.db import base


LOG = logging.getLogger('nova.network.dcns.api')

FLAGS = flags.FLAGS


class API(base.Base):
    """API for interacting with the DCNS manager."""

    def setup_physical_network (self, context, project_id, host_nics, bandwidth, vlan):
        """API call to set up layer2 physial network."""
        LOG.debug(_("setting up physical network for project %s") % project_id)
        return rpc.call(context,
                        FLAGS.dcns_topic,
                        {"method": "setup_physical_network",
                         "args": {"project_id": project_id,
                                  "host_nics": host_nics,
                                  "bw": bandwidth,
                                  "vlan": vlan}})

        
    def modify_physical_network (self, context, project_id, add_host_nics, rem_host_nics, bandwidth, vlan):
        """API call to modify layer2 physial network."""
        LOG.debug(_("modifying physical network for project %s") % project_id)
        return rpc.call(context,
                        FLAGS.dcns_topic,
                        {"method": "modify_physical_network",
                         "args": {"project_id": project_id,
                                  "add_host_nics": add_host_nics,
                                  "rem_host_nics": rem_host_nics,
                                  "bw": bandwidth,
                                  "vlan": vlan}})


    def teardown_physical_network (self, context, project_id, forced):
        """API call to tear down layer2 physial network."""
        LOG.debug(_("tearing down up physical network for project %s") % project_id)
        return rpc.call(context,
                        FLAGS.dcns_topic,
                        {"method": "teardown_physical_network",
                         "args": {"project_id": project_id, 'forced':forced}})

    def get_network_info (self, context, project_id):
        """API call to set up layer2 physial network."""
        LOG.debug(_("getting physical network info for project %s") % project_id)
        return rpc.call(context,
                        FLAGS.dcns_topic,
                        {"method": "get_network_info",
                         "args": {"project_id": project_id}})

