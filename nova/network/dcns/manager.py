# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    License TBD

import datetime
import netaddr
import socket

from nova import context
from nova import exception
from nova import flags
from nova import log as logging
from nova import manager as nova_manager
from nova.db import api as nova_db_api
from nova import utils
from nova import rpc
from nova.network.dcns import api as dcns_api
from nova.network.dcns import topology
from nova.network.dcns import pce


LOG = logging.getLogger("nova.network.dcns.manager")

FLAGS = flags.FLAGS

class DCNService(nova_manager.SchedulerDependentManager):

    def __init__(self, l2dcn_driver=None, *args, **kwargs):
        """Initializes DCNS
        Args:
           l2dcn_driver: The L2 DCN driver such as OSCARS, DRAGON and OpenFlow.
        """
        if not l2dcn_driver:
            l2dcn_driver = FLAGS.l2dcn_driver
        self.driver = utils.import_object(l2dcn_driver)

        self.api = dcns_api.API()

        self.hostPortMapper = topology.HostPortMapper()

        self.staticPCE = pce.StaticPCE()

        self.cached_host_nics = {}

        super(DCNService, self).__init__(service_name='nova_dcns',
                                             *args, **kwargs)

    def init_host(self):
        """Do any initialization that needs to be run if this is a
           standalone service.
        """
        pass

    def periodic_tasks(self, context=None):
        """Tasks to be run at a periodic interval."""
        super(DCNService, self).periodic_tasks(context)


    def setup_physical_network (self, context, project_id, host_nics, bw, vlan):
        """Serve API call to set up layer2 physial network."""
        LOG.debug(_("setting up physical network"), context=context)

        if dcns_net:
            raise Exception("A project DCNS network has already existed in DB.")

        if (len(host_nics) == 1):
            other_host_nics = self.cached_host_nics[project_id]
            if other_host_nics == None:
                self.set_cached_host_nics(project_id, host_nics)
                return 1
            elif len(other_host_nics) == 1:
                if host_nics[0] != other_host_nics[0]:
                    host_nics.append(other_host_nics[0])
                    self.cached_host_nics[project_id] = None
                else:
                    raise Exception("The same host+nic has been added to project network!")
            else:
                raise Exception("cached_host_nics has length >= 2: this should never happen!")

        # get port maping from topology.HostPortMap
        if len(host_nics) < 2:
            raise Exception("A network path must have at least two end points")
        elif len(host_nics) > 2:
            raise Exception("Multippoint network path is not supported yet")
        (srcHost, srcNic) = host_nics[0].split(':')
        source = self.hostPortMapper.lookup_port_by_host(srcHost, srcNic)
        if not source:
            raise Exception("Unknown source port for host:"+srcHost+" nic:"+srcNic)
        (dstHost, dstNic) = host_nics[1].split(':')
        destination = self.hostPortMapper.lookup_port_by_host(dstHost, dstNic)
        if not destination:
            raise Exception("Unknown destination port for host:"+dstHost+" nic:"+dstNic)

        # get path from pce.StaticPCE
        path = self.staticPCE.compute_p2p_path(source, destination)
        if not path:
            raise Exception("No routing path between "+source+" and "+destination)
        # TODO: regulate path hops format  
        path_hops =  path['hops'].split(' ')

        # setup path with l2dcn_driver
        if not project_id:
            project_id = 'unknown_project'
        gri = FLAGS.dcns_net_prefix + project_id
        ret = self.driver.setup_p2p_path(gri, path_hops, bw, vlan)

        # TODO: verify path with l2dcn_driver ?

        """ TODO: path info should have been stored in database
        """
        self.staticPCE.set_project_path(project_id, path_hops)

        # add to database upon success
        dcns_net = nova_db_api.dcns_network_create(context, {'gri':gri, 
                    'project_id':project_id, 
                    'bandwidth':bw, 
                    'vlan_range':vlan, 
                    'status':'created'})
        dcns_port_src = nova_db_api.dcns_port_add(context, project_id, 
                    {'dcns_net_id':dcns_net['id'],
                    'port_urn':source, 
                    'host_name':srcHost, 
                    'host_nic':srcNic})
        dcns_port_dst = nova_db_api.dcns_port_add(context, project_id,
                    {'dcns_net_id':dcns_net['id'],
                    'port_urn':destination, 
                    'host_name':dstHost, 
                    'host_nic':dstNic})

        return ret


    def teardown_physical_network (self, context, project_id, forced):
        """Serve API call to tear down layer2 physial network."""
        LOG.debug(_("tearing down up physical network"), context=context)
        if not project_id:
            project_id = 'unknown_project'

        dcns_net = nova_db_api.dcns_network_get(context, project_id)
        vlan = dcns_net.vlan_range

        # delete from database no matter what happens
        if forced: 
            nova_db_api.dcns_network_delete(context, project_id)

        """ TODO: path info should have been stored in database and retrieved
            upon teardown
        """
        # get path from pce.StaticPCE
        path_hops = self.staticPCE.get_project_path(project_id)
        if not path_hops:
            raise Exception("No path record for project"+project_id)

        # teardown path with l2dcn_driver
        gri = FLAGS.dcns_net_prefix + project_id
        ret = self.driver.teardown_p2p_path(gri, path_hops, vlan)

        # TODO: verify path down with l2dcn_driver ?

        # delete from database upon success
        if not forced: 
            nova_db_api.dcns_network_delete(context, project_id)

        return ret


    def get_network_info (self, context, project_id):
        """Serve API call to set up layer2 physial network."""
        if not project_id:
            project_id = 'unknown_project'
        # get info from database
        dcns_net = nova_db_api.dcns_network_get(context, project_id)
        LOG.debug(_("getting physical network info %s") % dcns_net)
        return dcns_net


    """ TODO """
    def modify_physical_network (self, context, project_id, add_host_nics, rem_host_nics, bw, vlan):
        """Serve API call to modify layer2 physial network."""
        LOG.debug(_("modifying physical network"), context=context)
        #@ get port maping from topology.HostPortMap
        #@ get old path from pce.StaticPCE
        #@ teardown path with l2dcn_driver
        #@ get new path from pce.StaticPCE
        #@ setup path with l2dcn_driver
        #@ verify both paths with l2dcn_driver ?
        #@ update database upon success
        raise NotImplementedError()
