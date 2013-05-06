#!/usr/bin/env bash
#
# nova-install.sh
# Dong In "David" Kang
# dkang@isi.edu
# Oct, 8, 2012
#
# (c) 2012 USC/ISI
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
NETWORK_SIZE=65536
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
DHCP_FIXED_RANGE=10.99.0.0/16
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
    COMPUTE_DRIVER=gpu.GPULibvirtDriver
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
#if [ "$CMD" == "sys-init" ]; then
#    mysqladmin -u root password nova
#    mysql -uroot -pnova -e 'CREATE DATABASE nova;'
#    mysql -uroot -pnova -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;"
#    mysql -uroot -pnova -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;"
#    mysql -uroot -pnova -e "SET PASSWORD FOR 'root'@'%' = PASSWORD('nova');"
#fi
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
verbose=True
allow_resize_to_same_host=True
compute_scheduler_driver=nova.scheduler.filter_scheduler.FilterScheduler
dhcpbridge_flagfile= $NOVA_CONF
fixed_range=$DHCP_FIXED_RANGE
network_size=$NETWORK_SIZE
network_manager=nova.network.manager.$NET_MAN
osapi_compute_extension=nova.api.openstack.compute.contrib.standard_extensions
my_ip=$HOST_IP
sql_connection=$SQL_CONN
libvirt_type=$LIBVIRT_TYPE
instance_name_template=instance-%08x
api_paste_config=/etc/nova/api-paste.ini 
image_service=nova.image.glance.GlanceImageService
ec2_dmz_host=$NOVA_API_server_IP_address
rabbit_host=$NOVA_API_server_IP_address
glance_api_servers=$Glance_server_IP_address:9292
auth_strategy=keystone
keystone_ec2_url=http://$Keystone_server_IP_address:5000/v2.0/ec2tokens
multi_host=False
send_arp_for_ha=True
logging_context_format_string=%(asctime)s %(levelname)s %(name)s [%(request_id)s %(user_name)s %(project_name)s] %(instance)s%(message)s
compute_driver=$COMPUTE_DRIVER
quota_cores=$QUOTA_CORES
quota_gigabytes=$QUOTA_GIGABYTES
quota_ram=$QUOTA_RAM
quota_volumes=$QUOTA_VOLUMES
periodic_interval=$PERIODIC_INTERVAL
max_nbd_devices=$MAX_NBD_DEVICES
libvirt_use_virtio_for_bridges=True
volume_name_template=volume-%s
iscsi_ip_address=$Volume_server_IP_address
iscsi_helper=tgtadm
service_down_time=$DOWN_TIME
ec2_private_dns_show_ip=True
instance_type_extra_specs=$EXTRA_SPECS
rootwrap_config=/etc/nova/rootwrap.conf
fixed_ip_disassociate_timeout=600
force_dhcp_release=False
public_interface=$PUBLIC_INTERFACE
vlan_interface=$VLAN_INTERFACE
pybasedir=/usr
instances_path=/var/lib/nova/instances
networks_path=/var/lib/nova/networks
ca_path=/var/lib/nova/CA
states_path=/var/lib/nova
lock_path=/var/lib/nova
buckets_path=/var/lib/nova/buckets
logdir=/var/log/nova
volumes_dir=/var/lib/nova/volumes
keys_path=/var/lib/nova/keys
NOVA_CONF_EOF
fi
chown nova:nova $NOVA_CONF
chmod 600  $NOVA_CONF
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
        if [ "$ARCH" == "gpu" ]; then
                echo "user=$USER" >>  $NOVA_CONF
                echo "use_cow_images=False" >>  $NOVA_CONF
        fi
        if [ "$ARCH" == "tilera" ]; then
                echo "tile_monitor=/usr/local/TileraMDE/bin/tile-monitor" >> $NOVA_CONF
        fi
        if [ "$LIBVIRT_TYPE" == "lxc" ]; then
                echo "dev_cgroups_path=$CGROUPS_PATH"  >>  $NOVA_CONF
        fi
fi
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
##    echo "ISCSITARGET_ENABLE=true" | sudo tee /etc/default/iscsitarget
##    sudo /etc/init.d/iscsitarget restart
##    screen -d -m -S nova -t nova
    sleep 1
    #mysqladmin -u root password $MYSQL_ROOT_PASS
    # mysql -u$MYSQL_ROOT_USR -p$MYSQL_ROOT_PASS -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;"
    # mysql -u$MYSQL_ROOT_USR -p$MYSQL_ROOT_PASS -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;"

    # mysql -u$MYSQL_ROOT_USR -p$MYSQL_ROOT_PASS -e 'DROP DATABASE nova;' -h ${MySQL_Nova_IP_address}
    # mysql -u$MYSQL_ROOT_USR -p$MYSQL_ROOT_PASS -e 'CREATE DATABASE nova;' -h ${MySQL_Nova_IP_address}

    #echo "MySQL nova user creation"
    #mysql -uroot -p$MYSQL_ROOT_PASS -e "CREATE USER '$MYSQL_NOVA_USR'@'%' IDENTIFIED BY '$MYSQL_NOVA_PASS';"
    #mysql -uroot -p$MYSQL_ROOT_PASS -e "CREATE USER '$MYSQL_NOVA_USR'@'localhost' IDENTIFIED BY '$MYSQL_NOVA_PASS';"
    #mysql -uroot -p$MYSQL_ROOT_PASS -e "GRANT ALL PRIVILEGES ON nova.* TO '$MYSQL_NOVA_USR'@'%' WITH GRANT OPTION;"
    #mysql -uroot -p$MYSQL_ROOT_PASS -e "GRANT ALL PRIVILEGES ON nova.* TO '$MYSQL_NOVA_USR'@'localhost' WITH GRANT OPTION;"

    #echo "drop and create and sync db, if this is first trial, please ignore error message of 'database doesn't exist'"
    #mysql -u$MYSQL_ROOT_USR -p$MYSQL_ROOT_PASS -e 'DROP DATABASE nova;' 
    #mysql -u$MYSQL_ROOT_USR -p$MYSQL_ROOT_PASS -e 'CREATE DATABASE nova;' 


    nova-manage db sync

    echo "nova-manage network create"
    nova-manage network create --bridge_interface=$BRIDGE_IFACE --bridge=$BRIDGE \
       --num_networks=$NUM_NETWORKS --fixed_range_v4=$DHCP_FIXED_RANGE \
       --network_size=$DHCP_IP_NUM --label=$NETWORK_LABEL
    service nova-api restart
    service nova-network restart
    service nova-objectstore restart
    service nova-scheduler restart
    service nova-cert restart
fi
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
       echo "start nova-compute"
      service nova-compute restart
fi

if [ "$CMD" == "volume-init" ]; then
      service tgtd restart
      service nova-volume restart
fi
