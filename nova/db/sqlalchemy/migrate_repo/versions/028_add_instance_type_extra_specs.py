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
            compute.instance_types.create(name="cg1.small",
                                          memory=2048,
                                          vcpus=1,
                                          local_gb=20,
                                          flavorid=100,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))
            compute.instance_types.create(name="cg1.medium",
                                          memory=4096,
                                          vcpus=2,
                                          local_gb=40,
                                          flavorid=101,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))
            compute.instance_types.create(name="cg1.large",
                                          memory=8192,
                                          vcpus=4,
                                          local_gb=80,
                                          flavorid=102,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))
            compute.instance_types.create(name="cg1.xlarge",
                                          memory=16384,
                                          vcpus=8,
                                          local_gb=160,
                                          flavorid=103,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=1))
            compute.instance_types.create(name="cg1.2xlarge",
                                          memory=16384,
                                          vcpus=8,
                                          local_gb=320,
                                          flavorid=104,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=2))
            compute.instance_types.create(name="cg1.4xlarge",
                                          memory=2200,
                                          vcpus=8,
                                          local_gb=1690,
                                          flavorid=105,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            xpu_arch="fermi",
                                            xpus=2))
            compute.instance_types.create(name="sh1.small",
                                          memory=2048,
                                          vcpus=1,
                                          local_gb=20,
                                          flavorid=200,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.medium",
                                          memory=4096,
                                          vcpus=2,
                                          local_gb=40,
                                          flavorid=201,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.large",
                                          memory=8192,
                                          vcpus=4,
                                          local_gb=80,
                                          flavorid=202,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.xlarge",
                                          memory=16384,
                                          vcpus=8,
                                          local_gb=160,
                                          flavorid=203,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.2xlarge",
                                          memory=32768,
                                          vcpus=16,
                                          local_gb=320,
                                          flavorid=204,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.4xlarge",
                                          memory=65536,
                                          vcpus=32,
                                          local_gb=320,
                                          flavorid=205,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.8xlarge",
                                          memory=1310722,
                                          vcpus=64,
                                          local_gb=500,
                                          flavorid=206,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.16xlarge",
                                          memory=262144,
                                          vcpus=128,
                                          local_gb=500,
                                          flavorid=207,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))
            compute.instance_types.create(name="sh1.32xlarge",
                                          memory=524288,
                                          vcpus=256,
                                          local_gb=1000,
                                          flavorid=208,
                                          extra_specs=dict(
                                            cpu_arch="x86_64",
                                            system_type="UV"))

            compute.instance_types.create(name="tp64.8x8",
                                          memory=16384,
                                          vcpus=1,
                                          local_gb=1000,
                                          flavorid=302,
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
