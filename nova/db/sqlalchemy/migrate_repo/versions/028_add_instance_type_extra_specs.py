# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 University of Southern California
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

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy import MetaData, String, Table
from nova import compute
from nova import log as logging
from nova import db
from nova import context

meta = MetaData()

# Just for the ForeignKey and column creation to succeed, these are not the
# actual definitions of instances or services.
instance_types = Table('instance_types', meta,
        Column('id', Integer(), primary_key=True, nullable=False),
        )

#
# New Tables
#

instance_type_extra_specs_table = Table('instance_type_extra_specs', meta,
        Column('created_at', DateTime(timezone=False)),
        Column('updated_at', DateTime(timezone=False)),
        Column('deleted_at', DateTime(timezone=False)),
        Column('deleted', Boolean(create_constraint=True, name=None)),
        Column('id', Integer(), primary_key=True, nullable=False),
        Column('instance_type_id',
               Integer(),
               ForeignKey('instance_types.id'),
               nullable=False),
        Column('key',
               String(length=255, convert_unicode=False, assert_unicode=None,
                      unicode_error=None, _warn_on_bytestring=False)),
        Column('value',
               String(length=255, convert_unicode=False, assert_unicode=None,
                      unicode_error=None, _warn_on_bytestring=False)))


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine;
    # bind migrate_engine to your metadata
    meta.bind = migrate_engine
    for table in (instance_type_extra_specs_table, ):
        try:
            table.create()
            # We're using a helper method here instead of direct table
            # manipulation
            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          1,  # m1.tiny
                                          extra_specs=dict(
                                            cpu_arch="x86_64"))
            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          2,  # m1.small
                                          extra_specs=dict(
                                            cpu_arch="x86_64"))
            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          3,  # m1.medium
                                          extra_specs=dict(
                                            cpu_arch="x86_64"))
            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          4,  # m1.large
                                          extra_specs=dict(
                                            cpu_arch="x86_64"))
            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          5,  # m1.xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          100, # cg1.small
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          101, # cg1.medium
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          102, # cg1.large
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          103, # cg1.xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          104, # cg1.2xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=2))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          105, # cg1.4xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=2))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          200, # sh1.small
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          201, # sh1.medium
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          202, # sh1.large
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          203, # sh1.xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          204, # sh1.2xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          205, # sh1.4xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          206, # sh1.8xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          207, # sh1.16xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          208, # sh1.32xlarge
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            db.api.instance_type_extra_specs_update_or_create(
                                          context.get_admin_context(),
                                          302, # tp64.8x8
                                          extra_specs=dict(
                                            cpu_arch='tilepro64'))

        except Exception:
            logging.info(repr(table))
            logging.exception('Exception while creating table')
            raise


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    for table in (instance_type_extra_specs_table, ):
        table.drop()
