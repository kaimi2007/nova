import os
import pickle
import subprocess

import pprint

from nova.openstack.common import log as logging
#from nova.compute import flavors
from nova.compute import vm_states
from nova import context as nova_context
from nova import db
from nova import exception
from oslo.config import cfg
from nova import utils
from nova.network import model as network_model

# Constants for the 'vif_type' field in VIF class
#VIF_TYPE_PCI = 'pci'


LOG = logging.getLogger(__name__)

ib_opts = [
    # cfg.StrOpt('ib_bus',
    #            default=7,
    #            help='PCI Slot Number of Infiniband Card'),
    # cfg.StrOpt('ib_devices',
    #            default=4,
    #            help='The numer of PCI functions of Infiniband PCI Card'),
    cfg.StrOpt('ib_usage_file',
               default='/var/lib/nova/ibs_allocated',
               help='Filename keeping the information of ibs allocated'),
    ]

ibutil_opts = [
    cfg.StrOpt('instance_type_extra_specs',
               default='',
               help='Additional host resource specification')
]

CONF = cfg.CONF
CONF.register_opts(ib_opts)
CONF.register_opts(ibutil_opts)

class IbUtil(object):
    _instance = None
    resourceStartRange = 1

    @classmethod
    def getInstance(cls):
        if not cls._instance:
            raise Exception("IbUtil instance not yet defined. ")
        return cls._instance

    def __new__(cls, driver):
        if cls._instance is None :
            cls._instance = super(IbUtil,cls).__new__(cls)
            cls._instance.ibs_available = []
            cls._instance.ibs_allocated = {}
            cls._instance.ibs_usage_file = ''
            cls._instance.ib_devices = 0
            cls._instance.extra_specs = {}
            cls._instance.driver = driver
        return cls._instance

    def init_host_ib(self):
        live_instance_uuids = self.driver.list_instance_uuids()
        LOG.debug("live_instance_uuids = %s " % live_instance_uuids)
        #self.ibs_usage_file = os.path.join(CONF.state_path, CONF.ib_usage_file)
        self.ibs_usage_file = CONF.ib_usage_file
        LOG.debug(_("ibs_usage_file = %s") % self.ibs_usage_file)
        if not CONF.instance_type_extra_specs:
            LOG.warning( _("__init__: missing instance_type_extra_specs definition"))
            return
        if not self.extra_specs:
            LOG.debug( _("__init__: instance_type_extra_specs %s .") % CONF.instance_type_extra_specs)
            for pair in CONF.instance_type_extra_specs.split(','):
                keyval = pair.split(':', 1)
                keyval[0] = keyval[0].strip()
                keyval[1] = keyval[1].strip()
                LOG.debug(_("__init__: key value pair %s = %s") % (keyval[0], keyval[1]))
                self.extra_specs[keyval[0]] = keyval[1]
            # self.ib_bus = CONF.ib_bus
            if 'ib_devices' in self.extra_specs:
                self.ib_devices = self.extra_specs['ib_devices']
                self.ibs_available = range(self.resourceStartRange, int(self.extra_specs['ib_devices']))
                LOG.debug("ibs_available = %s " % str(self.ibs_available))
            if 'ib_bus' in self.extra_specs:
                self.ib_bus = self.extra_specs['ib_bus']
            self.ibs_allocated = self._load_ibs_allocation()
            LOG.debug("save state ibs_allocated = %s " % str(self.ibs_allocated))
            for instance_uuid, ibs in self.ibs_allocated.items():
                if instance_uuid in live_instance_uuids:
                    for allocated in ibs:
                        try:
                            self.ibs_available.remove(allocated)
                        except ValueError:
                            pass
                else:
                    del self.ibs_allocated[instance_uuid]
            LOG.debug("cleaned    ibs_allocated = %s " % str(self.ibs_allocated))
            self._save_ibs_allocation()

    def _load_ibs_allocation(self):
        try:
            input = open(self.ibs_usage_file, 'r')
            data = pickle.load(input)
            input.close()
            return data
        except Exception as e:
            LOG.error("Failed to open IB allocation information")
            LOG.debug("Exception %s " % str(e))
            return {}

    def _save_ibs_allocation(self):
        try:
            output = open(self.ibs_usage_file, 'w')
            pickle.dump(self.ibs_allocated, output, pickle.HIGHEST_PROTOCOL)
            output.close()
        except Exception as e:
            LOG.error("Failed to save IB allocation information")
            LOG.debug("Exception %s " % str(e))
            pass
    def update_status(self,data):
        for key in self.extra_specs.iterkeys():
            if 'ib_devices' == key:
                data['ib_devices'] = int(self._get_ib_total())
                LOG.debug("update_status ibs_available = %s " % str(self.ibs_available))
                LOG.debug("update_status ib_devices = %s " % str(data['ib_devices']))
            else:
                data[key] = self.extra_specs[key]
        return data

    def _get_ib_total(self):
        return len(self.ibs_available)

    def get_vif(self, context, instance):
        (bus, function) = self._assign_ibs(context, instance)
        if bus == 0 and function == 0:
            return None
        pci_vif = network_model.Passthrough.hydrate({
                "type":'pci',
                "passthrough":'pci',
                "domain":"0x0",
                "bus": hex(bus),
                "slot":"0x0",
                "function":hex(function)
                })
        return pci_vif

    def deallocate_for_instance(self, context, instance):
        self._deassign_ibs(instance)

