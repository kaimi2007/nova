# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    License TBD

from nova import exception
from nova import flags
from nova import log as logging


LOG = logging.getLogger("nova.network.dcns.driver_base")

FLAGS = flags.FLAGS


class L2DCNDriver(object):
    """DCNS Base Driver for L2 Neworking
       Abstract class
    """

    def init_host(self, host):
        raise NotImplementedError()

    """ A P2P path hop is represented by a dict that could represent:
           ero_hop by DRAGON
           hop urn by OSCARS
           datapath element by OpenFlow
    """

    def setup_p2p_path(self, gri, hops, bw, vlan):
        """ Set up p2p path with hops array
            Abstract
        """
        raise NotImplementedError()

    def teardown_p2p_path(self, gri, hops):
        """ Tear down p2p path with hops array
            Abstract
        """
        raise NotImplementedError()

    def verify_p2p_path(self, gri, hops):
        """ Verify p2p path with hops array
            Abstract
        """
        raise NotImplementedError()

    """ A MP path hop is also represented by a dict.
        In addition to the hop format in P2P hop, it could 
        also be a branch element that points to a branch array.
        Only multicast tree topology is supported by MP path.
    """

    def setup_mp_path(self, gri, mp_hops, bw, vlan):
        """ Set up multipoint path with mp_hops array
            Abstract
        """
        raise NotImplementedError()

    def teardown_mp_path(self, gri, mp_hops):
        """ Tear down multipoint path with mp_hops array
            Abstract
        """
        raise NotImplementedError()

    def verify_mp_path(self, gri, mp_hops):
        """ Verify multipoint path with mp_hops array
            Abstract
        """
        raise NotImplementedError()


class StubL2DCNDriver(L2DCNDriver):
    """Stub DCNS Driver for L2 instantation
       For p2p path only
    """

    def init_host(self, host):
        pass

    def setup_p2p_path(self, gri, hops, bw, vlan):
        """ Set up p2p path with hops array """
        LOG.debug(_("setting up path for gri: %s") % gri)
        LOG.debug(_("path committed on hops: %s") % self.get_path_hops_urn(hops))
        return 1

    def teardown_p2p_path(self, gri, hops):
        """ Tear down p2p path with hops array """
        LOG.debug(_("tearing down path for gri: %s") % gri)
        LOG.debug(_("path deleted on hops: %s") % self.get_path_hops_urn(hops))
        return 1

    def verify_p2p_path(self, gri, hops):
        """ Verify p2p path with hops array """
        LOG.debug(_("verifying path for gri: %s") % gri)
        LOG.debug(_("path active for hops: %s") % self.get_path_hops_urn(hops))
        return 1

    def get_path_hops_urn(self, hops):
        """ Display path in string with urn of every hop """
        path_str = ''
        path_str += '--'
        for hop in hops:
            path_str += hop
            path_str += '--'
        return path_str

    """ MP path methods are not supported """

    def setup_mp_path(self, gri, mp_hops, bw, vlan):
        raise NotImplementedError()

    def teardown_mp_path(self, gri, mp_hops):
        raise NotImplementedError()

    def verify_mp_path(self, gri, mp_hops):
        raise NotImplementedError()


