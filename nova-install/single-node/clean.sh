#!/bin/bash

source helper.sh

echo "removing any leftover glance images..."
rm -rf /var/lib/glance/images/*
rm -rf userkey.pem
rm -rf install.log
echo "Removing any leftover nova instances..."
rm -rf /var/lib/nova/instances/_base/*
rm -rf /var/lib/nova/instances/instance-*
rm -rf /var/lib/nova/instances/-*-
echo "Removing old certification files..."
rm -rf pk.pem
rm -rf cacert.pem
rm -rf cert.pem

echo "Removing Log Files..."
rm -rf /var/log/keystone/
rm -rf /var/log/nova/
rm -rf /var/log/glance/