#    def _assign_ibs(self, context, inst, instance_extra):
    def _assign_ibs(self, context, inst):
        if self.ib_devices < 1:
            return (0, 0)	# ignore
        ibs_in_meta = 0
        ibs_in_extra = 0

        # kyao
        LOG.debug("context = " + pprint.pformat(context))
        LOG.debug("inst = " + pprint.pformat(inst))


        # inst_type = instance_types.get_instance_type(inst['instance_type_id'])
        # inst_type = flavors.extract_instance_type(inst)
        inst_type = self.driver.virtapi.instance_type_get(
            nova_context.get_admin_context(read_deleted='yes'),
            inst['instance_type_id'])

        LOG.debug("inst_type = " + pprint.pformat(inst_type))
        #instance_extra = db.instance_type_extra_specs_get(context, inst_type['flavorid'])
        instance_extra = inst_type['extra_specs']
        # kyao 
        msg = _("assign_ibs: instance_type_id is %s .") \
            % str(inst['instance_type_id'])
        LOG.debug(msg)

        msg = _("assign_ibs: instance_extra is %s .") % instance_extra
        LOG.debug(msg)
        msg = _("vcpus for this instance are %d .") % inst['vcpus']
        LOG.debug(msg)
        if 'ib_devices' in inst['metadata']:
            ibs_in_meta = int(inst['metadata']['ib_devices'])
            msg = _("ib_devices in metadata asked, %d .") % ibs_in_meta
            LOG.info(msg)
        if 'ib_devices' in instance_extra:
            ibs_in_extra = int(instance_extra['ib_devices'].split()[1])
            msg = _("ibs in instance_extra asked, %d .") % ibs_in_extra
            LOG.info(msg)

        if ibs_in_meta > ibs_in_extra:
            ibs_needed = ibs_in_meta
        else:
            ibs_needed = ibs_in_extra

        if (ibs_needed == 0):
            return (0, 0)	# ignore
        elif (ibs_needed > 1):
            LOG.debug("Warning: Only 1 inifiniband NIC is given")
            ibs_needed = 1

        ibs_allocated_list = []
        function = 0
        if ibs_needed > len(self.ibs_available):
            raise Exception(_("Overcommit Error"))
        for i in range(ibs_needed):
            function = self.ibs_available.pop()
            ibs_allocated_list.append(function)
            function = function + 1
        if ibs_needed:
            self.ibs_allocated[inst['uuid']] = ibs_allocated_list
            LOG.debug("ibs_assign: %s" % str(self.ibs_allocated))
        assert function > 0, "SRIOV function number must be non-zero but (%d)" \
                % function
        self._save_ibs_allocation()
        return (int(self.ib_bus), function)

    def _deassign_ibs(self, inst):
        """Assigns ibs to a specific instance"""

        if self.ib_devices < 1:
            return	# ignore
        LOG.debug("deassign_ibs: before: ibs_allocated: %s" % str(self.ibs_allocated))
        if inst['uuid'] in self.ibs_allocated:
            self.ibs_available.extend(self.ibs_allocated[inst['uuid']])
            LOG.debug("dkang: deassign IB (%s)" % str(self.ibs_allocated[inst['uuid']]))
            del self.ibs_allocated[inst['uuid']]
            LOG.debug("deassign_ibs: after: ibs_allocated: %s" % str(self.ibs_allocated))
        return

        
