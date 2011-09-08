# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    License TBD

from nova import exception
from nova import flags
from nova import log as logging

import yaml

LOG = logging.getLogger("nova.network.dcns.pce")

FLAGS = flags.FLAGS


class PCEBase(object):
    """DCNS Path Computation Element Base
       Abstract class
    """

    def init_host(self, host):
        raise NotImplementedError()

    def compute_p2p_path(self, srcEndPoint, dstEndPoint):
        """ Compute p2p path and return switch hops
        """
        raise NotImplementedError()

    def compute_mp_path(self, endPoints):
        """ Compute multipoint path to form bcast network among endPoints
            and return switch hops
        """
        raise NotImplementedError()


class StaticPCE(PCEBase):
    """Return path hops from static path config file
       For p2p path only
    """

    def __init__(self):
        f = file(FLAGS.static_route_file, 'r')
        self.static_routes = list(yaml.load_all(f))
        f.close()
        self.project_paths = {}

    def compute_p2p_path(self, source, destination):
        for route in self.static_routes:
            if route['source'] == source and route['destination'] == destination:
                return route['path']
        return None

    def compute_mp_path(self, endPoints):
        """ Not supported """
        raise NotImplementedError()

    def set_project_path(self, project, path):
        self.project_paths[project] = path

    def get_project_path(self, project):
        return self.project_paths.get(project)

