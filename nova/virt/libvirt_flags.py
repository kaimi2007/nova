
from nova import flags
from nova import utils
#FLAGS = flags.FLAGS
flags.DECLARE('live_migration_retry_count', 'nova.compute.manager')
# TODO(vish): These flags should probably go into a shared location
flags.DEFINE_string('rescue_image_id', 'ami-rescue', 'Rescue ami image')
flags.DEFINE_string('rescue_kernel_id', 'aki-rescue', 'Rescue aki image')
flags.DEFINE_string('rescue_ramdisk_id', 'ari-rescue', 'Rescue ari image')
flags.DEFINE_string('injected_network_template',
                    utils.abspath('virt/interfaces.template'),
                    'Template file for injected network')
flags.DEFINE_string('libvirt_xml_template',
                    utils.abspath('virt/libvirt.xml.template'),
                    'Libvirt XML Template')
flags.DEFINE_string('libvirt_type',
                    'kvm',
                    'Libvirt domain type (valid options are: '
                    'kvm, qemu, uml, xen)')
flags.DEFINE_string('libvirt_uri',
                    '',
                    'Override the default libvirt URI (which is dependent'
                    ' on libvirt_type)')
flags.DEFINE_bool('allow_project_net_traffic',
                  True,
                  'Whether to allow in project network traffic')
flags.DEFINE_bool('use_cow_images',
                  True,
                  'Whether to use cow images')
flags.DEFINE_string('ajaxterm_portrange',
                    '10000-12000',
                    'Range of ports that ajaxterm should randomly try to bind')
flags.DEFINE_string('firewall_driver',
                    'nova.virt.libvirt_conn.IptablesFirewallDriver',
                    'Firewall driver (defaults to iptables)')
flags.DEFINE_string('cpuinfo_xml_template',
                    utils.abspath('virt/cpuinfo.xml.template'),
                    'CpuInfo XML Template (Used only live migration now)')
flags.DEFINE_string('live_migration_uri',
                    "qemu+tcp://%s/system",
                    'Define protocol used by live_migration feature')
flags.DEFINE_string('live_migration_flag',
                    "VIR_MIGRATE_UNDEFINE_SOURCE, VIR_MIGRATE_PEER2PEER",
                    'Define live migration behavior.')
flags.DEFINE_integer('live_migration_bandwidth', 0,
                    'Define live migration behavior')
