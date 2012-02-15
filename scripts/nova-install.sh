#!/usr/bin/env bash
# assuming that nova source code is at ./nova
#
#DIR=`pwd`
CMD=$1
ARCH=$2

USE_MYSQL=1
NET_MAN=FlatDHCPManager
BRIDGE=br100
NETWORK_LABEL=public
NUM_NETWORKS=1
#DIRNAME=nova
#NOVA_DIR=$DIR/$DIRNAME
NOVA_DIR=/usr/local/nova
NETWORK_SIZE=256
USER=/home/nova

# We assume that IP address of br100 of cloud controller is 10.99.1.1
# The followings should be changed if your network settings are different from this.
CLOUD_HOST_IP=10.99.1.1
DHCP_FIXED_RANGE=10.99.1.0/24
DHCP_START_IP=10.99.1.2
DHCP_IP_NUM=$NETWORK_SIZE
GLANCE_SERVER=10.0.11.1:9292
VOLUME_SERVER=10.2.11.1
API_PASTE_INI=/etc/nova/api-paste.ini.feb-2012
# system specific info:
BRIDGE_IFACE=
BAREMETAL_DRIVER=
LIBVIRT_TYPE=
CPU_ARCH=
CONNECTION_TYPE=
XPU_ARCH=
XPUS=
MAX_NBD_DEVICES=16

if [ "$ARCH" == "gpu" ]; then
    LIBVIRT_TYPE=lxc
    CPU_ARCH=x86_64
    CONNECTION_TYPE=gpu
    XPU_ARCH="fermi"
    XPUS=4
    BRIDGE_IFACE=eth0
    USE_COW_IMAGES=False
elif [ "$ARCH" == "tilera" ]; then
    BAREMETAL_DRIVER=tilera
    LIBVIRT_TYPE=kvm
    CPU_ARCH=tilepro64
    CONNECTION_TYPE=baremetal
    XPU_ARCH=
    BRIDGE_IFACE=eth0
elif [ "$ARCH" == "uv" ]; then
    LIBVIRT_TYPE=lxc
    CPU_ARCH=x86_64
    CONNECTION_TYPE=libvirt
    BRIDGE_IFACE=eth0
else
    LIBVIRT_TYPE=kvm
    CPU_ARCH=x86_64
    CONNECTION_TYPE=libvirt
    BRIDGE_IFACE=eth0
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
echo "Cloud Host IP = " $CLOUD_HOST_IP

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
    SQL_CONN=mysql://root:$MYSQL_PASS@$CLOUD_HOST_IP/nova
else
    SQL_CONN=sqlite:///$NOVA_DIR/nova.sqlite
fi

if [ "$USE_LDAP" == 1 ]; then
    AUTH=ldapdriver.LdapDriver
else
    AUTH=dbdriver.DbDriver
fi

mkdir -p /etc/nova
mkdir -p /var/log/nova
chown -R nova:libvirt /var/log/nova
chmod 700 /var/log/nova
mkdir -p /var/run/nova
chown -R nova:libvirt /var/run/nova
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
     [ "$CMD" == "cloud-init" ]; then
    echo "writing nova.conf"
    cat >$NOVA_DIR/bin/nova.conf << NOVA_CONF_EOF
--verbose
--nodaemon
--allow_admin_api
--dhcpbridge_flagfile=$NOVA_DIR/bin/nova.conf
--dhcpbridge=$NOVA_DIR/bin/nova-dhcpbridge
--cc_host=$CLOUD_HOST_IP
--ec2_url=http://$HOST_IP:8773/services/Cloud
--rabbit_host=$CLOUD_HOST_IP
--sql_connection=$SQL_CONN
--network_manager=nova.network.manager.$NET_MAN
--libvirt_type=$LIBVIRT_TYPE
--flat_network_dhcp_start=$DHCP_START_IP
--glance_api_servers=$GLANCE_SERVER
--image_service=nova.image.glance.GlanceImageService
--scheduler_driver=nova.scheduler.arch.ArchitectureScheduler
--quota_cores=1024
--quota_gigabytes=1000
--quota_ram=1024000
--connection_type=$CONNECTION_TYPE
--cpu_arch=$CPU_ARCH
--xpu_arch=$XPU_ARCH
--periodic_interval=20
--max_nbd_devices=$MAX_NBD_DEVICES
--fixed_range=$DHCP_FIXED_RANGE
--network_size=$NETWORK_SIZE
--baremetal_driver=$BAREMETAL_DRIVER
--iscsi_ip_prefix=$VOLUME_SERVER
--service_down_time=120
--ec2_dmz_host=$CLOUD_HOST_IP
--api_paste_config=$API_PASTE_INI
--osapi_extension=nova.api.openstack.v2.contrib.standard_extensions
--osapi_extension=extensions.admin.Admin
NOVA_CONF_EOF
fi

chown nova:libvirt $NOVA_DIR/bin/nova.conf
chmod 600 $NOVA_DIR/bin/nova.conf

