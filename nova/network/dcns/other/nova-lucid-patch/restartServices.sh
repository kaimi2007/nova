#!/bin/sh
service nova-api restart
service nova-network restart
service nova-objectstore restart
service nova-scheduler restart
service nova-compute restart

