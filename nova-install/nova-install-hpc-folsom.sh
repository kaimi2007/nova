#!/usr/bin/env bash
#
# nova-install.sh
# Dong In "David" Kang
# dkang@isi.edu
# March, 8, 2012
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
USE_MYSQL=1
MYSQL_PASS=nova
NET_MAN=FlatDHCPManager
BRIDGE=br100
NETWORK_LABEL=public
NUM_NETWORKS=1
#DIRNAME=nova
#NOVA_DIR=$DIR/$DIRNAME
NOVA_DIR=/usr/local/nova
NOVA_CONF=/etc/nova/nova.conf-dummy
NOVA_VAR_LIB=$NOVA_DIR
NOVA_VAR_RUN=/var/run/nova
NETWORK_SIZE=65536
USER=/home/nova
CGROUPS_PATH=/cgroup/devices/libvirt/lxc
# We assume that IP address of br100 of cloud controller is 10.99.0.1
# The followings should be changed if your network settings are different from this.
# Arbitrary value of DHCP_START_IP other than x.x.x.2 doesn't seem to work as of this release.
#NOVA_API_server_IP_address=10.99.0.1
#Glance_server_IP_address=10.99.0.1
#Volume_server_IP_address=10.99.0.1
#Keystone_server_IP_address=10.99.0.1
NOVA_API_server_IP_address=10.10.0.1
Glance_server_IP_address=10.10.0.1
Volume_server_IP_address=10.10.0.1
Keystone_server_IP_address=10.10.0.1
MySQL_server_IP_address=10.10.0.1

DHCP_FIXED_RANGE=10.99.0.0/16
DHCP_START_IP=10.99.0.2
DHCP_IP_NUM=$NETWORK_SIZE
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
    GPU_ARCH="fermi"
    GPUS=4
    USE_COW_IMAGES=False
elif [ "$ARCH" == "tilera" ]; then
    BAREMETAL_DRIVER=tilera
    LIBVIRT_TYPE=kvm
    CPU_ARCH=tilepro64
    CONNECTION_TYPE=baremetal
    GPU_ARCH=
elif [ "$ARCH" == "uv" ]; then
    LIBVIRT_TYPE=kvm
    CPU_ARCH=x86_64
    CONNECTION_TYPE=libvirt
else
    LIBVIRT_TYPE=kvm
    CPU_ARCH=x86_64
    CONNECTION_TYPE=libvirt
fi
FLAT_INTERFACE=$BRIDGE_IFACE
PUBLIC_INTERFACE=$BRIDGE
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
USE_MYSQL=${USE_MYSQL:-0}
MYSQL_PASS=${MYSQL_PASS:-nova}
TEST=${TEST:-0}
USE_LDAP=${USE_LDAP:-0}
LIBVIRT_TYPE=${LIBVIRT_TYPE:-qemu}
NET_MAN=${NET_MAN:-VlanManager}
# NOTE(vish): If you are using FlatDHCP on multiple hosts, set the interface
#             below but make sure that the interface doesn't already have an
#             ip or you risk breaking things.
#FLAT_INTERFACE=$BRIDGE_IFACE
if [ "$USE_MYSQL" == 1 ]; then
    SQL_CONN=mysql://root:$MYSQL_PASS@${MySQL_server_IP_address}/nova
else
    SQL_CONN=sqlite:///$NOVA_DIR/nova.sqlite
fi
if [ "$USE_LDAP" == 1 ]; then
    AUTH=ldapdriver.LdapDriver
else
    AUTH=dbdriver.DbDriver
fi
#groupadd libvirt
mkdir -p /etc/nova
mkdir -p /var/log/nova
chown -R nova:nova /var/log/nova
chmod 700 /var/log/nova
mkdir -p /var/run/nova
chown -R nova:nova /var/run/nova
chmod 700 /var/log/nova
## libvirtd type need to be kvm for uv
## Here 10.1.1.0/25 must be changed according to your network configuration
if [ "$CMD" == "sys-init" ]; then
    mysqladmin -u root password nova
    mysql -uroot -pnova -e 'CREATE DATABASE nova;'
    mysql -uroot -pnova -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;"
    mysql -uroot -pnova -e "SET PASSWORD FOR 'root'@'%' = PASSWORD('nova');"
