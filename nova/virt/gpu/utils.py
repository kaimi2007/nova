# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 University of Southern California
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
#
"""
Utility functions
   to allow GPUs to be seen inside of LXC instance.
   to manage allocation/deallocation of gpu devices to/from VM

**Related Flags**

:instance_type_extra_specs:
:dev_cgroups_path:full path of cgroup device of LXC
:gpu_dev_major_number: major number of gpu device
:gpu_dev_minor_number: start of the minor numbers of gpu device

"""
import os
import subprocess

from nova.compute import vm_states
from nova import context as nova_context
from nova import db
from nova import exception
from nova import flags
from nova.openstack.common import cfg
from nova.openstack.common import log as logging
from nova import utils

# Variables for tracking gpus available and gpus assigned
gpus_available = []
gpus_assigned = {}
num_gpus = None
extra_specs = {}

LOG = logging.getLogger(__name__)

gpu_opts = [
    cfg.ListOpt('instance_type_extra_specs',
                default=[],
                help='a list of additional capabilities corresponding to '
                'instance_type_extra_specs for this compute '
                'host to advertise. Valid entries are name=value, pairs '
                'For example, "key1:val1, key2:val2"'),
    cfg.StrOpt('dev_cgroups_path',
               default='/cgroup/devices/libvirt/lxc',
               help='Path of the LXC cgroup'),
    cfg.StrOpt('gpu_dev_major_number',
               default=195,
               help='Major number of GPU devices'),
    cfg.StrOpt('gpu_dev_minor_number',
               default=0,
               help='Start numer of minor number of GPU devices'),
    ]

FLAGS = flags.FLAGS
FLAGS.register_opts(gpu_opts)


def init_host_gpu():
    get_instance_type_extra_specs_capabilities()
    global gpus_available
    global num_gpus
    global extra_specs
    if 'gpus' in extra_specs:
        num_gpus = extra_specs['gpus']
        gpus_available = range(int(extra_specs['gpus']))


def update_status(data):
    global extra_specs
    for key in extra_specs.iterkeys():
        if 'gpus' == key:
            data['gpus'] = int(len(gpus_available))
        else:
            data[key] = extra_specs[key]
    return data


def get_instance_type_extra_specs_capabilities():
    """Return additional capabilities to advertise for this compute host."""
    global extra_specs
    for pair in FLAGS.instance_type_extra_specs:
        keyval = pair.split(':', 1)
        keyval[0] = keyval[0].strip()
        keyval[1] = keyval[1].strip()
        extra_specs[keyval[0]] = keyval[1]
    return extra_specs


def get_gpu_total():
    return len(gpus_available)

def allow_gpus(inst):
    global num_gpus
    dev_whitelist = os.path.join(FLAGS.dev_cgroups_path,
                                  inst['name'],
                                  'devices.allow')
    # Allow Nvidia Controller
    perm = 'c %d:255 rwm\n' % FLAGS.gpu_dev_major_number
    _PIPE = subprocess.PIPE
    utils.execute('tee', dev_whitelist, process_input=perm,
                  run_as_root=True)
    for i in range(int(num_gpus)):
        # Allow each gpu device
        perm = 'c 195:%d rwm\n' % (i + FLAGS.gpu_dev_minor_number)
        utils.execute('tee', dev_whitelist, process_input=perm,
                      run_as_root=True)


def assign_gpus(context, inst, lxc_container_root):
    """Assigns gpus to a specific instance"""
    global gpus_available
    global gpus_assigned
