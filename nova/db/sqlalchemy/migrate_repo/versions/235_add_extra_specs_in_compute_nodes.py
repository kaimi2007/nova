# Copyright 2013 OpenStack Foundation
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

from sqlalchemy import Column, Text

from nova.db.sqlalchemy import api as db
from nova.db.sqlalchemy import utils


def upgrade(migrate_engine):
    compute_nodes = utils.get_table(migrate_engine, 'compute_nodes')
    extra_specs = Column('extra_specs', Text)
    compute_nodes.create_column(extra_specs)
    shadow_compute_nodes = utils.get_table(migrate_engine,
            db._SHADOW_TABLE_PREFIX + 'compute_nodes')
    extra_specs = Column('extra_specs', Text)
    shadow_compute_nodes.create_column(extra_specs)


def downgrade(migrate_engine):
    compute_nodes = utils.get_table(migrate_engine, 'compute_nodes')
    compute_nodes.drop_column('extra_specs')
    shadow_compute_nodes = utils.get_table(migrate_engine,
            db._SHADOW_TABLE_PREFIX + 'compute_nodes')
    shadow_compute_nodes.drop_column('extra_specs')