fi
#--flat_network_bridge=br100
#--FAKE_subdomain=ec2
#--auth_driver=nova.auth.$AUTH
#--force_dhcp_release
if [ "$CMD" == "compute-init" ] ||
     [ "$CMD" == "cloud-init" ] ||
     [ "$CMD" == "single-init" ]; then
    echo "writing nova.conf"
    cat > $NOVA_CONF << NOVA_CONF_EOF
[DEFAULT]
verbose=True
nodaemon=True
allow_admin_api=True
dhcpbridge_flagfile= $NOVA_CONF
dhcpbridge=$NOVA_DIR/bin/nova-dhcpbridge
cc_host=$NOVA_API_server_IP_address
ec2_url=http://$NOVA_API_server_IP_address:8773/services/Cloud
rabbit_host=$NOVA_API_server_IP_address
sql_connection=$SQL_CONN
network_manager=nova.network.manager.$NET_MAN
libvirt_type=$LIBVIRT_TYPE
flat_network_dhcp_start=$DHCP_START_IP
glance_api_servers=$Glance_server_IP_address:9292
image_service=nova.image.glance.GlanceImageService
scheduler_driver=nova.scheduler.filter_scheduler.FilterScheduler
quota_cores=$QUOTA_CORES
quota_gigabytes=$QUOTA_GIGABYTES
quota_ram=$QUOTA_RAM
quota_volumes=$QUOTA_VOLUMES
connection_type=$CONNECTION_TYPE
periodic_interval=$PERIODIC_INTERVAL
max_nbd_devices=$MAX_NBD_DEVICES
fixed_range=$DHCP_FIXED_RANGE
network_size=$NETWORK_SIZE
baremetal_driver=$BAREMETAL_DRIVER
iscsi_ip_address=$Volume_server_IP_address
service_down_time=$DOWN_TIME
ec2_dmz_host=$NOVA_API_server_IP_address
api_paste_config=$API_PASTE_INI
osapi_extension=nova.api.openstack.v2.contrib.standard_extensions
osapi_extension=extensions.admin.Admin
iscsi_helper=tgtadm
state_path=$NOVA_DIR
lock_path=$NOVA_DIR
ca_path=$NOVA_DIR/CA
keys_path=$NOVA_DIR/keys
images_path=$NOVA_DIR/images
buckets_path=$NOVA_DIR/buckets
instances_path=$NOVA_DIR/instances
networks_path=$NOVA_DIR/networks
auth_strategy=keystone
ec2_private_dns_show_ip=True
bvirt_use_virtio_for_bridges=True
NOVA_CONF_EOF
fi
#--keystone_ec2_url=http://$Keystone_server_IP_address:5000/v2.0/ec2tokens
INSTANCE_TYPE_EXTRA_SPECS="instance_type_extra_specs=cpu_arch:$CPU_ARCH"
chown nova:nova $NOVA_CONF
chmod 600  $NOVA_CONF
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
        if [ "$ARCH" == "gpu" ]; then
                echo "$INSTANCE_TYPE_EXTRA_SPECS, gpu_arch:$GPU_ARCH, gpus:$GPUS" >> $NOVA_CONF     
                echo "user=$USER" >>  $NOVA_CONF
        fi
        if [ "$ARCH" == "tilera" ]; then
                echo "$INSTANCE_TYPE_EXTRA_SPECS" >> $NOVA_CONF     
                echo "tile_monitor=/usr/local/TileraMDE/bin/tile-monitor" >> $NOVA_CONF
        fi
        if [ "$ARCH" == "uv" ]; then
                echo "$INSTANCE_TYPE_EXTRA_SPECS, system_type:UV" >> $NOVA_CONF     
        fi
        if [ "$ARCH" == "" ]; then
                echo "$INSTANCE_TYPE_EXTRA_SPECS" >> $NOVA_CONF     
        fi
        if [ "$LIBVIRT_TYPE" != "lxc" ]; then
                echo "use_cow_images"  >>  $NOVA_CONF
        else
                echo "dev_cgroups_path=$CGROUPS_PATH"  >>  $NOVA_CONF
        fi
fi
if [ "$CMD" == "cloud-init" ]; then 
        echo "$INSTANCE_TYPE_EXTRA_SPECS" >> $NOVA_CONF     
fi
if [ "$CMD" == "compute-init" ] ||
     [ "$CMD" == "cloud-init" ]; then
    if [ -n "$FLAT_INTERFACE" ]; then
        echo "flat_interface=$FLAT_INTERFACE" >>  $NOVA_CONF
        echo "public_interface=$PUBLIC_INTERFACE" >>  $NOVA_CONF
    fi