#    ctxt = nova_context.get_admin_context()
    gpus_in_meta = 0
    gpus_in_extra = 0

    env_file = lxc_container_root + '/etc/environment'
    instance_extra = db.instance_type_extra_specs_get(context,
                                                      inst['instance_type_id'])
    msg = _("instance_extra is %s .") % instance_extra
    LOG.debug(msg)
    msg = _("vcpus for this instance are %d .") % inst['vcpus']
    LOG.debug(msg)
    if 'gpus' in inst['metadata']:
        gpus_in_meta = int(inst['metadata']['gpus'])
        msg = _("gpus in metadata asked, %d .") % gpus_in_meta
        LOG.info(msg)
    if 'gpus' in instance_extra:
        gpus_in_extra = int(instance_extra['gpus'].split()[1])
        msg = _("gpus in instance_extra asked, %d .") % gpus_in_extra
        LOG.info(msg)

    if gpus_in_meta > gpus_in_extra:
        gpus_needed = gpus_in_meta
    else:
        gpus_needed = gpus_in_extra
    allow_gpus(inst)
    gpus_assigned_list = []
    if gpus_needed > len(gpus_available):
        raise Exception(_("Overcommit Error"))
    for i in range(gpus_needed):
        gpus_assigned_list.append(gpus_available.pop())
    if gpus_needed:
        gpus_assigned[inst['name']] = gpus_assigned_list
        gpus_visible = str(gpus_assigned_list).strip('[]')
        flag = "CUDA_VISIBLE_DEVICES=%s\n" % gpus_visible
        utils.execute('tee', env_file, process_input=flag,
                      run_as_root=True)


def deassign_gpus(inst):
    """Assigns gpus to a specific instance"""
    global gpus_available
    global gpus_assigned
    if inst['name'] in gpus_assigned:
        gpus_available.extend(gpus_assigned[inst['name']])
        del gpus_assigned[inst['name']]
    return


'''
The following codes are used because the main stream's code
does not work for LXC Raw image volume management.
'''


