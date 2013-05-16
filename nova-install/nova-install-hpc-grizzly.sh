#!/usr/bin/env bash
#
# nova-install.sh
# Dong In "David" Kang
# dkang@isi.edu
# Malek Musleh
# mmusleh@isi.edu
# May, 14, 2013
#
# (c) 2013 USC/ISI
#
# This script is provided for a reference only.
# Its functional correctness is not guaranteed.
#
# Warning:
#       The variables in the head of the script must be configured according to your needs
#       It is assumed that OpenStack is installed and the binaries are found at $NOVA_DIR
#
# What it does:
#       Initializes openstack
#          nova database initialize
#          "nova.conf" file creation
#          network setup
#          start necessary services (Eg. libvirt)
#          start openstack services
#
# Assumption:
#       MySQL is running on the head node
#       RabbitMQ is running on the head node
#
# Usage:
#      1. For single node installation.
#        (sys-init must be done once.
#          If you do multiple times, it will simply fail, but do no harm.)
#        $ nova-install.sh sys-init
#        (single-init will reset database and reset the status of openstack.)
#        $ nova-install.sh single-init
#
#      2. For multi-node installation
#        2.1 For head node
#        (sys-init must be done once.
#         If you do multiple times, it will simply fail, but do no harm.)
#        $ nova-install.sh sys-init
#        (cloud-init will reset database and reset the status of openstack.)
#        (cloud-init
#        $ nova-install.sh cloud-init
#
#        2.2 For compute node
#        (ARCHITECTURE can be {gpu | tilera | uv}. If unspecified, default is x86.)
#        $ nova-install.sh compute-init $ARCHITECTURE_TYPE
#
#DIR=`pwd`
CMD=$1
ARCH=$2
MYSQL_ROOT_USR=root
MYSQL_ROOT_PASS=nova
MYSQL_NOVA_USR=nova
MYSQL_NOVA_PASS=sqlnova
NET_MAN=FlatDHCPManager
BRIDGE=br100
NETWORK_LABEL=public
NUM_NETWORKS=1
NOVA_CONF=/etc/nova/nova.conf
NETWORK_SIZE=256
USER=/home/nova
CGROUPS_PATH=/cgroup/devices/libvirt/lxc
# We assume that IP address of br100 of cloud controller is 10.99.0.1
# The followings should be changed if your network settings are different from this.
# Arbitrary value of DHCP_START_IP other than x.x.x.2 doesn't seem to work as of this release.
HOST_IP=10.99.0.1
NOVA_API_server_IP_address=10.99.0.1
Glance_server_IP_address=10.99.0.1
Volume_server_IP_address=10.99.0.1
Keystone_server_IP_address=10.99.0.1
MySQL_Nova_IP_address=10.99.0.1
DHCP_FIXED_RANGE=10.99.0.0/24
DHCP_START_IP=10.99.0.2
DHCP_IP_NUM=$NETWORK_SIZE
FLAT_NETWORK_DNS=10.99.0.1

PUBLIC_INTERFACE=eth0
FLAT_INTERFACE=eth1
VLAN_INTERFACE=$FLAT_INTERFACE

API_PASTE_INI=/etc/nova/api-paste.ini
QUOTA_CORES=1024
QUOTA_GIGABYTES=1000
QUOTA_RAM=1024000
QUOTA_VOLUMES=100
PERIODIC_INTERVAL=20
DOWN_TIME=120
# system specific info: The followings are initialized per architecture. Default value is eth0.
BRIDGE_IFACE=eth1
BAREMETAL_DRIVER=
LIBVIRT_TYPE=
CPU_ARCH=
CONNECTION_TYPE=
GPU_ARCH=
GPUS=
MAX_NBD_DEVICES=16
if [ "$ARCH" == "gpu" ]; then
    LIBVIRT_TYPE=lxc
    CPU_ARCH=x86_64
    CONNECTION_TYPE=gpu
    GPU_ARCH=fermi
    GPUS=4
    EXTRA_SPECS="cpu_arch:$CPU_ARCH, gpus:$GPUS, gpu_arch:$GPU_ARCH"
    COMPUTE_DRIVER=gpu.GPULibvirtDriver