fi
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
    sudo killall libvirtd
#    sudo /etc/init.d/iscsitarget restart
    sudo modprobe kvm
    sudo modprobe nbd
    #sudo service libvirtd start
    #/usr/local/sbin/libvirtd -d
    rm -rf $NOVA_VAR_LIB/instances
    mkdir -p $NOVA_VAR_LIB/instances
    rm -rf $NOVA_VAR_LIB/networks
    mkdir -p $NOVA_VAR_LIB/networks
    mkdir -p $NOVA_VAR_LIB/images
    mkdir -p $NOVA_VAR_LIB/CA
    chown -R nova:nova $NOVA_VAR_LIB/instances
    chown -R nova:nova $NOVA_VAR_LIB/networks
    chown -R nova:nova $NOVA_VAR_LIB/keys
    chown -R nova:nova $NOVA_VAR_LIB/images
    chown -R nova:nova $NOVA_VAR_LIB/CA
    service libvirtd restart
fi
if [ "$CMD" == "cloud-init" ] ||
   [ "$CMD" == "single-init" ]; then
    killall dnsmasq
#    echo "ISCSITARGET_ENABLE=true" | sudo tee /etc/default/iscsitarget
#    sudo /etc/init.d/iscsitarget restart
#    screen -d -m -S nova -t nova
    sleep 1
    if [ "$USE_MYSQL" == 1 ]; then
        echo "drop and create and sync db"
        mysql -p$MYSQL_PASS -e 'DROP DATABASE nova;'
        mysql -p$MYSQL_PASS -e 'CREATE DATABASE nova;'
        $NOVA_DIR/bin/nova-manage db sync
    else
        rm $NOVA_DIR/nova.sqlite
    fi
    if [ "$USE_LDAP" == 1 ]; then
        sudo $NOVA_DIR/nova/auth/slap.sh
    fi
    rm -rf $NOVA_VAR_LIB/instances
    mkdir -p $NOVA_VAR_LIB/instances
    rm -rf $NOVA_VAR_LIB/networks
    mkdir -p $NOVA_VAR_LIB/networks
    mkdir -p $NOVA_VAR_LIB/keys
    mkdir -p $NOVA_VAR_LIB/images
    mkdir -p $NOVA_VAR_LIB/CA
    chown -R nova:nova $NOVA_VAR_LIB/instances
    chown -R nova:nova $NOVA_VAR_LIB/networks
    chown -R nova:nova $NOVA_VAR_LIB/keys
    chown -R nova:nova $NOVA_VAR_LIB/images
    chown -R nova:nova $NOVA_VAR_LIB/CA
    if [ "$TEST" == 1 ]; then
        cd $NOVA_DIR
        cd $DIR
    fi
    # create a network
    echo "nova-manage network create"
     # old one for hpc-release
     #$NOVA_DIR/bin/nova-manage network create $DHCP_FIXED_RANGE 1 $DHCP_IP_NUM
     # new one for hpc-trunk
     #$NOVA_DIR/bin/nova-manage network create --bridge_interface=$BRIDGE_IFACE --bridge=$BRIDGE  \
     # --fixed_range_v4=$DHCP_FIXED_RANGE --num_networks=$NUM_NETWORKS \
     # --network_size=$DHCP_IP_NUM --label=$NETWORK_LABEL
     $NOVA_DIR/bin/nova-manage network create --bridge_interface=$BRIDGE_IFACE --bridge=$BRIDGE \
       --num_networks=$NUM_NETWORKS --fixed_range_v4=$DHCP_FIXED_RANGE \
       --network_size=$DHCP_IP_NUM --label=$NETWORK_LABEL
     #$NOVA_DIR/bin/nova-manage floating create 65.114.169.172/30
     chown -R nova $NOVA_VAR_LIB/networks
     chgrp -R nova $NOVA_VAR_LIB/networks
    echo "launch nova cloud services is not done for testing"
    service openstack-nova-api restart
    service openstack-nova-network restart
    service openstack-nova-objectstore restart
    service openstack-nova-scheduler restart
fi
if [ "$CMD" == "compute-init" ] ||
   [ "$CMD" == "single-init" ]; then
    service openstack-nova-compute restart
fi

rm -f /usr/bin/nova-manage
ln -s /usr/local/nova/bin/nova-manage /usr/bin/nova-manage