def attach_volume_lxc(self, connection_info, instance_name, \
                      mountpoint, virt_dom):
    # get device path
    data = connection_info['data']
    device_path = data['device_path']
    LOG.info(_('attach_volume: device_path(%s)') % str(device_path))

    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('attach_volume: pid(%s)') % spid)

    # get PID of the init process
    ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" % \
                       spid, shell=True, stdout=subprocess.PIPE)
    init_pid = ps_command.stdout.read()
    init_pid = str(int(init_pid))
    retcode = ps_command.wait()
    assert retcode == 0, "ps command returned %d" % retcode

    LOG.info(_('attach_volume: init_pid(%s)') % init_pid)
    # get major, minor number of the device
    s = os.stat(device_path)
    major_num = os.major(s.st_rdev)
    minor_num = os.minor(s.st_rdev)
    LOG.info(_('attach_volume: path(%s)') % device_path)
    LOG.info(_('attach_volume: major_num(%(major_num)d) ' \
               'minor_num(%(minor_num)d)') % locals())

    # allow the device
    dev_whitelist = os.path.join(FLAGS.dev_cgroups_path,
                                 instance_name,
                                 'devices.allow')
    # Allow the disk
    perm = "b %d:%d rwm" % (major_num, minor_num)
    cmd = "echo %s | sudo tee -a %s" % (perm, dev_whitelist)
    LOG.info(_('attach_volume: cmd(%s)') % cmd)
    subprocess.Popen(cmd, shell=True)

    cmd_lxc = 'sudo lxc-attach -n %s -- ' % init_pid
    # check if 'mountpoint' already exists

    LOG.info(_('attach_volume: mountpoint(%s)') % mountpoint)
    dev_key = init_pid + mountpoint
    LOG.info(_('attach_volume: dev_key(%s)') % dev_key)
    if dev_key in lxc_mounts:
        LOG.info(_('attach_volume: dev_key(%s) is already used') \
                    % dev_key)
        raise Exception(_('the same mount point(%s) is already used.')\
                    % mountpoint)

    # create device(s) for mount
    # sudo lxc-attach -n pid -- mknod -m 777
    #                 <mountpoint> b <major #> <minor #>
    cmd = '/bin/mknod -m 777 %s b %d %d '\
         % (mountpoint, major_num, minor_num)
    cmd = cmd_lxc + cmd
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    subprocess.call(cmd, shell=True)

    # create a directory for mount
    cmd = '/bin/mkdir -p /vmnt '
    cmd = cmd_lxc + cmd
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    subprocess.call(cmd, shell=True)

    # create a sub-directory for mount
    found = 0
    for n in range(0, 100):
        dir_name = '/vmnt/vol' + str(n)
        cmd = cmd_lxc + '/bin/ls ' + dir_name
        LOG.info(_('attach_volume: cmd (%s)') % cmd)
        p = subprocess.Popen(cmd, shell=True,  \
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        x = p.communicate()
        LOG.info(_('attach_volume: return x[0](%s)') % x[0])
        LOG.info(_('attach_volume: return x[1](%s)') % x[1])
        #if len(x[1]) > 5: # new  "No such file exists..."
        s = x[1].lower()
        if (len(s) > 0 and s.find('no such') >= 0):
        # new  "No such file exists..."
            cmd = cmd_lxc + ' /bin/mkdir ' + dir_name
            LOG.info(_('attach_volume: cmd (%s)') % cmd)
            subprocess.call(cmd, shell=True)
            found = 1
            break
    if found == 0:
        cmd = '/bin/rm %s ' % (mountpoint)
        cmd = cmd_lxc + cmd
        LOG.info(_('attach_volume: cmd (%s)') % cmd)
        subprocess.call(cmd, shell=True)
        raise Exception(_('cannot find mounting directories'))

    lxc_mounts[dev_key] = dir_name
    cmd = cmd_lxc + '/bin/chmod 777 ' + mountpoint
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    subprocess.call(cmd, shell=True)

    # mount
    cmd = cmd_lxc + ' /bin/mount ' + mountpoint + ' ' + dir_name
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    p = subprocess.Popen(cmd, shell=True, \
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    x = p.communicate()

    # change owner
    user = FLAGS.user
    user = user.rsplit("/")
    user = user[len(user) - 1]
    cmd = '/bin/chown %s /vmnt' % user
    cmd = cmd_lxc + cmd
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    subprocess.call(cmd, shell=True)

    cmd = '/bin/chown %s %s ' % (user, dir_name)
    cmd = cmd_lxc + cmd
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    subprocess.call(cmd, shell=True)

    cmd = cmd_lxc + " /bin/chmod 'og+w' " + ' ' + dir_name
    LOG.info(_('attach_volume: cmd (%s)') % cmd)
    subprocess.call(cmd, shell=True)


def detach_volume_lxc(self, connection_info, instance_name, \
                      mountpoint, virt_dom):
    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('detach_volume: pid(%s)') % spid)

    # get PID of the init process
    ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" \
                          % spid, shell=True, stdout=subprocess.PIPE)
    init_pid = ps_command.stdout.read()
    init_pid = str(int(init_pid))
    retcode = ps_command.wait()
    assert retcode == 0, "ps command returned %d" % retcode

    dev_key = init_pid + mountpoint
    if dev_key not in lxc_mounts:
        raise Exception(_('no such process(%(init_pid)s) or ' \
              'mount point(%(mountpoint)s)') % locals())
    dir_name = lxc_mounts[dev_key]

    LOG.info(_('detach_volume: init_pid(%s)') % init_pid)
    cmd_lxc = 'sudo lxc-attach -n %s -- ' % str(init_pid)
    cmd = cmd_lxc + ' /bin/umount ' + dir_name
    LOG.info(_('detach_volume: cmd(%s)') % cmd)
    p = subprocess.Popen(cmd, shell=True, \
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    x = p.communicate()
    cmd = cmd_lxc + ' /bin/rmdir  ' + dir_name
    LOG.info(_('detach_volume: cmd(%s)') % cmd)
    subprocess.call(cmd, shell=True)

    del lxc_mounts[dev_key]  # delete dictionary entry

    cmd = cmd_lxc + ' /bin/rm ' + mountpoint
    LOG.info(_('detach_volume: cmd(%s)') % cmd)
    subprocess.call(cmd, shell=True)
