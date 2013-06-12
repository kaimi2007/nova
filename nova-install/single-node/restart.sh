#!/bin/bash

# NOVA
echo "Restarting NOVA services"
service openstack-nova-conductor restart
service openstack-nova-api restart
service openstack-nova-network restart
service openstack-nova-scheduler restart
service openstack-nova-cert restart
service openstack-nova-compute restart
service openstack-nova-objectstore restart


# Keystone+Glance
echo "Restarting Keystone + Glance Services"
service openstack-keystone restart
service openstack-glance-api restart
service openstack-glance-registry restart


# Cinder
echo "Restarting Cinder Services"
service openstack-cinder-api restart
service openstack-cinder-scheduler restart
service openstack-cinder-volume restart