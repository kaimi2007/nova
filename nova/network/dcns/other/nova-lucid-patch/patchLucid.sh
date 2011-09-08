#!/bin/su
# patch for 2011.2-0ubuntu0ppa1~lucid1

echo "Patching Nova code 2011.2-0ubuntu0ppa1~lucid1..."
echo

cp nova.flags.py /usr/lib/pymodules/python2.6/nova/flags.py
cp nova.network.manager.py /usr/lib/pymodules/python2.6/nova/network/manager.py
cp nova.db.api.py /usr/lib/pymodules/python2.6/nova/db/api.py
cp nova.db.sqlalchemy.api.py /usr/lib/pymodules/python2.6/nova/db/sqlalchemy/api.py
cp nova.db.sqlalchemy.models.py /usr/lib/pymodules/python2.6/nova/db/sqlalchemy/models.py
cp nova.db.sqlalchemy.migrate_repo.versions.015_dcns.py /usr/lib/pymodules/python2.6/nova/db/sqlalchemy/migrate_repo/versions/015_dcns.py
cp -rf dcns/  /usr/lib/pymodules/python2.6/nova/network/dcns

cp dcns/other/nova-dcns /usr/bin/nova-dcns
cp dcns/other/init.nova-dcns.conf /etc/init/nova-dcns.conf
cp dcns/other/nova-dcns.conf /etc/nova/nova-dcns.conf
cp dcns/other/dcns_host_port_map.yaml.sample /etc/nova/dcns_host_port_map.yaml
cp dcns/other/dcns_static_routes.yaml.sample /etc/nova/dcns_static_routes.yaml
cp dcns/cli.py /usr/bin/dcns-cli

nova-manage db sync

echo
echo "Do not forget to edit /etc/nova/dcns_host_port_map.yaml and /etc/nova/dcns_static_routes.yaml"
echo
echo "Then run ./restartServices.sh (for compute node, run: service nova-compute restart)"
echo
echo " ... To access openflow controller over SSH, make sure you can login to the"
echo " ... controller host passwordless as 'root' from 'nova' user on this host."
echo
