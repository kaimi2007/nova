# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import datetime

from sqlalchemy import *
from migrate import *

from nova import log as logging
from nova import utils

meta = MetaData()

# dcns_networks table to add to DB
dcns_networks = Table('dcns_networks', meta,
        Column('created_at', DateTime(timezone=False),
               default=utils.utcnow()),
        Column('updated_at', DateTime(timezone=False),
               onupdate=utils.utcnow()),
        Column('deleted_at', DateTime(timezone=False)),
        Column('deleted', Boolean(create_constraint=True, name=None)),
        Column('id', Integer, primary_key=True),
        Column('gri', String(255)),
        Column('project_id', String(255), ForeignKey('projects.id')),
        Column('bandwidth', String(255)),
        Column('vlan_range', String(255)),
        Column('start_time', DateTime, default=utils.utcnow),
        Column('end_time', DateTime),
        Column('status', String(255)),
        )

# dcns_ports table to add to DB
dcns_ports = Table('dcns_ports', meta,
        Column('created_at', DateTime(timezone=False),
               default=utils.utcnow()),
        Column('updated_at', DateTime(timezone=False),
               onupdate=utils.utcnow()),
        Column('deleted_at', DateTime(timezone=False)),
        Column('deleted', Boolean(create_constraint=True, name=None)),
        Column('id', Integer, primary_key=True),
        Column('dcns_net_id', Integer, ForeignKey('dcns_networks.id'), nullable=True),
        Column('port_urn', String(255)),
        Column('host_name', String(255)),
        Column('host_nic', String(255)),
        )

def upgrade(migrate_engine):
    meta.bind = migrate_engine

    projects = Table('projects', meta, autoload=True)

    # create dcns_networks table
    try:
        dcns_networks.create()
    except Exception:
        logging.error(_("Table |%s| not created!"), repr(dcns_networks))
        raise

    # create dcns_ports table
    try:
        dcns_ports.create()
    except Exception:
        logging.error(_("Table |%s| not created!"), repr(dcns_ports))
        raise


def downgrade(migrate_engine):
    logging.error(_("Can't downgrade without losing data"))
    raise Exception
