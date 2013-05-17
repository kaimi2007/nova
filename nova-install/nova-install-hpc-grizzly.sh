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
MYSQL_NOVA_PASS=nova
Keystone_User_Nova=nova
Keystone_Password_Nova=secrete
NET_MAN=FlatDHCPManager
BRIDGE=br100
NETWORK_LABEL=public
NUM_NETWORKS=1
NOVA_CONF=/etc/nova/nova.conf
NETWORK_SIZE=256
USER=/home/nova
CGROUPS_PATH=/cgroup/devices/libvirt/lxc
# We assume that IP address of eth0 (PUBLIC_INTERFACE) of cloud controller is 10.1.1.4
# We assume that the bridge br100 is associated with eth2 (FLAT_INTERFACE).
# The followings should be changed if your network settings are different from this.
NOVA_API_server_IP_address=10.1.1.4
Rabbitmq_IP_address=$NOVA_API_server_IP_address
Glance_server_IP_address=$NOVA_API_server_IP_address
Volume_server_IP_address=$NOVA_API_server_IP_address
Keystone_server_IP_address=$NOVA_API_server_IP_address
MySQL_Nova_IP_address=$NOVA_API_server_IP_address
METADATA_HOST=$NOVA_API_server_IP_address
DHCP_FIXED_RANGE=10.111.0.0/24
DHCP_IP_NUM=$NETWORK_SIZE

PUBLIC_INTERFACE=eth0
FLAT_INTERFACE=eth2

API_PASTE_INI=/etc/nova/api-paste.ini
QUOTA_CORES=1024
QUOTA_GIGABYTES=1000
QUOTA_RAM=1024000
QUOTA_VOLUMES=100
PERIODIC_INTERVAL=20
DOWN_TIME=120
# system specific info: The followings are initialized per architecture. Default value is eth0.
BRIDGE_IFACE=$FLAT_INTERFACE
BAREMETAL_DRIVER=
GPU_ARCH=fermi
GPUS=4
MAX_NBD_DEVICES=16

echo "Cloud Host IP = " ${NOVA_API_server_IP_address}
MYSQL_ROOT_PASS=${MYSQL_ROOT_PASS:-nova}
# NOTE(vish): If you are using FlatDHCP on multiple hosts, set the interface
#             below but make sure that the interface doesn't already have an
#             ip or you risk breaking things.
SQL_CONN=mysql://$MYSQL_NOVA_USR:$MYSQL_NOVA_PASS@$MySQL_Nova_IP_address/nova

#if [ -n "$FLAT_INTERFACE" ]; then
#        echo "flat_interface=$FLAT_INTERFACE" >>  $NOVA_CONF
#        echo "flat_network_bridge=br100" >> $NOVA_CONF
#        echo "flat_network_dns=$FLAT_NETWORK_DNS" >> $NOVA_CONF
#fi
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
network_manager = nova.network.manager.FlatDHCPManager
iscsi_helper = tgtadm
rpc_backend = nova.rpc.impl_kombu
rabbit_host=$Rabbitmq_IP_address
ec2_host=$NOVA_API_server_IP_address
ec2_dmz_host=$NOVA_API_server_IP_address
glance_host=$Glance_server_IP_address
iscsi_ip_address=$Volume_server_IP_address
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
metadata_host=$METADATA_HOST
metadata_port=8775
metadata_listen=0.0.0.0
metadata_listen_port=8775
novncproxy_port=6080
novncproxy_host=$NOVA_API_server_IP_address
NOVA_CONF_EOF
fi

