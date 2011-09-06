# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 Brian Schott
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

from sqlalchemy import *
from migrate import *

from nova import api
from nova import db
from nova import log as logging


meta = MetaData()


# Table stub-definitions
# Just for the ForeignKey and column creation to succeed, these are not the
# actual definitions of instances or services.
#
instance_types = Table('instance_types', meta,
        Column('created_at', DateTime(timezone=False)),
        Column('updated_at', DateTime(timezone=False)),
        Column('deleted_at', DateTime(timezone=False)),
        Column('deleted', Boolean(create_constraint=True, name=None)),
        Column('name',
               String(length=255, convert_unicode=False, assert_unicode=None,
                      unicode_error=None, _warn_on_bytestring=False),
                      unique=True),
        Column('id', Integer(),  primary_key=True, nullable=False),
        Column('memory_mb', Integer(),  nullable=False),
        Column('vcpus', Integer(),  nullable=False),
        Column('local_gb', Integer(),  nullable=False),
        Column('flavorid', Integer(),  nullable=False, unique=True),
        Column('swap', Integer(),  nullable=False, default=0),
        Column('rxtx_quota', Integer(),  nullable=False, default=0),
        Column('rxtx_cap', Integer(),  nullable=False, default=0))

#
# New Tables
#
# None

#
# Tables to alter
#
# None

#
# Columns to add to existing tables
#

instance_types_cpu_arch = Column('cpu_arch',
                                 String(length=255,
                                        convert_unicode=False,
                                        assert_unicode=None,
                                        unicode_error=None,
                                        _warn_on_bytestring=False))

instance_types_cpu_info = Column('cpu_info',
                                 String(length=255,
                                        convert_unicode=False,
                                        assert_unicode=None,
                                        unicode_error=None,
                                        _warn_on_bytestring=False))

instance_types_xpu_arch = Column('xpu_arch',
                                 String(length=255,
                                        convert_unicode=False,
                                        assert_unicode=None,
                                        unicode_error=None,
                                        _warn_on_bytestring=False))

instance_types_xpu_info = Column('xpu_info',
                                 String(length=255,
                                        convert_unicode=False,
                                        assert_unicode=None,
                                        unicode_error=None,
                                        _warn_on_bytestring=False))

instance_types_xpus = Column('xpus', Integer())

instance_types_net_arch = Column('net_arch',
                                 String(length=255,
                                        convert_unicode=False,
                                        assert_unicode=None,
                                        unicode_error=None,
                                        _warn_on_bytestring=False))

instance_types_net_info = Column('net_info',
                                 String(length=255,
                                        convert_unicode=False,
                                        assert_unicode=None,
                                        unicode_error=None,
                                        _warn_on_bytestring=False))

instance_types_net_mbps = Column('net_mbps', Integer())


