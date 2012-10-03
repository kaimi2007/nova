# Copyright 2012 OpenStack LLC.
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

from sqlalchemy import Boolean, Column, DateTime, String, ForeignKey, Integer
from sqlalchemy import MetaData, String, Table

from nova import context
from nova import db

from nova.openstack.common import log as logging

LOG = logging.getLogger(__name__)

def _populate_instance_type_extra_specs(instance_types):
    try:
        instance_type_rows = list(instance_types.select().execute())
        for instance_type in instance_type_rows:
            flavorid = instance_type.flavorid
            name = instance_type.name
            if (name == 'm1.tiny') or \
                   (name == 'm1.small') or \
                   (name == 'm1.medium') or \
                   (name == 'm1.large') or \
                   (name == 'm1.xlarge'):
                    extra_specs = dict(cpu_arch='s== x86_64',
                                       hypervisor_type='s== QEMU')
            elif (name == 'cg1.small'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      gpu_arch='s== fermi',
                                      gpus='= 1',
                                      hypervisor_type='s== LXC')
            elif (name == 'cg1.medium'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      gpu_arch='s== fermi',
                                      gpus='= 2',
                                      hypervisor_type='s== LXC')
            elif (name == 'cg1.large'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      gpu_arch='s== fermi',
                                      gpus='= 3',
                                      hypervisor_type='s== LXC')
            elif (name == 'cg1.xlarge'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      gpu_arch='s== fermi',
                                      gpus='= 4',
                                      hypervisor_type='s== LXC')
            elif (name == 'cg1.2xlarge'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      gpu_arch='s== fermi',
                                      gpus='= 4',
                                      hypervisor_type='s== LXC')
            elif (name == 'cg1.4xlarge'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      gpu_arch='s== fermi',
                                      gpus='= 4',
                                      hypervisor_type='s== LXC')
            elif (name == 'sh1.small') or  \
                     (name == 'sh1.medium') or \
                     (name == 'sh1.large') or \
                     (name == 'sh1.xlarge') or \
                     (name == 'sh1.2xlarge') or \
                     (name == 'sh1.4xlarge') or \
                     (name == 'sh1.8xlarge') or \
                     (name == 'sh1.16xlarge') or \
                     (name == 'sh1.32xlarge'):
                    extra_specs = dict(
                                      cpu_arch='s== x86_64',
                                      system_type='s== UV',
                                      hypervisor_type='s== QEMU')
            elif (name == 'tp64.8x8'):
                    extra_specs = dict(
                                      cpu_arch='s== tilepro64')

            db.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          flavorid,
                                          extra_specs)

    except Exception:
        LOG.exception('Exception while creating extra_specs table')
        raise


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    instance_types = Table('instance_types', meta, autoload=True)
    is_public = Column('is_public', Boolean)

    instance_types.create_column(is_public)
    instance_types.update().values(is_public=True).execute()

    # New table.
    instance_type_projects = Table('instance_type_projects', meta,
        Column('created_at', DateTime(timezone=False)),
        Column('updated_at', DateTime(timezone=False)),
        Column('deleted_at', DateTime(timezone=False)),
        Column('deleted', Boolean(), default=False),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('instance_type_id',
                Integer,
                ForeignKey('instance_types.id'),
                nullable=False),
        Column('project_id', String(length=255)),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
        )

    try:
        instance_type_projects.create()
    except Exception:
        LOG.error(_("Table |%s| not created!"), repr(instance_type_projects))
        raise

    _populate_instance_type_extra_specs(instance_types)


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    instance_types = Table('instance_types', meta, autoload=True)
    is_public = Column('is_public', Boolean)

    instance_types.drop_column(is_public)

    instance_type_projects = Table(
            'instance_type_projects', meta, autoload=True)
    instance_type_projects.drop()