chown nova:nova $NOVA_CONF
chmod 600  $NOVA_CONF
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
        if [ "$ARCH" == "gpu" ]; then
		echo "sql_connection = mysql://$MYSQL_NOVA_USR:$MYSQL_NOVA_PASS@$MySQL_Nova_IP_address/nova"  >>  $NOVA_CONF
                echo "user=$USER" >>  $NOVA_CONF
                echo "use_cow_images=False" >>  $NOVA_CONF
		echo "compute_driver = gpu.GPULibvirtDriver" >> $NOVA_CONF
		echo "libvirt_type=lxc" >> $NOVA_CONF
                echo "dev_cgroups_path=$CGROUPS_PATH"  >>  $NOVA_CONF
		echo "instance_type_extra_specs = cpu_arch:x86_64, gpus:$GPUS, gpu_arch:$GPU_ARCH" >> $NOVA_CONF
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
		echo "net_config_template = /usr/lib/python2.6/site-packages/nova/virt/baremetal/net-static.ubuntu.template"  >> $NOVA_CONF
		echo "tftp_root = /tftpboot" >> $NOVA_CONF
		echo "power_manager = nova.virt.baremetal.tilera_pdu.PDU" >> $NOVA_CONF
		echo "driver = nova.virt.baremetal.tilera.TILERA" >> $NOVA_CONF
		echo "instance_type_extra_specs = cpu_arch:tilepro64" >> $NOVA_CONF
		echo "sql_connection = mysql://nova:nova@localhost/nova_bm" >> $NOVA_CONF
        elif [ "$ARCH" == "uv" ]; then
		echo "sql_connection = mysql://$MYSQL_NOVA_USR:$MYSQL_NOVA_PASS@$MySQL_Nova_IP_address/nova"  >>  $NOVA_CONF
                echo "use_cow_images=True" >>  $NOVA_CONF
		echo "compute_driver = libvirt.LibvirtDriver" >> $NOVA_CONF
		echo "libvirt_type=kvm" >> $NOVA_CONF
		echo "instance_type_extra_specs = cpu_arch:x86_64, system_type:UV" >> $NOVA_CONF
        else 
		echo "sql_connection = mysql://$MYSQL_NOVA_USR:$MYSQL_NOVA_PASS@$MySQL_Nova_IP_address/nova"  >>  $NOVA_CONF
                echo "use_cow_images=True" >>  $NOVA_CONF
		echo "compute_driver = libvirt.LibvirtDriver" >> $NOVA_CONF
		echo "libvirt_type=kvm" >> $NOVA_CONF
        fi
fi

echo "" >> $NOVA_CONF
echo "[keystone_authtoken]" >> $NOVA_CONF
echo "admin_tenant_name = service" >> $NOVA_CONF
echo "admin_user = $Keystone_User_Nova" >> $NOVA_CONF
echo "admin_password = $Keystone_Password_Nova" >> $NOVA_CONF
echo "auth_host = $Keystone_server_IP_address" >> $NOVA_CONF
echo "auth_port = 35357" >> $NOVA_CONF
echo "auth_protocol = http" >> $NOVA_CONF
echo "signing_dir = /tmp/keystone-signing-nova" >> $NOVA_CONF

if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
    sudo killall libvirtd
    sudo modprobe kvm
#    sudo modprobe nbd
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

   
    # create flavors for heterogeneous instance types 
    nova flavor-key 10 set gpus="= 1"
    nova flavor-key 10 set gpu_arch="s== fermi"

    nova flavor-create --is-public True cg1.medium 11 4096 20 2
    nova flavor-key 11 set gpus="= 1"
    nova flavor-key 11 set gpu_arch="s== fermi"
    nova flavor-create --is-public True cg1.large 12 8192 40 4
    nova flavor-key 12 set gpus="= 1"
    nova flavor-key 12 set gpu_arch="s== fermi"
    nova flavor-create --is-public True cg1.xlarge 13 8192 80 8
    nova flavor-key 13 set gpus="= 1"
    nova flavor-key 13 set gpu_arch="s== fermi"
    nova flavor-create --is-public True cg1.2xlarge 14 16384 160 8
    nova flavor-key 14 set gpus="= 2"
    nova flavor-key 14 set gpu_arch="s== fermi"
    nova flavor-create --is-public True cg1.4xlarge 15 22000 320 8
    nova flavor-key 15 set gpus="= 2"
    nova flavor-key 15 set gpu_arch="s== fermi"

    nova flavor-create --is-public True tp64.8x8 20 16218 917 64
    nova flavor-key 20 set cpu_arch="s== tilepro64"

    nova flavor-create --is-public True sh1.2xlarge 50 65536 160 16
    nova flavor-key 50 set system_type="s== UV"
    nova flavor-create --is-public True sh1.4xlarge 51 65536 160 32
    nova flavor-key 51 set system_type="s== UV"
    nova flavor-create --is-public True sh1.8xlarge 52 131072 160 64
    nova flavor-key 52 set system_type="s== UV"

fi
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
       echo "start openstack-nova-compute"
      service openstack-nova-conductor restart
      service openstack-nova-compute restart
fi

if [ "$CMD" == "volume-init" ]; then
      service tgtd restart
      service openstack-cinder-api restart
      service openstack-cinder-scheduler restart
      service openstack-cinder-volume restart
fi