# Here are our new defaults for Tilera, Nvidia GPU, and SGI UV
# TODO, I think we should have flavor autoincrement!
INSTANCE_TYPES = {

    # x86+GPU
    # TODO: we need to identify machine readable string for xpu arch
    'cg1.small': dict(memory_mb=2048, vcpus=1, local_gb=20,
                      flavorid=100,
                      cpu_arch="x86_64", xpu_arch="fermi", xpus=1),
    'cg1.medium': dict(memory_mb=4096, vcpus=2, local_gb=40,
                       flavorid=101,
                       cpu_arch="x86_64", xpu_arch="fermi", xpus=1),
    'cg1.large': dict(memory_mb=8192, vcpus=4, local_gb=80,
                      flavorid=102,
                      cpu_arch="x86_64", xpu_arch="fermi", xpus=1,
                      net_mbps=1000),
    'cg1.xlarge': dict(memory_mb=16384, vcpus=8, local_gb=160,
                       flavorid=103,
                       cpu_arch="x86_64", xpu_arch="fermi", xpus=1,
                       net_mbps=1000),
    'cg1.2xlarge': dict(memory_mb=16384, vcpus=8, local_gb=320,
                        flavorid=104,
                        cpu_arch="x86_64", xpu_arch="fermi", xpus=2,
                        net_mbps=1000),
    'cg1.4xlarge': dict(memory_mb=22000, vcpus=8, local_gb=1690,
                        flavorid=105,
                        cpu_arch="x86_64", cpu_info='{"model":"Nehalem"}',
                        xpu_arch="fermi", xpus=2,
                        xpu_info='{"model":"Tesla 2050", "gcores":"448"}',
                        net_arch="ethernet", net_mbps=10000),

    # Shared-memory (SGI UV)
    'sh1.small': dict(memory_mb=2048, vcpus=1, local_gb=20,
                      flavorid=200,
                      cpu_arch="x86_64",
                      cpu_info='{"model":"UV"}'),
    'sh1.medium': dict(memory_mb=4096, vcpus=2, local_gb=20,
                       flavorid=201,
                       cpu_arch="x86_64",
                       cpu_info='{"model":"UV"}'),
    'sh1.large': dict(memory_mb=8192, vcpus=4, local_gb=20,
                          flavorid=202,
                      cpu_arch="x86_64",
                      cpu_info='{"model":"UV"}'),
    'sh1.xlarge': dict(memory_mb=16384, vcpus=8, local_gb=20,
                       flavorid=203,
                           cpu_arch="x86_64",
                       cpu_info='{"model":"UV"}'),
    'sh1.2xlarge': dict(memory_mb=32768, vcpus=16, local_gb=20,
                        flavorid=204,
                        cpu_arch="x86_64", cpu_info='{"model":"UV"}'),
    'sh1.4xlarge': dict(memory_mb=65536, vcpus=32, local_gb=20,
                        flavorid=205,
                        cpu_arch="x86_64", cpu_info='{"model":"UV"}'),
    'sh1.8xlarge': dict(memory_mb=131072, vcpus=64, local_gb=20,
                        flavorid=206,
                        cpu_arch="x86_64", cpu_info='{"model":"UV"}'),
    'sh1.16xlarge': dict(memory_mb=262144, vcpus=128, local_gb=20,
                         flavorid=207,
                         cpu_arch="x86_64", cpu_info='{"model":"UV"}'),
    'sh1.32xlarge': dict(memory_mb=524288, vcpus=256, local_gb=20,
                         flavorid=208,
                         cpu_arch="x86_64",
                         cpu_info='{"model":"UV"}'),

    # Tilera (reservation is currently whole board)
    't64.8x8':  dict(memory_mb=16384, vcpus=1, local_gb=1000,
                     flavorid=301,
                     cpu_arch="tile64",
                     cpu_info='{"geometry":"8x8"}'),
    'tp64.8x8': dict(memory_mb=16384, vcpus=1, local_gb=1000,
                     flavorid=302,
                     cpu_arch="tilepro64",
                     cpu_info='{"geometry":"8x8"}'),
    'tgx.4x4':  dict(memory_mb=16384, vcpus=1, local_gb=1000,
                     flavorid=303,
                     cpu_arch="tile-gx16",
                     cpu_info='{"geometry":"4x4"}'),
    'tgx.6x6':  dict(memory_mb=16384, vcpus=1, local_gb=1000,
                     flavorid=304,
                     cpu_arch="tile-gx36",
                     cpu_info='{"geometry":"6x6"}'),
    'tgx.8x8':  dict(memory_mb=16384, vcpus=1, local_gb=1000,
                     flavorid=305,
                     cpu_arch="tile-gx64",
                     cpu_info='{"geometry":"8x8"}'),
    'tgx.10x10':  dict(memory_mb=16384, vcpus=1, local_gb=1000,
                       flavorid=306,
                       cpu_arch="tile-gx100",
                       cpu_info='{"geometry":"10x10"}')
    }


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine;
    # bind migrate_engine to your metadata
    meta.bind = migrate_engine

    # Add columns to existing tables
    instance_types.create_column(instance_types_cpu_arch)
    instance_types.create_column(instance_types_cpu_info)
    instance_types.create_column(instance_types_xpu_arch)
    instance_types.create_column(instance_types_xpu_info)
    instance_types.create_column(instance_types_xpus)
    instance_types.create_column(instance_types_net_arch)
    instance_types.create_column(instance_types_net_info)
    instance_types.create_column(instance_types_net_mbps)

    try:
        i = instance_types.insert()
        for name, values in INSTANCE_TYPES.iteritems():
            i.execute({'name': name,
                       'memory_mb': values["memory_mb"],
                       'vcpus': values["vcpus"],
                       'deleted': 0,
                       'local_gb': values["local_gb"],
                       'flavorid': values["flavorid"],
                       'cpu_arch': values.get("cpu_arch", "X86_64"),
                       'cpu_info': values.get("cpu_info", ""),
                       'xpu_arch': values.get("xpu_arch", ""),
                       'xpu_info': values.get("xpu_info", ""),
                       'xpus': values.get("xpus", 0),
                       'net_arch': values.get("net_arch", ""),
                       'net_info': values.get("net_info", ""),
                       'net_mbps': values.get("net_mbps", 0)
                       })
    except Exception:
        logging.info(repr(instance_types))
        logging.exception('Exception while seeding instance_types table')
        raise


def downgrade(migrate_engine):
    meta.bind = migrate_engine

    instances.drop_column('cpu_arch')
    instances.drop_column('cpu_info')
    instances.drop_column('xpu_arch')
    instances.drop_column('xpu_info')
    instances.drop_column('xpus')
    instances.drop_column('net_arch')
    instances.drop_column('net_info')
    instances.drop_column('net_mbps')
