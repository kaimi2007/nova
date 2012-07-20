from nova.openstack.common import cfg
from nova import log as logging
from nova import utils
from nova import flags

from nova.virt.baremetal import physical_states

import os
import stat
import subprocess
import time
import tempfile

opts = [
    cfg.StrOpt('tile_monitor',
               default='/usr/local/TileraMDE/bin/tile-monitor',
               help='Tilera command line program for Bare-metal driver')
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(opts)

LOG = logging.getLogger(__name__)

def get_power_manager(phy_host, **kwargs):
    pm = Pdu(address=phy_host['pm_address'],
              host_id=phy_host['id'])
    return pm


class PduError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message

    def __str__(self):
        return "%s: %s" % (self.status, self.message)


class Pdu:

    def __init__(self, address=None, host_id=None):
        if address == None:
            raise PduError, (-1, "address is None")
        if host_id == None:
            raise PduError, (-1, "host_id is None")
        self._address = address
        self._host_id = host_id

    def _exec_status(self):
        LOG.debug(_("Before ping to the bare-metal node"))
        tile_output = "/tftpboot/tile_output_" + str(self._host_id)
        grep_cmd = ("ping -c1 " + self._address + " | grep Unreachable > " +
                    tile_output)
        subprocess.Popen(grep_cmd, shell=True)
        self.sleep_mgr(5)
        file = open(tile_output, "r")
        out = file.readline().find("Unreachable")
        utils.execute('sudo', 'rm', tile_output)
        return out
    
    def activate_node(self):
        self._power_off()
        state = self._power_on()
        return state
    
    def reboot_node(self):
        self._power_off()
        state = self._power_on()
        return state

    def deactivate_node(self):
        state = self._power_off()
        return state
    
    def _power_mgr(self, mode):
        """
        Changes power state of the given node.

        According to the mode (1-ON, 2-OFF, 3-REBOOT), power state can be
        changed. /tftpboot/pdu_mgr script handles power management of
        PDU (Power Distribution Unit).
        """
        if self._host_id < 5:
            pdu_num = 1
            pdu_outlet_num = self._host_id + 5
        else:
            pdu_num = 2
            pdu_outlet_num = self._host_id
        path1 = "10.0.100." + str(pdu_num)
        utils.execute('/tftpboot/pdu_mgr', path1, str(pdu_outlet_num),
                      str(mode), '>>', 'pdu_output')

    def _power_on(self):
        count = 0
        while not self.is_power_on():
            count += 1
            if count > 3:
                return physical_states.ERROR
            try:
                self._power_mgr(2)
                self._power_mgr(3)
            except Exception as ex:
                LOG.exception("power_on failed", ex)
            time.sleep(5)
        return physical_states.ACTIVE

    def _power_off(self):
        count = 0
        while not self._is_power_off():
            count += 1
            if count > 3:
                return physical_states.ERROR
            try:
                self._power_mgr(2)
            except Exception as ex:
                LOG.exception("power_off failed", ex)
            time.sleep(5)
        return physical_states.DELETED

    def _power_status(self):
        out = self._exec_status()
        return out

    def _is_power_off(self):
        r = self._power_status()
        return r == -1

    def is_power_on(self):
        r = self._power_status()
        return r != -1
 
    def start_console(self, port, host_id):
        pass
 
    def stop_console(self, host_id):
        pass
 
