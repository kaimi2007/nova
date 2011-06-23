# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 University of Southern California
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
#


def get_baremetal_nodes():
    return BareMetalNodes()


class BareMetalNodes(object):

    def find_ip_w_id(self, id):
        return "127.0.0.1"

    def deactivate_node(self, node_id):
        return []

    def get_hw_info(self, field):
        return "fake"

    def set_status(self, node_id, status):
        return 1

    def check_idle_node(self):
        """check an idle node"""
        return 0

    def get_status(self):
        pass

    def get_idle_node(self):
        """get an idle node"""
        return 0

    def free_node(self, node_id):
        return 0

    def power_mgr(self, node_id, mode):
        pass

    def network_set(self, node_ip, mac_address, ip_address):
        pass

    def check_activated(self, node_id, node_ip):
        pass

    def vmlinux_set(self, mode, node_id):
        pass

    def sleep_mgr(self, time):
        pass

    def ssh_set(self, node_ip):
        pass

    def fs_set(self, node_id, node_ip):
        pass

    def activate_node(self, node_id, node_ip, name, mac_address, \
                      ip_address):
        pass

    def get_console_output(self, console_log):
        pass

    def get_image(self, bp):
        pass

    def set_image(self, bpath, node_id):
        pass

    def init_kmsg(self):
        pass
