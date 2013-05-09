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

"""
import os
import pickle

from nova.compute import instance_types
from nova.compute import vm_states
from nova import context as nova_context
from nova import db
from nova import exception
from oslo.config import cfg
from nova.openstack.common import log as logging
from nova import utils

# Variables for tracking gpus available and gpus allocateed
gpus_available = []
gpus_allocated = {}
num_gpus = None
extra_specs = {}
gpu_usage_file = ''

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
    cfg.StrOpt('guest_tee_command',
               default='/usr/bin/tee',
               help='Full path of tee command in the LXC FS'),
    cfg.StrOpt('gpu_usage_file',
               default='gpus_allocated',
               help='Full path of the file keeping the information of gpus allocated'),
#    cfg.StrOpt('volume_auto_mount',
#               default=False,
#               help='if True, a volume is automatically mounted'
#               'inside of the guest when it is attached.'
#               'If there is no file system on the volume,'
#               'ext3 file system is created on that before'
#               'the first attachment of the volume'),
#    cfg.StrOpt('volume_mount_dir',
#               default='/vmnt',
#               help='The directory where volume is automatically mounted'
#               'as a subdirectory named vol[0-99]'),
    ]

CONF = cfg.CONF
CONF.register_opts(gpu_opts)


def num_available_gpus():
    global gpus_available
    return len(gpus_available)


def init_host_gpu(live_instance_uuids):
    global gpus_available
    global num_gpus
    global extra_specs
    global gpus_allocated
    global gpu_usage_file
    get_instance_type_extra_specs_capabilities()
    num_gpus = 0
    gpu_usage_file = CONF.state_path + '/' + CONF.gpu_usage_file
    if 'gpus' in extra_specs:
        num_gpus = extra_specs['gpus']
        gpus_available = range(int(extra_specs['gpus']))
        try:
            gpus_allocated = load_gpu_allocation()
            LOG.info("GPUs allocated = %s" % str(gpus_allocated))
            for instance_uuid, gpus in gpus_allocated.items():
                LOG.info("for instance %s" % instance_uuid)
                if instance_uuid in live_instance_uuids:
                    for allocated in gpus:
                        gpus_available.remove(allocated)
                else:
                    del gpus_allocated[instance_uuid]
                
                LOG.info("Available GPUs = %d" % num_available_gpus())
        except Exception:
            gpus_allocated = {}
            LOG.info("Available GPUs = %d" % num_available_gpus())
            pass
    save_gpu_allocation(gpus_allocated)


def update_status(data):
    global extra_specs
    global gpus_available
    for key in extra_specs.iterkeys():
        if 'gpus' == key:
            data['gpus'] = num_available_gpus()
        else:
            data[key] = extra_specs[key]
    return data


def load_gpu_allocation():
    global gpu_usage_file
    try:
        input = open(gpu_usage_file, 'r')
        data = pickle.load(input)
        input.close()
        return data
    except Exception:
        LOG.error("Failed to open GPU allocation information")
        return {}

def save_gpu_allocation(gpus_allocated):
    global gpu_usage_file
    try:
        output = open(gpu_usage_file, 'w')
        pickle.dump(gpus_allocated, output, pickle.HIGHEST_PROTOCOL)
        output.close()
    except Exception:
        LOG.error("Failed to save GPU allocation information")
        pass


def get_instance_type_extra_specs_capabilities():
    """Return additional capabilities to advertise for this compute host."""
    global extra_specs
    for pair in CONF.instance_type_extra_specs:
        keyval = pair.split(':', 1)
        keyval[0] = keyval[0].strip()
        keyval[1] = keyval[1].strip()
        extra_specs[keyval[0]] = keyval[1]
#    return extra_specs


def allow_cgroup_device(instance, perm):
    dev_whitelist = os.path.join(CONF.dev_cgroups_path,
                                 instance['name'], 'devices.allow')
    # Allow 
    utils.execute('tee', dev_whitelist, process_input=perm,
                  run_as_root=True)

def allow_gpus(inst):
    global num_gpus
    # Allow Nvidia Controller
    perm = 'c %d:255 rwm\n' % CONF.gpu_dev_major_number
    allow_cgroup_device(inst, perm)
    for i in range(int(num_gpus)):
        # Allow each gpu device
        perm = 'c %d:%d rwm\n' % (CONF.gpu_dev_major_number, i)
        allow_cgroup_device(inst, perm)

def allocate_gpus(context, instance, extra_specs, virt_dom):
    """Assigns gpus to a specific instance"""
    global gpus_available
    global gpus_allocated
    gpus_in_meta = 0
    gpus_in_extra = 0

    metadata = instance.get('metadata')
    if 'gpus' in metadata:
        gpus_in_meta = int(metadata['gpus'])
    if 'gpus' in extra_specs:
        gpus_in_extra = int(extra_specs['gpus'].split()[1])

    if gpus_in_meta > gpus_in_extra:
        gpus_needed = gpus_in_meta
    else:
        gpus_needed = gpus_in_extra

    if gpus_needed < 1:
        return

    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('allocate_gpus: pid(%s)') % spid)

    init_pid = 0
    # get PID of the init process
    try:
        out, err = utils.execute('ps', '-o', 'pid', '--ppid', spid,
                  '--noheaders', run_as_root=True,
                  check_exit_code=False)
        init_pid = str(int(out))
    except Exception:
        LOG.error(_("Failed to get pid of the container"))
        raise Exception(_("LXC container not found"))

    env_file = '/etc/environment'

    allow_gpus(instance)
    gpus_allocated_list = []
    LOG.info(_("gpus available, %d .") % num_available_gpus())
    if gpus_needed > num_available_gpus():
        raise Exception(_("Overcommit Error"))
    LOG.info(_("gpus needed - %d .") % gpus_needed)
    for i in range(gpus_needed):
        gpus_allocated_list.append(gpus_available.pop())
    if (gpus_needed > 0):
        gpus_visible = str(gpus_allocated_list).strip('[]')
        flag = "CUDA_VISIBLE_DEVICES=%s\n" % gpus_visible
        try:
            out, err = utils.execute('lxc-attach', '-n', init_pid,
                          '--', CONF.guest_tee_command, env_file, 
                          process_input=flag,
                          run_as_root=True)
            gpus_allocated[instance['uuid']] = gpus_allocated_list
            save_gpu_allocation(gpus_allocated)
        except Exception:
            LOG.info("Failed to set up GPU environment file")
            gpus_available.extend(gpus_allocated_list)
            del gpus_allocated[inst['uuid']]
            raise Exception(_("Failed to set up GPU environment file"))

def deallocate_gpus(inst):
    """Assigns gpus to a specific instance"""
    global gpus_available
    global gpus_allocated
    if inst['uuid'] in gpus_allocated:
        gpus_available.extend(gpus_allocated[inst['uuid']])
        del gpus_allocated[inst['uuid']]
    save_gpu_allocation(gpus_allocated)
    return


def _attach_lxc_volume(host_dev, disk_dev, virt_dom, instance):
    LOG.info(_('ISI: attaching LXC block device'))
    LOG.debug(_('attach_volume: host_dev(%s)') % host_dev)
    LOG.debug(_('attach_volume: disk_dev(%s)') % disk_dev)

    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('attach_volume: pid(%s)') % spid)

    out = ""
    err = ""
    init_pid = 0
    try:
        out, err = utils.execute('ps', '--format', 'pid', '--ppid', spid,
                                '--noheaders', run_as_root=True)
        init_pid = str(int(out))
    except Exception:
        LOG.error(_("Failed to get pid of the container"))
        raise Exception(_("LXC container not found"))

    LOG.info(_('attach_volume: init_pid(%s)') % init_pid)
    # get major, minor number of the device
    s = os.stat(host_dev)
    major_num = os.major(s.st_rdev)
    minor_num = os.minor(s.st_rdev)
    LOG.info(_('attach_volume: path(%s)') % host_dev)
    LOG.info(_('attach_volume: major_num(%(major_num)d) '
                   'minor_num(%(minor_num)d)') % locals())

    # allow the device
    perm = "b %d:%d rwm" % (major_num, minor_num)
    allow_cgroup_device(instance, perm)
    # create a node inside of the guest
    try:
        utils.execute('lxc-attach', '-n', init_pid, '--',
                  '/bin/mknod', '-m', '777', disk_dev,
                  'b', str(major_num), str(minor_num),
                  run_as_root=True)
    except Exception:
        LOG.error("Failed to make device in the guest")

#        if CONF.volume_auto_mount:
#            try:
#                self._mount_lxc_volume(init_pid, disk_dev, host_dev)
#            except Exception:
#                LOG.error("Failed to mount the volume in the guest")
#                utils.execute('lxc-attach', '-n', init_pid, '--',
#                          '/bin/rm', disk_dev,
#                          run_as_root=True)

def _detach_lxc_volume(lxc_device, virt_dom, instance):
    LOG.info(_('ISI: detaching LXC block device'))

    #inst_path = libvirt_utils.get_instance_path(instance)
    #container_dir = os.path.join(inst_path, 'rootfs')
    device = '/dev/' + lxc_device

    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('detach_volume: pid(%s)') % spid)

    # get PID of the init process
    try:
        out, err = utils.execute('ps', '--format', 'pid', '--ppid', 
                                spid, '--noheaders', run_as_root=True)
        init_pid = str(int(out))
    except Exception:
        LOG.error(_("Failed to get pid of the container"))
        raise Exception(_("LXC container not found"))
#     if CONF.volume_auto_mount:
#            try:
#                self._umount_lxc_volume(init_pid, device)
#            except Exception:
#                LOG.error(_("Failed to umount volume in the guest"))

    LOG.info(_('detach_volume:'))
    utils.execute('lxc-attach', '-n', init_pid, '--', '/bin/rm',
                  device, run_as_root=True)

'''
following codes are used because the main stream's code
does not work for LXC Raw image volume management.

def attach_volume_lxc(self, connection_info, instance_name,
                      mountpoint, virt_dom):
    # get device path
    data = connection_info['data']
    device_path = data['device_path']
    LOG.info(_('attach_volume: device_path(%s)') % str(device_path))

    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('attach_volume: pid(%s)') % spid)

    # get PID of the init process
    ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders" %
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
    LOG.info(_('attach_volume: major_num(%(major_num)d) '
               'minor_num(%(minor_num)d)') % locals())

    # allow the device
    dev_whitelist = os.path.join(CONF.dev_cgroups_path,
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
        LOG.info(_('attach_volume: dev_key(%s) is already used')
                    % dev_key)
        raise Exception(_('the same mount point(%s) is already used.')
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
        p = subprocess.Popen(cmd, shell=True,
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
    p = subprocess.Popen(cmd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    x = p.communicate()

    # change owner
    user = CONF.user
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


def detach_volume_lxc(self, connection_info, instance_name,
                      mountpoint, virt_dom):
    # get id of the virt_dom
    spid = str(virt_dom.ID())
    LOG.info(_('detach_volume: pid(%s)') % spid)

    # get PID of the init process
    ps_command = subprocess.Popen("ps -o pid --ppid %s --noheaders"
                          % spid, shell=True, stdout=subprocess.PIPE)
    init_pid = ps_command.stdout.read()
    init_pid = str(int(init_pid))
    retcode = ps_command.wait()
    assert retcode == 0, "ps command returned %d" % retcode

    dev_key = init_pid + mountpoint
    if dev_key not in lxc_mounts:
        raise Exception(_('no such process(%(init_pid)s) or '
              'mount point(%(mountpoint)s)') % locals())
    dir_name = lxc_mounts[dev_key]

    LOG.info(_('detach_volume: init_pid(%s)') % init_pid)
    cmd_lxc = 'sudo lxc-attach -n %s -- ' % str(init_pid)
    cmd = cmd_lxc + ' /bin/umount ' + dir_name
    LOG.info(_('detach_volume: cmd(%s)') % cmd)
    p = subprocess.Popen(cmd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    x = p.communicate()
    cmd = cmd_lxc + ' /bin/rmdir  ' + dir_name
    LOG.info(_('detach_volume: cmd(%s)') % cmd)
    subprocess.call(cmd, shell=True)

    del lxc_mounts[dev_key]  # delete dictionary entry

    cmd = cmd_lxc + ' /bin/rm ' + mountpoint
    LOG.info(_('detach_volume: cmd(%s)') % cmd)
    subprocess.call(cmd, shell=True)
'''
