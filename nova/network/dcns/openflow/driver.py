# vim: tabstop=4 shiftwidth=4 softtabstop=4
#    License TBD

from nova import exception
from nova import flags
from nova import log as logging
from nova.network.dcns import driver_base 

import re

class OpenFlowDriver(driver_base.L2DCNDriver):
    """OpenFlow driver.
    """

    def init_host(self, host):
        (url_type, url_path) = FLAGS.controller_url.split(':/')
        if (url_type == 'file'):
            self.dpctl = url_path

    # execute shell command and return both exit code and text output
    def shell_execute(cmd, timeout):
        pipe = os.popen('{ ' + cmd + '; } 2>&1', 'r')
        pipe = os.popen(cmd + ' 2>&1', 'r')
        text = ''
        while timeout:
            line = pipe.read()
            text += line
            time.sleep(1)
            timeout = timeout-1
        code = pipe.close()
        if code is None: code = 0
        if text[-1:] == '\n': text = text[:-1]
        return code, text

    def setup_p2p_path(self, gri, hops, bw, vlan):
        """ Set up p2p path with hops array """
        if not self.dpctl:
            raise Excpetion("OpenFlow driver currently only uses dpctl, whose path has to be configured in nova-dcns.conf!") 
        if (len(hops) != 2):
            raise Excpetion("Malformed path hops: OpenFlow driver currently only supports p2p hops!") 
        (src_ip, src_port) = hops[0].split(":")
        (dst_ip, dst_port) = hops[1].split(":")
        if ( src_ip != dst_ip):
            raise Excpetion("Malformed path hops: hop IPs for the same swtich do not match!") 
        LOG.debug(_("setting up path for gri: %s") % gri)
        vlan_hex = "0x%04x" % vlan
        sys_cmd = self.dpctl + " add-flow " + "tcp:" + src_ip + ":6633" + "in_port=" + src_port \
            + ",dl_vlan=" + vlan_hex + "idle_timeout=0,hard_timeout=0,actions=output:" + dst_port
        result = shell_execute(sys_cmd, 3)
        # TODO: parse error msg from result and raise excpetion
        sys_cmd = self.dpctl + " add-flow " + "tcp:" + dst_ip + ":6633" + "in_port=" + dst_port \
            + ",dl_vlan=" + vlan_hex + "idle_timeout=0,hard_timeout=0,actions=output:" + src_port
        result = shell_execute(sys_cmd, 3)
        # TODO: parse error msg from result and raise excpetion
        LOG.debug(_("path committed on hops: %s") % self.get_path_hops_urn(hops))
        return 1

    def teardown_p2p_path(self, gri, hops, vlan):
        """ Tear down p2p path with hops array """
        if not self.dpctl:
            raise Excpetion("OpenFlow driver currently only uses dpctl, whose path has to be configured in nova-dcns.conf!") 
        if len(hops) != 2:
            raise Excpetion("Malformed path hops: OpenFlow driver currently only supports p2p hops!") 
        (src_ip, src_port) = hops[0].split(":")
        (dst_ip, dst_port) = hops[1].split(":")
        if src_ip != dst_ip:
            raise Excpetion("Malformed path hops: hop IPs for the same swtich do not match!") 
        LOG.debug(_("tearing down path for gri: %s") % gri)
        vlan_hex = "0x%04x" % vlan
        sys_cmd = self.dpctl + " del-flows " + "tcp:" + src_ip + ":6633" + "in_port="+src_port+",dl_vlan="+vlan_hex
        result = shell_execute(sys_cmd, 3)
        # TODO: parse error msg from result and raise excpetion
        sys_cmd = self.dpctl + " del-flows " + "tcp:" + dst_ip + ":6633" + "in_port="+dst_port+",dl_vlan="+vlan_hex
        result = shell_execute(sys_cmd, 3)
        # TODO: parse error msg from result and raise excpetion
        LOG.debug(_("path deleted on hops: %s") % self.get_path_hops_urn(hops))
        return 1

    def verify_p2p_path(self, gri, hops, vlan):
        """ Verify p2p path with hops array """
        if not self.dpctl:
            raise Excpetion("OpenFlow driver currently only uses dpctl, whose path has to be configured in nova-dcns.conf!") 
        if (len(hops) != 2):
            raise Excpetion("Malformed path hops: OpenFlow driver currently only supports p2p hops!") 
        (src_ip, src_port) = hops[0].split(":")
        (dst_ip, dst_port) = hops[1].split(":")
        if src_ip != dst_ip:
            raise Excpetion("Malformed path hops: hop IPs for the same swtich do not match!") 
        LOG.debug(_("verifying path for gri: %s") % gri)
        vlan_hex = "0x%04x" % vlan
        sys_cmd = self.dpctl + " dump-flows " + "tcp:" + src_ip + ":6633"
        result = shell_execute(sys_cmd, 3)
        vlan_hex = "0x%04x" % vlan
        pattern1 = re.compile( "in_port=" + src_port+ "[^,]*,dl_vlan="+vlan_hex+"[^,]*,actions=output:"+dst_port )
        ret = 0
        match1 = pattern1.match(result)
        if match1 == None:
            LOG.debug(_("no forward data path for hops: %s") % self.get_path_hops_urn(hops))
            ret = ret + 1
        pattern2 = re.compile( "in_port=" + dst_port+ "[^,]*,dl_vlan="+vlan_hex+"[^,]*,actions=output:"+src_port )
        match2 = pattern1.match(result)
        if match1 == None:
            LOG.debug(_("no reverse data path for hops: %s") % self.get_path_hops_urn(hops))
            ret = ret + 1
        if ret == 2:
            LOG.debug(_("path active for hops: %s") % self.get_path_hops_urn(hops))
        return ret

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

