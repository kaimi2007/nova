#!/usr/bin/env python 
# vim: tabstop=4 shiftwidth=4 softtabstop=4 
#    License TBD

import eventlet
eventlet.monkey_patch()
import gettext
import os
import sys

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir, 'nova', '__init__.py')):
    sys.path.insert(0, possible_topdir)

from nova import context
from nova import flags
from nova.network.dcns import api as dcns_api

FLAGS = flags.FLAGS

gettext.install('nova', unicode=1)


def create(cxt, args):
    project = args[0]
    bw = args[1]
    vlan = args[2]
    host_nics = []
    for n in range(3, len(args)):
        host_nics.append(args[n])
    print host_nics
    ret = dcns_api.API().setup_physical_network(cxt, project, host_nics, bw, vlan)
    print("setup_physical_network returns %d" % ret)


def show(cxt, args):
    project = args[0]
    net_info = dcns_api.API().get_network_info(cxt, project)
    print("get_network_info returns: %s" % net_info)


def remove(cxt, args):
    project = args[0]
    ret = dcns_api.API().teardown_physical_network(cxt, project, forced=False)
    print("teardown_physical_network returns %d" % ret)


if __name__ == "__main__":
    cxt =  context.get_admin_context()
    argv = FLAGS(sys.argv)
    argv.pop(0)
    cmd = argv.pop(0)
    calls = {
    'create': create,
    'show': show,
    'remove': remove 
    }
    print "call "+cmd
    print argv
    calls[cmd](cxt, argv)
    sys.exit(0)
"""
./bin/dcns-cli create projectA 100Mbps 101 arlg-es1:eth1 arlg-es2:eth1
./bin/dcns-cli show projectA 
./bin/dcns-cli remove projectA
"""