elif [ "$ARCH" == "tilera" ]; then
    BAREMETAL_DRIVER=tilera
    LIBVIRT_TYPE=kvm
    CPU_ARCH=tilepro64
    CONNECTION_TYPE=baremetal
    EXTRA_SPECS="cpu_arch:$CPU_ARCH"
    GPU_ARCH=
    COMPUTE_DRIVER=baremetal.BareMetalDriver
elif [ "$ARCH" == "uv" ]; then
    LIBVIRT_TYPE=kvm
    CPU_ARCH=x86_64
    CONNECTION_TYPE=libvirt
    COMPUTE_DRIVER=libvirt.LibvirtDriver
    EXTRA_SPECS="cpu_arch:$CPU_ARCH, system_type:UV"
else
    LIBVIRT_TYPE=kvm
    CPU_ARCH=x86_64
    CONNECTION_TYPE=libvirt
    COMPUTE_DRIVER=gpu.GPULibvirtDriver
    EXTRA_SPECS="cpu_arch:$CPU_ARCH"
fi

# HOST_IP should be set at the IP address of br100 of the cloud controller.
# For the datacenter machines, we use 10.1.1.1 for HOST_IP.
if [ ! -n "$HOST_IP" ]; then
    # NOTE(vish): This will just get the first ip in the list, so if you
    #             have more than one eth device set up, this will fail, and
    #             you should explicitly set HOST_IP in your environment
    HOST_IP=`ifconfig  | grep -m 1 'inet addr:'| cut -d: -f2 | awk '{print $1}'`
fi
echo "Host IP = " $HOST_IP
echo "Cloud Host IP = " ${NOVA_API_server_IP_address}
MYSQL_ROOT_PASS=${MYSQL_ROOT_PASS:-nova}
# NOTE(vish): If you are using FlatDHCP on multiple hosts, set the interface
#             below but make sure that the interface doesn't already have an
#             ip or you risk breaking things.
SQL_CONN=mysql://$MYSQL_NOVA_USR:$MYSQL_NOVA_PASS@$MySQL_Nova_IP_address/nova

if [ -n "$FLAT_INTERFACE" ]; then
        echo "flat_interface=$FLAT_INTERFACE" >>  $NOVA_CONF
        echo "flat_network_bridge=br100" >> $NOVA_CONF
        echo "flat_network_dns=$FLAT_NETWORK_DNS" >> $NOVA_CONF
fi
if [ "$CMD" == "compute-init" ] ||
     [ "$CMD" == "cloud-init" ] ||
     [ "$CMD" == "volume-init" ] ||
     [ "$CMD" == "single-init" ]; then
    echo "writing nova.conf"
    cat > $NOVA_CONF << NOVA_CONF_EOF
[DEFAULT]
verbose = True
debug = True
logdir = /var/log/nova
state_path = /var/lib/nova
lock_path = /var/lib/nova/tmp
volumes_dir = /etc/nova/volumes
dhcpbridge = /usr/bin/nova-dhcpbridge
dhcpbridge_flagfile = /etc/nova/nova.conf
force_dhcp_release = False
injected_network_template = /usr/share/nova/interfaces.template
libvirt_nonblocking = True
libvirt_inject_partition = -1
network_manager = nova.network.manager.FlatDHCPManager
iscsi_helper = tgtadm
sql_connection = mysql://nova:nova@localhost/nova
rpc_backend = nova.openstack.common.rpc.impl_qpid
rootwrap_config = /etc/nova/rootwrap.conf
volume_api_class = nova.volume.cinder.API
enabled_apis = ec2,osapi_compute,metadata
auth_strategy = keystone
multi_host=False
public_interface=$PUBLIC_INTERFACE
flat_network_bridge=$BRIDGE
flat_interface=$FLAT_INTERFACE
fixed_range=$DHCP_FIXED_RANGE
network_size=$NETWORK_SIZE
dhcpbridge = /usr/bin/nova-dhcpbridge
NOVA_CONF_EOF
fi
 
