# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    License TBD

from nova import exception
from nova import flags
from nova import log as logging

import yaml

LOG = logging.getLogger("nova.network.dcns.topology")

FLAGS = flags.FLAGS


class HostPortMapper(object):
    """Mapping host:interface into topology edge port
    """

    def __init__(self):
        f = file(FLAGS.host_port_map_file, 'r')
        self.host_port_map = list(yaml.load_all(f))
        f.close()

    def lookup_port_by_host(self, host, nic):
        """ Look up topology edge port that is attached to the host:nic
        """
        for hp in self.host_port_map:
            if hp['host'] == host and hp['nic'] == nic:
                return hp['port']
        return None

    def lookup_host_by_port(self, port):
        """ Look up host:nic by topology edge port 
        """
        for hp in self.host_port_map:
            if hp['port'] == port:
                return hp['port']+":"+hp['nic']
        return None


# TODO: class Topology, Domain etc.