if [ "$CMD" == "compute-init" ]; then
	if [ "$ARCH" == "gpu" ]; then
	        echo "--xpus=$XPUS" >>$NOVA_DIR/bin/nova.conf
        fi
	if [ "$ARCH" == "tilera" ]; then
		echo "--tile_monitor=/usr/local/TileraMDE/bin/tile-monitor" >> $NOVA_DIR/bin/nova.conf
	fi
	if [ "$ARCH" == "uv" ]; then
	        echo "--extra_node_capabilities=system_type=UV" >> $NOVA_DIR/bin/nova.conf
	fi
        if [ "$LIBVIRT_TYPE" != "lxc" ]; then
		echo "--use_cow_images"  >>$NOVA_DIR/bin/nova.conf
        fi
	if [ "$ARCH" != "tilera" ]; then
		echo "--user=$USER" >>$NOVA_DIR/bin/nova.conf
        fi
fi

if [ "$CMD" == "compute-init" ] ||
     [ "$CMD" == "cloud-init" ]; then
    if [ -n "$FLAT_INTERFACE" ]; then
        echo "--flat_interface=$FLAT_INTERFACE" >>$NOVA_DIR/bin/nova.conf
        echo "--public_interface=$PUBLIC_INTERFACE" >>$NOVA_DIR/bin/nova.conf
    fi
fi

if [ "$CMD" == "compute-init" ]; then
    echo "ISCSITARGET_ENABLE=true" | sudo tee /etc/default/iscsitarget
    sudo killall libvirtd
    sudo /etc/init.d/iscsitarget restart
    sudo modprobe kvm
    sudo modprobe nbd
    #sudo service libvirtd start
    #/usr/local/sbin/libvirtd -d
    rm -rf $NOVA_DIR/instances
    mkdir -p $NOVA_DIR/instances
    rm -rf $NOVA_DIR/networks
    mkdir -p $NOVA_DIR/networks
    mkdir -p $NOVA_DIR/images
    mkdir -p $NOVA_DIR/CA
    chown -R nova:libvirt $NOVA_DIR/instances
    chown -R nova:libvirt $NOVA_DIR/networks
    chown -R nova:libvirt $NOVA_DIR/keys
    chown -R nova:libvirt $NOVA_DIR/images
    chown -R nova:libvirt $NOVA_DIR/CA
    service libvirtd restart
    service openstack-nova-compute restart
fi

if [ "$CMD" == "cloud-init" ]; then
    killall dnsmasq
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
    rm -rf $NOVA_DIR/instances
    mkdir -p $NOVA_DIR/instances
    rm -rf $NOVA_DIR/networks
    mkdir -p $NOVA_DIR/networks
    mkdir -p $NOVA_DIR/keys
    mkdir -p $NOVA_DIR/images
    mkdir -p $NOVA_DIR/CA
    chown -R nova:libvirt $NOVA_DIR/instances
    chown -R nova:libvirt $NOVA_DIR/networks
    chown -R nova:libvirt $NOVA_DIR/keys
    chown -R nova:libvirt $NOVA_DIR/images
    chown -R nova:libvirt $NOVA_DIR/CA

    if [ "$TEST" == 1 ]; then
        cd $NOVA_DIR
#          python $NOVA_DIR/run_tests.py
        cd $DIR
    fi
    # create a network
    echo "nova-manage network create"
     # old one for hpc-release
     #$NOVA_DIR/bin/nova-manage network create $DHCP_FIXED_RANGE 1 $DHCP_IP_NUM
     # new one for hpc-trunk
     #$NOVA_DIR/bin/nova-manage network create --bridge_interface=$BRIDGE_IFACE --bridge=$BRIDGE --fixed_range_v4=$DHCP_FIXED_RANGE --num_networks=$NUM_NETWORKS --network_size=$DHCP_IP_NUM --label=$NETWORK_LABEL
     $NOVA_DIR/bin/nova-manage network create --bridge_interface=$BRIDGE_IFACE --bridge=$BRIDGE --num_networks=$NUM_NETWORKS --fixed_range_v4=$DHCP_FIXED_RANGE --network_size=$DHCP_IP_NUM --label=$NETWORK_LABEL
     #$NOVA_DIR/bin/nova-manage floating create 65.114.169.172/30
     chown -R nova nova/networks
     chgrp -R libvirt nova/networks

    echo "launch nova cloud services is not done for testing"
    service openstack-nova-api restart
    service openstack-nova-network restart
    service openstack-nova-objectstore restart
    service openstack-nova-scheduler restart
fi

if [ "$CMD" == "project-init" ]; then
   # create an admin user called 'admin'
   echo "nova-manage user"
    $NOVA_DIR/bin/nova-manage user admin admin admin admin
    # create a project called 'admin' with project manager of 'admin'
   echo "nova-manage project create"
    $NOVA_DIR/bin/nova-manage project create admin admin

fi

if [ "$CMD" == "euca-init" ]; then
   # export environment variables for project 'admin' and user 'admin'
   echo "nova-manage project environment"
   mkdir -p $NOVA_DIR/creds
   rm $DIR/creds/*
   $NOVA_DIR/bin/nova-manage project zipfile admin admin $NOVA_DIR/creds/novacreds.zip
   cd $NOVA_DIR/creds
   unzip novacreds.zip
   cd ..
   chown -R nova creds
   chgrp -R libvirt creds
fi