chown nova:nova $NOVA_CONF
chmod 600  $NOVA_CONF
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
        if [ "$ARCH" == "gpu" ]; then
                echo "user=$USER" >>  $NOVA_CONF
                echo "use_cow_images=False" >>  $NOVA_CONF
		echo "firewall_driver = nova.virt.libvirt.firewall.IptablesFirewallDriver" >> $NOVA_CONF
		echo "compute_driver = libvirt.LibvirtDriver" >> $NOVA_CONF
		echo "libvirt_type=lxc" >> $NOVA_CONF
                echo "dev_cgroups_path=$CGROUPS_PATH"  >>  $NOVA_CONF
        elif [ "$ARCH" == "tilera" ]; then
		echo "libvirt_type=kvm" >> $NOVA_CONF
                echo "tile_monitor=/usr/local/TileraMDE/bin/tile-monitor" >> $NOVA_CONF
		echo "scheduler_host_manager = nova.scheduler.baremetal_host_manager.BaremetalHostManager" >> $NOVA_CONF
		echo "firewall_driver = nova.virt.firewall.NoopFirewallDriver" >> $NOVA_CONF
		echo "compute_driver = nova.virt.baremetal.driver.BareMetalDriver" >> $NOVA_CONF
		echo "ram_allocation_ratio = 1.0" >> $NOVA_CONF
		echo "reserved_host_memory_mb = 0" >> $NOVA_CONF
		echo "" >> $NOVA_CONF
		echo "[baremetal]" >> $NOVA_CONF
		echo "net_config_template = /usr/lib/python2.6/site-packages/nova-2013.1.a4957.gf543f34-py2.6.egg/nova/virt/baremetal/net-static.ubuntu.template" >> $NOVA_CONF
		echo "tftp_root = /tftpboot" >> $NOVA_CONF
		echo "power_manager = nova.virt.baremetal.tilera_pdu.PDU" >> $NOVA_CONF
		echo "driver = nova.virt.baremetal.tilera.TILERA" >> $NOVA_CONF
		echo "instance_type_extra_specs = cpu_arch:tilepro64" >> $NOVA_CONF
		echo "sql_connection = mysql://nova:nova@localhost/nova_bm" >> $NOVA_CONF
        else 
                echo "use_cow_images=True" >>  $NOVA_CONF
		echo "firewall_driver = nova.virt.libvirt.firewall.IptablesFirewallDriver" >> $NOVA_CONF
		echo "compute_driver = libvirt.LibvirtDriver" >> $NOVA_CONF
		echo "libvirt_type=kvm" >> $NOVA_CONF
        fi
fi

echo "" >> $NOVA_CONF
echo "[keystone_authtoken]" >> $NOVA_CONF
echo "admin_tenant_name = service" >> $NOVA_CONF
echo "admin_user = nova" >> $NOVA_CONF
echo "admin_password = nova" >> $NOVA_CONF
echo "auth_host = 127.0.0.1" >> $NOVA_CONF
echo "auth_port = 35357" >> $NOVA_CONF
echo "auth_protocol = http" >> $NOVA_CONF
echo "signing_dir = /tmp/keystone-signing-nova" >> $NOVA_CONF

if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
    sudo killall libvirtd
    sudo modprobe kvm
    sudo modprobe nbd
    service libvirtd restart
fi
if [ "$CMD" == "cloud-init" ] ||
   [ "$CMD" == "single-init" ]; then
    killall dnsmasq

    sleep 1
    nova-manage db sync

    echo "nova-manage network create"
    nova-manage network create --bridge_interface=$BRIDGE_IFACE --bridge=$BRIDGE \
       --num_networks=$NUM_NETWORKS --fixed_range_v4=$DHCP_FIXED_RANGE \
       --network_size=$DHCP_IP_NUM --label=$NETWORK_LABEL
    service openstack-nova-api restart
    service openstack-nova-network restart
    service openstack-nova-objectstore restart
    service openstack-nova-scheduler restart
    service openstack-nova-cert restart
fi
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
       echo "start openstack-nova-compute"
      service openstack-nova-compute restart
fi

if [ "$CMD" == "volume-init" ]; then
      service tgtd restart
      service openstack-cinder-api restart
      service openstack-cinder-scheduler restart
      service openstack-cinder-volume restart
fi
