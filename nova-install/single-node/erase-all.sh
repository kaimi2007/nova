#!/bin/env bash

openstack_packages="openstack-cinder-api \
 openstack-cinder-doc \
 openstack-cinder-scheduler \
 openstack-cinder-volume \
 openstack-cinder \
 openstack-glance-api \
 openstack-glance-registry \
 openstack-keystone \
 openstack-nova-api \
 openstack-nova-cert \
 openstack-nova-common \
 openstack-nova-commonopenstack-nova-compute \
 openstack-nova-compute \
 openstack-nova-console \
 openstack-nova-network \
 openstack-nova-novncproxy \
 openstack-nova-objectstore \
 openstack-nova-scheduler \
 openstack-nova-volume \
 openstack-nova \
 openstack-quantum-cisco \
 openstack-quantum-linuxbridge \
 openstack-quantum-metaplugin \
 openstack-quantum-nec \
 openstack-quantum-nicira \
 openstack-quantum-openvswitch \
 openstack-quantum-ryu \
 openstack-quantum \           
 euca2ools \
 python-cinder \
 python-cinderclient \
 python-keystone \
 python-keystoneclient \
 python-glance \
 python-nova-adminclient \
 python-nova \
 python-novaclient-doc \
 python-novaclient \
 python-quantum \
 python-quantumclient \
 quantum-dhcp-agent \
 quantum-l3-agent \
 quantum-linuxbridge-agent \
 quantum-server,
 python-sqlalchemy-migrate \
 python-migrate"

grizzly_packages='nova-install openstack-nova-network openstack-nova-conductor'
dodcs_packages='dodcs-openstack'

yum -y erase $grizzly_packages $dodcs_packages

#yum -y -q erase $openstack_packages                                                                                   
yum -y erase $openstack_packages

rm -rf /var/lib/nova /var/lib/glance /var/lib/quantum /var/lib/keystone /var/lib/cinder
rm -rf /var/log/nova /var/log/glance /var/log/quantum /var/log/keystone /var/log/cinder
rm -rf /etc/nova /etc/glance /etc/quantum /etc/keystone /etc/cinder


libvirtpackages="libvirt \
 libvirt-client \
 qemu-kvm \
 qemu-kvm-debuginfo \
 qemu-common \
 qemu-system-x86 \
 qemu-img \
 vgabios"

yum -y erase $libvirtpackages


mysql_packages="mysql-server rabbitmq-server"

yum -y erase $mysql_packages