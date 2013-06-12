#!/bin/bash

source helper.sh

cp /etc/glance/glance-api.conf.bkp /etc/glance/glance-api.conf
cp /etc/glance/glance-registry.conf.bkp /etc/glance/glance-registry.conf
cp /etc/nova/api-paste.ini.bkp /etc/nova/api-paste.ini
cp /usr/local/nova/examples/keystone/default_catalog.templates /etc/keystone/default_catalog.templates
cp /usr/local/nova/nova-install-hpc-folsom.sh.bkp /usr/local/nova/nova-install-hpc-folsom.sh

cp -r /etc/sysconfig/network-scripts/ /etc/sysconfig/network-scripts-old/
rm -rf /etc/sysconfig/network-scripts/
cp -r /etc/sysconfig/network-scripts-bkp/ /etc/sysconfig/network-scripts/

ifconfig br100 down

echo "removing any leftover glance images..."
rm -rf /var/lib/glance/images/*
rm -rf userkey.pem
rm -rf install.log
echo "Removing any leftover nova instances..."
rm -rf /var/lib/nova/instances/_base/*
rm -rf /var/lib/nova/instances/instance-*
echo "Removing old certification files..."
rm -rf pk.pem
rm -rf cacert.pem
rm -rf cert.pem
service network restart