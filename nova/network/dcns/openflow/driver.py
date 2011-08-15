# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    License TBD

from nova.network.dcns import driver_base 

class OpenFlowDriver(driver_base.L2DCNDriver):
    """OpenFlow driver.
       TODO
    """

    def init_host(self, host):
        raise NotImplementedError()

