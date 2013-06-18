#!/bin/bash

set -o errexit
# Any subsequent commands with fail will cause the shell script to exit immediately

# Turn off verbose and variable expansion
set +o verbose
set +x

# OS-install.sh
# Malek Musleh
# mmusleh@isi.edu
# May. 15, 2013
#
# (c) 2013 USC/ISI                                                         
#                                                                            
# This script is provided for a reference only.
# Its functional correctness is not guaranteed. 
# Script will either take arguments on the command line or install defaults
# Source in helper routines
source helper.sh


##### Constants

readonly BASENAME="${0##*/}"                   # name of this script for error output 
readonly LOG_FILE='install.log'  # location of script log file                                          
readonly PARAMETERS="$*"                       # all of the specified input parameters                    
readonly ROOT_UID=0                            # users with $UID 0 have root privileges                    

# Exit codes                                                           
readonly EX_OK=0       # successful termination                
readonly EX_USAGE=64   # command line usage error                         
readonly EX_OSFILE=72  # critical OS file missing            
readonly EX_NOPERM=77  # permission denied

# NewLine
declare NewLine=$'\n'

##### DEFAULT PARAMETERS
declare INSTALL_STEP
declare START_INSTALL_STEP
declare LAST_INSTALL_STEP=21
declare OS_DIST

declare VERBOSE=0
declare DEFAULT_ROOT_USER
declare DEFAULT_MYSQL_ROOT_PASSWORD
declare DEFAULT_INSTALL
declare DEFAULT_OS_INSTALL_DIR
declare CREDENTIAL_FILE
declare DEFAULT_NUM_NODES
declare DEFAULT_DODCS_SCRIPT
declare DEFAULT_VM_TYPE
declare DEFAULT_VM_RAMDISK
declare DEFAULT_VM_KERNEL
declare DEFAULT_VM_FS
declare LOCALHOST

declare DEFAULT_RHEL_ISO_NAME
declare DEFAULT_DODCS_ISO_NAME

declare DEFAULT_RHEL_ISO_PATH
declare DEFAULT_DODCS_ISO_PATH

declare DEFAULT_PUBLIC_INTERFACE
declare DEFAULT_BRIDGE
declare DEFAULT_NUM_NICS
declare DEFAULT_CC_ADDR


### Necessary global variables
declare -a INSTALL
declare -a OS_INSTALL_DIR
declare -a ADMIN
declare -a MYSQL_ROOT_PASSWORD
declare -a YOUR_ADMIN_TOKEN
declare -a NUM_NODES
declare -a CONFIG_FILE
declare -a YOUR_TOKEN # EC2 Token
declare -a VM_TYPE
declare -a VM_RAMDISK
declare -a VM_KERNEL
declare -a VM_FS

declare -a RHEL_ISO
declare -a DODCS_ISO

declare -a RHEL_REPO
declare -a DODCS_REPO

declare -a RHEL_ISO_NAME
declare -a DODCS_ISO_NAME
declare -a RHEL_ISO_PATH
declare -a DODCS_ISO_PATH

declare -a RHEL_REPO_PATH
declare -a DODCS_REPO_PATH

declare PUBLIC_INTERFACE
declare FLAT_INTERFACE
declare BRIDGE
declare CC_ADDR

declare NOVA_ADMIN_USER
declare NOVA_ADMIN_PASSWORD
declare NOVA_ADMIN_TENANT   ## Common for all services
declare MYSQL_NOVA_USER
declare MYSQL_NOVA_PASSWORD
declare NOVA_API_SERVER_IP_ADDRESS # IP address of node where the nova-api is running
declare NOVA_REGION

declare -a MYSQL_KEYSTONE_USER
declare -a MYSQL_KEYSTONE_PASSWORD
declare -a KEYSTONE_SERVER_IP_ADDRESS # IP address of node where the keystone service is running
declare KEYSTONE_PUBLIC_PORT
declare KEYSTONE_ADMIN_PORT
declare KEYSTONE_COMPUTE_PORT
declare KEYSTONE_ADMIN_USER
declare KEYSTONE_ADMIN_PASSWORD

declare MYSQL_GLANCE_USER
declare MYSQL_GLANCE_PASSWORD
declare GLANCE_ADMIN_USER
declare GLANCE_ADMIN_PASSWORD

declare MYSQL_CINDER_USER
declare MYSQL_CINDER_PASSWORD
# declare MYSQL_CINDER_TENANT
declare CINDER_ADMIN_USER
declare CINDER_ADMIN_PASSWORD


declare ADMIN_USER
declare ADMIN_PASSWORD
declare DEMO_USER
declare DEMO_PASSWORD

declare -a GLANCE_SERVER_IP_ADDRESS # IP address of node where the Glance server is running
declare -a VOLUME_SERVER_IP_ADDRESS # IP address of node where the Volume server is running
declare CINDER_SERVER_IP_ADDRESS # IP address of node where the Cinder server is running

declare -a KERNEL_NAME

# Boolean variables to mark when certain paths are complete
declare -a MYSQL_CONFIGURED=false
declare -a KEYSTONE_INSTALLED=false
declare -a CINDER_INSTALLED=false
declare -a KERNEL_INSTALLED=false
declare -a REPOS_CONFIG=true
declare DO_KERNEL_INSTALL=false

export LANG=C

# Print Script Usage
function usage() {
    cat << USAGE
Syntax
   OS-install.sh -T {type" -A {admin} -v {qemu | kvm}
   -F: Name of config-file (config.yaml)
   -K: Install Kernel Upgrade as part of Installation process
   -T: Installation type: all (single node) | controller | compute | parseonly | genec2token | geneucakey | leanmysql | fullclean | clean | backup | restore 
   -S: Start Main Installation at step number (max:22)
   -V: Verbose (print line number script is executing)
USAGE
    exit 1
}

# Function to enable echos when verbose is on
function verbose () {
    [[ ${VERBOSE:-} -eq 1 ]] && return 0 || return 1
}

# Function to just drop / delete all users from the MYSQL database
function clean_mysql() {

    echo "Cleaning All MYSQL DATABASES and Users..."
    cd ${OS_INSTALL_DIR}
    clear; python OS-config.py ${CONFIG_FILE} "clean"
    echo "DONE!"
}

# Function to do simple clean
function clean() {

    # remove images from glance  
    remove_glance_images "clean"
    remove_install_files
}

# Function to uninstall all packages / configurations / Dependencies
function clean_all() {

    local os_release=$(lsb_release -r | awk '{print $2}')
    echo "Executing clean all...will remove all databases and related packages"
    
    # remove images from glance
    remove_glance_images "clean"
    remove_install_files

    yum clean all && yum update --releasever=$os_release -y #clean meta data
    install_gnu_packages "clean"
    install_ntp "clean"
    install_yum_pri "clean"
    update_kernel "clean"
    install_openstack "clean"
    install_mysql "clean"
    config_yum_repos "clean"
    echo "Clean ALL DONE!"
}

# Function to restore original files if OS-install went wrong/errored out
function restore_original() {

    local MSG="
Restoring Original system network / openstack-related Install files \n
PLEASE BE SURE TO HAVE RAN THE BACKUP OPTION PRIOR TO INSTALL/RESTORE \n"
    echo -e ${MSG}

    set +o errexit

    local bkpext="-bkp"
    local orig="/etc/sysconfig/network-scripts"
    local bkp=${orig}$bkpext}
    local deletefile

    echo "Restoring original network-scripts folder"
    cp -r ${bkp} ${orig}

    orig="/usr/local/nova/nova-install-hpc-${OS_DIST}.sh"
    bkp=${orig}${bkpext}
    echo "restoring folsom script"
    cp -r ${folsomscriptbkp} ${folsomscript}

    orig="\/etc\/keystone\/default\_catalog\.templates"
    bkp="\/usr\/local\/nova\/examples\/keystone\/default\_catalog\.templates"
    echo "restoring keystone catalog file"
    cp ${bkp} ${orig}

    orig="\/etc\/glance\/glance\-api\.conf"
    bkp="\/etc\/glance\/glance\-api\.conf\.bkp"
    echo "restoring ${orig} file"
    cp ${bkp} ${orig}

    orig="\/etc\/glance\/glance\-registry\.conf"
    bkp="\/etc\/glance\/glance\-registry\.conf\.bkp"
    echo "restoring ${orig} file"
    cp ${bkp} ${orig}

    orig="\/etc\/nova\/api\.paste"
    bkp="\/etc\/nova\/api\.paste\.bkp"
    echo "restoring ${orig} file"
    cp ${bkp} ${orig}

    echo "removing any leftover glance images..."
    rm -rf /var/lib/glance/images/*

    echo "Removing any leftover nova instances..."
    rm -rf /var/lib/nova/instances/_base/*
    if [ "${OS_DIST}" == "folsom" ]
    then
	rm -rf /var/lib/nova/instances/instance-*
    else
	rm -rf /var/lib/nova/instances/*-*
    fi

    echo "Restoring original credential (openrc) file..."
    cp -r openrc.sample openrc

    echo "Removing old certification files..."
    deletefile="${OS_INSTALL_DIR}\/userkey.pem"
    rm -rf ${deletefile}

    deletefile="${OS_INSTALL_DIR}\/pk.pem"
    rm -rf ${deletefile}

    deletefile="${OS_INSTALL_DIR}\/cacert.pem"
    rm -rf ${deletefile}

    deletefile="${OS_INSTALL_DIR}\/cert.pem"
    rm -rf ${deletefile}

    service network restart

    echo "Done!"
    set -o errexit
}

# Function to create backups of the necessary files/folders to allow for
# easy restoring of system state
function create_backup() {

    set +o errexit
    local netfolder="/etc/sysconfig/network-scripts"
    local bkpext="-bkp"
    local netfolderbkp=${netfolder}${bkpext}
    local hpcscript="/usr/local/nova/nova-install-${OS_DIST}.sh"
    local hpcscriptbkp=${hpcscript}${bkpext}
    echo "Creating backups of necessary files ..."

    # network files
    if [ ! -e "${netfolderbkp}" ]
    then
	echo "Creating backup of network-scripts"
	cp -r ${netfolder} ${netfolderbkp}
    else
	echo "Backup of network-scripts folder: ${netfolderbkp} already exists!"
    fi

    # hpc--script backup only if it has been installed
    if [ ! -e "${hpcscriptbkp}" ] && [ -e "${hpcscript}" ]
    then
	echo "Creating ${OS_DIST}-script backup"
	cp ${hpcscript} ${hpcscriptbkp}
    elif [ ! -e "${hpcscript}" ]
    then
	echo "dodcs ${OS_DIST} has not yet been installed, no backup of it necessary"
    else
	echo "Backup of hpc-script: ${hpcscriptbkp} already exists!"
    fi
    set -o errexit
    echo "backup Done!"
}

# Process Command Line
function process_command_line() {

    echo "Processing Command Line Parameters..."
    opts="$@"

    while getopts T:N:A:P:F:K:S:V:v:hy opts
    do
	case ${opts} in
	    T)
		INSTALL=$(echo "${OPTARG}" | tr [A-Z] [a-z] )
		case ${INSTALL} in
		    all|fullclean|clean|cleanmysql|single|controller|compute|node|parseonly|genec2token|geneucakey|backup|restore)
			;;
		    *)
			usage
			;;
		esac
		;;
	    P)
		PUBLIC_INTERFACE=${OPTARG}
		;;
	    A)
		ADMIN=${OPTARG}
		;;
	    F)
		CONFIG_FILE=${OPTARG}
		;;
	    K)
		DO_KERNEL_INSTALL=true
		;;
	    S)
		INSTALL_STEP=${OPTARG}
		START_INSTALL_STEP=${INSTALL_STEP}
		;;
	    V)  PS4=':${LINENO}+'
		set -x
		set -o verbose
		VERBOSE=1
		;;
	    h)
		usage
		;;
	esac
    done
    DEFAULT_OS_INSTALL_DIR=$(pwd)
    # clean out meta data cache every time script is executed
    # to prevent strange yum/rpm problems from occuring
    yum clean all
}

# Restart all related services
function restart_services() {

    restart_glance_services
    restart_keystone_services
    restart_nova_services
}

# Restart glance services
function restart_glance_services() {

    set +o errexit
    if [ "${OS_DIST}" != "grizzly" ]
    then
	chkconfig glance-api on
	chkconfig glance-registry on
	service glance-api restart
	service glance-registry restart
    else
	chkconfig openstack-glance-api on
	chkconfig openstack-glance-registry on
	service openstack-glance-registry restart
	service openstack-glance-api restart
    fi
}

# Restart keystone service
function restart_keystone_services() {

    set +o errexit
    if [ "${OS_DIST}" != "grizzly" ]
    then
	chkconfig keystone on
	service keystone restart
    else
	chkconfig openstack-keystone on
	service openstack-keystone restart
    fi
    set -o errexit
}

# Restart NOVA services
function restart_nova_services() {

    set +o errexit
    if [ "${OS_DIST}" != "grizzly" ]
    then
	chkconfig nova-volume on
        chkconfig openstack-nova-api on
        chkconfig openstack-nova-network on
        chkconfig openstack-nova-scheduler on
        chkconfig openstack-nova-compute on

        service nova-api restart
        service nova-compute restart
        service nova-cert restart
        service nova-network restart
        service nova-scheduler restart
	service nova-volume restart
    else

        chkconfig openstack-nova-api on
        chkconfig openstack-nova-network on
        chkconfig openstack-nova-scheduler on
        chkconfig openstack-nova-compute on
	chkconfig openstack-nova-conductor on
	chkconfig openstack-cinder-api on
	chkconfig openstack-cinder-scheduler on
	chkconfig openstack-cinder-volume on

        service openstack-nova-api restart
        service openstack-nova-compute restart
        service openstack-nova-cert restart
        service openstack-nova-network restart
        service openstack-nova-scheduler restart

	service memcached restart
	service openstack-nova-conductor restart
	service openstack-cinder-api restart
	sleep 20
	service openstack-cinder-scheduler restart
	sleep 20
	service openstack-cinder-volume restart
	sleep 20
    fi

    set -o errexit

    echo "Giving some time for NOVA-services to restart..."
    sleep 35;
}

# Read in parameters indicated in config-file
function parse_config_file() {

    local text
    # make sure variable is set
    local set=(isvarset ${CONFIG_FILE})
    if [ -n "${CONFIG_FILE}" ]    
    then
	echo "Parsing CONFIG_FILE..."
	cd ${OS_INSTALL_DIR}
	text=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "INSTALL")
	echo "TEXT OF FILE"
	echo "$text"
    else
	echo "NO Config File set"
    fi
    exit 1
}

# Read in parameters indicated in config-file
function parse_configFile_defaults() {

    local text
    # make sure variable is set
    local set=(isvarset ${CONFIG_FILE})
    if [ -n "${CONFIG_FILE}" ]
    then
        echo "Parsing CONFIG_FILE..."
	OS_DIST=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "OS_DIST")
	DEFAULT_ROOT_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "ROOT_USER")
	DEFAULT_MYSQL_ROOT_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_ROOT_PASSWORD")
	CREDENTIAL_FILE=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "CREDENTIAL_FILE")
	DEFAULT_YOUR_ADMIN_TOKEN=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "TOKEN")
        DEFAULT_INSTALL=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "INSTALL")
	DEFAULT_NUM_NODES=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "NUM_NODES")
	DEFAULT_DODCS_SCRIPT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "DODCS_SCRIPT")
        IMAGE_LOC=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "IMAGE_LOC")
	DEFAULT_VM_TYPE=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "VM_TYPE")
	DEFAULT_VM_RAMDISK=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "VM_RAMDISK")
	DEFAULT_VM_KERNEL=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "VM_KERNEL")
	DEFAULT_VM_FS=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "VM_FS")
	LOCALHOST=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "LOCALHOST")
	DEFAULT_RHEL_ISO_NAME=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "RHEL_ISO_NAME")
	DEFAULT_DODCS_ISO_NAME=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "DODCS_ISO_NAME")
	RHEL_ISO_PATH=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "RHEL_ISO_PATH")
	DODCS_ISO_PATH=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "DODCS_ISO_PATH")
	DEFAULT_PUBLIC_INTERFACE=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "PUBLIC_INTERFACE")
	FLAT_INTERFACE=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "FLAT_INTERFACE")
	DEFAULT_BRIDGE=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "BRIDGE")
	DEFAULT_NUM_NICS=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "NUM_NICS")
	CC_ADDR=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "CC_ADDR")
	DEFAULT_ARCH=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "ARCH")
	DEFAULT_ETH_PORT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "PUBLIC_INTERFACE")

	DEFAULT_MYSQL_GLANCE_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_GLANCE_USER")
	DEFAULT_MYSQL_GLANCE_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_GLANCE_PASSWORD")
	GLANCE_ADMIN_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "GLANCE_ADMIN_USER")
	GLANCE_ADMIN_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "GLANCE_ADMIN_PASSWORD")
	DEFAULT_MYSQL_KEYSTONE_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_KEYSTONE_USER")
	DEFAULT_MYSQL_KEYSTONE_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_KEYSTONE_PASSWORD")
	KEYSTONE_ADMIN_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "KEYSTONE_ADMIN_USER")
	KEYSTONE_ADMIN_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "KEYSTONE_ADMIN_PASSWORD")

	KEYSTONE_PUBLIC_PORT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "KEYSTONE_PUBLIC_PORT")
	KEYSTONE_ADMIN_PORT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "KEYSTONE_ADMIN_PORT")
	KEYSTONE_COMPUTE_PORT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "KEYSTONE_COMPUTE_PORT")
	DEFAULT_NOVA_ADMIN_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "NOVA_ADMIN_USER")
	DEFAULT_NOVA_ADMIN_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "NOVA_ADMIN_PASSWORD")
	DEFAULT_NOVA_ADMIN_TENANT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "NOVA_ADMIN_TENANT")
	NOVA_REGION=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "NOVA_REGION")
	DEFAULT_GLANCE_ADMIN_USER=${DEFAULT_MYSQL_GLANCE_USER}
	MYSQL_NOVA_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_NOVA_USER")
	MYSQL_NOVA_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_NOVA_PASSWORD")

	ADMIN_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "ADMIN_USER")
	ADMIN_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "ADMIN_PASSWORD")
	DEMO_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "DEMO_USER")
	DEMO_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "DEMO_PASSWORD")


	if [ "${OS_DIST}" == "grizzly" ]
	then
	    MYSQL_CINDER_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_CINDER_USER")
	    MYSQL_CINDER_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_CINDER_PASSWORD")
	    MYSQL_CINDER_ADMIN_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_CINDER_ADMIN_PASSWORD")
	    ## MYSQL_CINDER_TENANT=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "MYSQL_CINDER_TENANT")
	    CINDER_ADMIN_USER=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "CINDER_ADMIN_USER")
	    CINDER_ADMIN_PASSWORD=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "CINDER_ADMIN_PASSWORD")
	    CINDER_SERVER_IP_ADDRESS=$(python OS-config.py ${CONFIG_FILE} "get_config_value" "CINDER_SERVER_IP_ADDRESS")
	fi
   
    else
	echo "NO Config File set"
	error_exit ""
    fi
}

#check command line / default parameters
function check_params() {

    # If config-file specified read parameters from there
    local set=(isvarset ${CONFIG_FILE} = "false")

    check_install_vars
    check_network_vars
    check_mysql_vars
    check_keystone_vars
    check_glance_vars
    check_nova_vars

    set +o errexit
    if [ "${OS_DIST}" != "grizzly" ]
    then
	check_volume_vars
    else
	check_cinder_vars
    fi
}

# Check main installation parameters/variables
function check_install_vars() {

    (isvarset ${INSTALL} ) && set ${INSTALL:=${DEFAULT_INSTALL}}
    (isvarset ${OS_INSTALL_DIR} ) && set ${OS_INSTALL_DIR:=${DEFAULT_OS_INSTALL_DIR}}
    (isvarset ${INSTALL_STEP} ) && set ${INSTALL_STEP:=4}
    START_INSTALL_STEP=${INSTALL_STEP}
    (isvarset ${OS_DIST} ) && set ${OS_DIST:="grizzly"}
    (isvarset ${ADMIN} ) && set ${ADMIN:=${DEFAULT_ROOT_USER}}
    (isvarset ${NUM_NODES} ) && set ${NUM_NODES:=${DEFAULT_NUM_NODES}}
    (isvarset ${NUM_NICS} ) && set ${NUM_NICS:=${DEFAULT_NUM_NICS}}
    #(isvarset ${NUM_NICS} ) && set ${NUM_NICS:=$(get_num_nics) }
    (isvarset ${YOUR_ADMIN_TOKEN} ) && set ${YOUR_ADMIN_TOKEN:=${DEFAULT_YOUR_ADMIN_TOKEN}}
    (isvarset ${DODCS_SCRIPT} ) && set ${DODCS_SCRIPT:=${DEFAULT_DODCS_SCRIPT}}
    (isvarset ${ARCH} ) && set ${ARCH:=${DEFAULT_ARCH}}
    
    # VM Image
    (isvarset ${VM_TYPE} ) && set ${VM_TYPE:=${DEFAULT_VM_TYPE}}
    (isvarset ${VM_RAMDISK} ) && set ${VM_RAMDISK:=${DEFAULT_VM_RAMDISK}}
    (isvarset ${VM_KERNEL} ) && set ${VM_KERNEL:=${DEFAULT_VM_KERNEL}}
    (isvarset ${VM_FS} ) && set ${VM_FS:=${DEFAULT_VM_FS}}

    # ISO Images
    (isvarset ${RHEL_ISO_PATH} ) && set ${RHEL_ISO_PATH:=${DEFAULT_RHEL_ISO_PATH}}
    (isvarset ${DODCS_ISO_PATH} ) && set ${DODCS_ISO_PATH:=${DEFAULT_DODCS_ISO_PATH}}

    (isvarset ${RHEL_ISO_NAME} ) && set ${RHEL_ISO_NAME:=${DEFAULT_RHEL_ISO_NAME}}
    (isvarset ${DODCS_ISO_NAME} ) && set ${DODCS_ISO_NAME:=${DEFAULT_DODCS_ISO_NAME}}

    (isvarset ${RHEL_ISO} ) && set ${RHEL_ISO:=${RHEL_ISO_PATH}"/"${DEFAULT_RHEL_ISO_NAME}}
    (isvarset ${DODCS_ISO} ) && set ${DODCS_ISO:=${DODCS_ISO_PATH}"/"${DEFAULT_DODCS_ISO_NAME}}


    if [ "${INSTALL_STEP}" -gt "${LAST_INSTALL_STEP}" ]
    then
	echo "ERROR: INSTALL STEP: ${INSTALL_STEP} > LAST_STEP: ${LAST_INSTALL_STEP}"
	exit 1
    fi
}

# Check Network config parameters
function check_network_vars() {

    (isvarset ${PUBLIC_INTERFACE} ) && set ${PUBLIC_INTERFACE:=${DEFAULT_PUBLIC_INTERFACE}}
    (isvarset ${BRIDGE} ) && set ${BRIDGE:=${DEFAULT_BRIDGE}}
    (isvarset ${CC_ADDR} ) && set ${CC_ADDR:=${DEFAULT_CC_ADDR}}
    (isvarset ${ETH_PORT} ) && set ${ETH_PORT:=${DEFAULT_ETH_PORT}}
}

# Check MYSQL config parameters
function check_mysql_vars() {

    (isvarset ${MYSQL_ROOT_USER} ) && set ${MYSQL_ROOT_USER:=${DEFAULT_ROOT_USER}}
    (isvarset ${MYSQL_ROOT_PASSWORD} ) && set ${MYSQL_ROOT_PASSWORD:=${DEFAULT_MYSQL_ROOT_PASSWORD}}
}

# Check NOVA config parameters
function check_nova_vars() {

    (isvarset ${MYSQL_NOVA_USER} ) && set ${MYSQL_NOVA_USER:=${DEFAULT_MYSQL_NOVA_USER}}
    (isvarset ${MYSQL_NOVA_PASSWORD} ) && set ${MYSQL_NOVA_PASSWORD:=${DEFAULT_MYSQL_NOVA_PASSWORD}}
    (isvarset ${NOVA_ADMIN_USER} ) && set ${NOVA_ADMIN_USER:=${DEFAULT_NOVA_ADMIN_USER}}
    (isvarset ${NOVA_ADMIN_PASSWORD} ) && set ${NOVA_ADMIN_PASSWORD:=${DEFAULT_NOVA_ADMIN_PASSWORD}}
    (isvarset ${NOVA_ADMIN_TENANT} ) && set ${NOVA_ADMIN_TENANT:=${DEFAULT_NOVA_ADMIN_TENANT}}
    (isvarset ${NOVA_API_SERVER_IP_ADDRESS} ) && set ${NOVA_API_SERVER_IP_ADDRESS:=${LOCALHOST}}
    (isvarset ${NOVA_REGION} ) && set ${NOVA_REGION:=RegionOne}
}

function check_glance_vars() {

    (isvarset ${MYSQL_GLANCE_USER} ) && set ${MYSQL_GLANCE_USER:=${DEFAULT_MYSQL_GLANCE_USER}}
    (isvarset ${MYSQL_GLANCE_PASSWORD} ) && set ${MYSQL_GLANCE_PASSWORD:=${DEFAULT_MYSQL_GLANCE_PASSWORD}}
    (isvarset ${GLANCE_ADMIN_USER} ) && set ${GLANCE_ADMIN_USER:=${DEFAULT_GLANCE_ADMIN_USER}}
    (isvarset ${GLANCE_ADMIN_PASSWORD} ) && set ${GLANCE_ADMIN_PASSWORD:=${MYSQL_GLANCE_PASSWORD}}
    (isvarset ${GLANCE_SERVER_IP_ADDRESS} ) && set ${GLANCE_SERVER_IP_ADDRESS:=${LOCALHOST}}
}

function check_cinder_vars() {

    (isvarset ${MYSQL_CINDER_USER} ) && set ${MYSQL_CINDER_USER:=${DEFAULT_MYSQL_CINDER_USER}}
    (isvarset ${MYSQL_CINDER_PASSWORD} ) && set ${MYSQL_CINDER_PASSWORD:=${DEFAULT_MYSQL_CINDER_PASSWORD}}
    (isvarset ${CINDER_ADMIN_USER} ) && set ${CINDER_ADMIN_USER:=${MYSQL_CINDER_USER}}
    (isvarset ${CINDER_ADMIN_PASSWORD} ) && set ${CINDER_ADMIN_PASSWORD:=${DEFAULT_MYSQL_ADMIN_PASSWORD}}
    (isvarset ${CINDER_SERVER_IP_ADDRESS} ) && set ${CINDER_SERVER_IP_ADDRESS:=${LOCALHOST}}

}

function check_volume_vars() {

    (isvarset ${VOLUME_SERVER_IP_ADDRESS} ) && set ${VOLUME_SERVER_IP_ADDRESS:=${LOCALHOST}}
}

# Verification Stage
function verify_install() {

    echo "Verifying Install"

cat << CONFIG
dodcs-openstack will be installed with these options:

----------------------------------------------

ConfigFile: ${CONFIG_FILE}
Release Version: ${OS_DIST}
Installation: ${INSTALL}
Install Dir: ${OS_INSTALL_DIR}
Install Step: ${INSTALL_STEP} (only applies to 'all' installation mode)
Install Kernel Flag: ${DO_KERNEL_INSTALL}
Verbose: ${VERBOSE}
Crendetials File: ${CREDENTIAL_FILE}
Admin Token: ${YOUR_ADMIN_TOKEN}
Num Nodes: ${NUM_NODES}
HPC-Script: ${DODCS_SCRIPT}
VM Image Location: ${IMAGE_LOC}
Architecture: ${ARCH}

VM Type: ${VM_TYPE} 
VM ramdisk: ${VM_RAMDISK}
VM kernel: ${VM_KERNEL}
VM FS: ${VM_FS}

RHEL_ISO_PATH: ${RHEL_ISO_PATH}
RHEL_ISO_NAME: ${RHEL_ISO_NAME}
RHEL ISO: ${RHEL_ISO}

DODCS_ISO_PATH: ${DODCS_ISO_PATH}
DODCS_ISO_NAME: ${DODCS_ISO_NAME}
DODCS ISO: ${DODCS_ISO}

----- Network Parameters  -----
Public Interface: ${PUBLIC_INTERFACE}
Flat Interface: ${FLAT_INTERFACE}
Cloud IP Address: ${CC_ADDR}
Num NICS: ${NUM_NICS}
ETH Port: ${ETH_PORT}
Bridge: ${BRIDGE}

-----   MySQL Parameters  -----
MySQL Root User: ${MYSQL_ROOT_USER}
MySQL Root Password: ${MYSQL_ROOT_PASSWORD}

----- KeyStone Parameters -----
KeyStone MySQL User: ${MYSQL_KEYSTONE_USER}
KeyStone MySQL Password: ${MYSQL_KEYSTONE_PASSWORD}
Keystone keystone User: ${KEYSTONE_ADMIN_USER}
Keystone keystone Password: ${KEYSTONE_ADMIN_PASSWORD}
Keystone_server_IP_address: ${KEYSTONE_SERVER_IP_ADDRESS}
Keystone public_port: ${KEYSTONE_PUBLIC_PORT}
Keystone admin_port: ${KEYSTONE_ADMIN_PORT}
Keystone compute_port: ${KEYSTONE_COMPUTE_PORT}

----- Glance Parameters   -----
Glance MySQL User: ${MYSQL_GLANCE_USER}
Glance MySQL Password: ${MYSQL_GLANCE_PASSWORD}
Glance keystone User: ${GLANCE_ADMIN_USER}
Glance keystone Password: ${GLANCE_ADMIN_PASSWORD}
Glance_server_IP_address: ${GLANCE_SERVER_IP_ADDRESS}

----- Cinder Parameters  -----
Cinder MySQL User: ${MYSQL_CINDER_USER}
Cinder MySQL Password: ${MYSQL_CINDER_PASSWORD}
Cinder keystone User: ${CINDER_ADMIN_USER}
Cinder keystone Password: ${CINDER_ADMIN_PASSWORD}
Cinder Server_IP_address: ${CINDER_SERVER_IP_ADDRESS}

-----  Nova Parameters    -----
Nova MySQL User: ${MYSQL_NOVA_USER}
Nova MySQL Password: ${MYSQL_NOVA_PASSWORD}
Nova keystone User: ${NOVA_ADMIN_USER}
Nova keystone Password: ${NOVA_ADMIN_PASSWORD}
NOVA_API_server_IP_address: ${NOVA_API_SERVER_IP_ADDRESS}
Nova Region: ${NOVA_REGION}

----- Common for all services -----
Service Admin Tenant: ${NOVA_ADMIN_TENANT}
Admin keystone user: ${ADMIN_USER}
Admin keystone password: ${ADMIN_PASSWORD}
Demo keystone user: ${DEMO_USER}
Demo keystone password: ${DEMO_PASSWORD}

----------------------------------------------

CONFIG

INSTALLMSG="This OpenStack installation script will: \n\n 
1) Install required packages from the Internet \n
2) Create and configure MySQL users and databases for keystone, glance,
and nova services. \n
3) Configure Keystone (Identity service) by adding users, tenants, etc \n
4) Create resource files to set up environment variables \n \n
BEFORE PROCEEDING PLEASE VERIFY CONFIGURATION PARAMETERS SPECIFIED ABOVE! \n
Are you sure you want to continue? [Y/n]" 

if [ -z ${AUTO} ]
then
    echo -e ${INSTALLMSG}
    read input
    if [ "${input}" = "no" ] || [ "${input}" = "n" ]
	then
	echo "Aborting Installation Process"
	exit 1
    else
	echo "Continuing Installation..."
    fi
fi

}

# Install gnu-related packages
function install_gnu_packages() {

    local option=$1
    local installed=$(is_installed "glibc-devel" )
    if [ "${option}" = "clean" ]
    then
	echo "Removing GNU-related packages"
	yum erase glibc-devel automake gcc gcc-c++
	yum erase expect
    else
	echo "Installing GNU-related packages"

	if [ "${installed}" == "NO" ]
	then
	    install_package "glibc-devel"
	else
	    echo "glibc-devel already installed"
	fi

	installed=$(is_installed "automake" )
	if [ "${installed}" == "NO" ]
        then
	    install_package "automake"
	else
	    echo "automake already installed"
	fi

	installed=$(is_installed "gcc" )
	if [ "${installed}" == "NO" ]
        then
	    install_package "gcc"
	else
	    echo "gcc already installed"
	fi

	installed=$(is_installed "gcc-c++" )
        if [ "${installed}" == "NO" ]
        then
	    install_package "gcc-c++"
	else
	    echo "gcc-c++ already installed"
	fi

	# to handle command line prompts from script
	installed=$(is_installed "expect" )
        if [ "${installed}" == "NO" ]
        then
	    install_package "expect"
	else
	    echo "expect already installed"
	fi
	
	# memcached is needed for dashboard
        installed=$(is_installed "memcached" )
	if [ "${installed}" == "NO" ]
        then
            install_package "memcached"
        else
            echo "memcached already installed"
	fi

	# to be able to vnc into VM instance
	installed=$(is_installed "vnc" )
        if [ "${installed}" == "NO" ]
        then
	    install_package "vnc"
	else
	    echo "vnc already installed"
	fi
    fi
}

# Install ntp for clock sync
function install_ntp() {

    local option=$1
    local installed=$(is_installed "ntp" )
    if [ "${option}" = "clean" ]
    then
	echo "Removing ntp package"
	yum erase ntp
    else
	if [ "${installed}" == "NO" ]
	then
	    echo "Installing ntp package"
	    install_package "ntp"
	else
	    echo "ntp package already installed"
	fi
    fi
}

# Install mysql/RabbitMQ
function install_mysql() {

    local option=$1
    local rhel_dir="/usr/share/repo/RHEL/"
    local mounted=$(mountpoint ${rhel_dir} )

    if [ ${REPOS_CONFIG} = false ]
    then
        echo "Repositories not configured, cannot install MYSQL"
	error_exit ""
    fi

    if [ "${option}" == "clean" ]
    then
        echo "Removing MYSQL/RabbitMQ package and dependencies ..."
        yum erase mysql
	# TODO: MultiNode installation, this needs to be done on head node only
	yum erase rabbitmq-server
    else
	echo "Installing MYSQL package and dependencies ..."

	# grizzly specific
	if [ "${OS_DIST}" == "grizzly" ]
	then
	    if [ "${mounted}" == "true" ]
	    then
		yum install --disablerepo=* --enablerepo=dodcs-sw-iso,rhel-iso erlang erlang-wx
	    else
		yum install erlang erlang-wx
	    fi
	fi

	# This installs a python/MYSQL interpreter to allow python to communicate with mysql
	echo "Installing python/MySQL Interpreter + rabbitMQ package and dependencies ..."
	if [ "${mounted}" == "true" ]
	then
	    yum install --disablerepo=* --enablerepo=dodcs-sw-iso,rhel-iso mysql
	    yum install --disablerepo=* --enablerepo=dodcs-sw-iso,rhel-iso MySQL-python

            yum install --disablerepo=* --enablerepo=dodcs-sw-iso,rhel-iso rabbitmq-server httpd
	else
	    yum install --enablerepo=dodcs-sw-iso mysql
	    yum install --enablerepo=dodcs-sw-iso MySQL-python
            yum install --enablerepo=dodcs-sw-iso rabbitmq-server httpd
	fi

	chkconfig mysqld on
	restart_service mysqld

        chkconfig rabbitmq-server on
        restart_service rabbitmq-server
    fi
}

# Install openstack packages
function install_openstack() {

    local option=$1
    local rhel_dir="/usr/share/repo/RHEL/"
    local mounted=$(mountpoint ${rhel_dir} )

    disable_SELINUX

    if [ ${REPOS_CONFIG} = false ]
    then
	echo "Repositories not configured, cannot install openstack"
	error_exit ""
    fi

    if [ "${option}" == "clean" ]
    then
	echo "Removing dodcs-openstack package and dependencies ..."
	yum erase dodcs-openstack nova-install python-nova
    else
	echo "Installing dodcs-openstack package and dependencies ..."
	# RHEL ISO not required if host has internet access
	if [ "${mounted}" == "true" ]
	then
	    yum install --disablerepo=* --enablerepo=dodcs-sw-iso,rhel-iso dodcs-openstack
	    # Also install firefox, X11
	    yum install --disablerepo=* --enablerepo=dodcs-sw-iso,rhel-iso firefox
	else
	    yum install --enablerepo=dodcs-sw-iso dodcs-openstack
	    yum install  firefox
	fi
	yum groupinstall "X Window System"
    fi
}

# Install/Remove yum-priority package
function install_yum_pri() {

    set +o errexit
    local installed=$(is_installed "yum-priority" )
    local option=$1
    if [ "${option}" = "clean" ]
    then
	echo "Uninstalling yum-priority"
	yum erase yum-plugin-priorities
    else
	echo "Installing yum-priority package"
	if [ ! -n "${installed}" ] 
	then
	    yum install yum-plugin-priorities
	    update_repo_pri "dodcs-sw-iso" "1"
	    update_repo_pri "rhel-iso" "2"
	else
	    echo "yum-priority already installed"
	fi
    fi
    set -o errexit
}

# Update the priority of yum-repo
function update_repo_pri() {

    local reponame=$1
    local pri=$2
    
    local filename="/etc/yum.repos.d/iso.repo"
    local str="priority"
    local replacestr=""
    local found=$(grep ${str} ${filename} )

    # Null argument, update both
    if [ -z "${reponame}" ]
    then
	found=$(grep -m 1 ${str} ${filename} )
	if [ -n "${found}" ]
	then
	    echo "reponame found"
	    sed -e '/enabled/{x;/./b;x;h;i\priority=3' -e '}' ${filename} > "test.txt"
	    mv "test.txt" ${filename}
	else
	    echo "repo: ${reponame} not found"
	    replacestr="priority=1"
	    sed -i 's/${str}/${replacestr}' ${filename}
	fi
    else
	# reponame found, update it with specified argument
	# also make sure a priority was specified
	if [ -z "${pri}" ]
	then
	    error_exit "Unspecified-Priority"
	fi
	echo "Updating yum-repo ${reponame} with priority: ${pri}"

	found=$(grep -m 1 ${reponame} ${filename} )
        if [ -n "${found}" ]
	then
	    echo "found"
	    linenum=$(grep -n "${reponame}" ${filename} | cut -f1 -d: )
	    let end=${linenum}
	    let end+=4
	    echo "linenum(${linenum}-end{$end})"
	    sed -e "${linenum},${end}{/enabled/{x;/./b;x;h;i\priority=${pri}" -e '}' -e '}' ${filename} > "test.txt"
            mv "test.txt" ${filename}
        else
            replacestr="priority=5"
            sed -i 's/${str}/${replacestr}' ${filename}
        fi
    fi
  
}

# Setup/Mount Repo images
function config_iso_repos() {

# copy the RHEL ISO file to /usr/share/iso
    local dir="/usr/share/iso/"
    local rhel_file=${dir}${RHEL_ISO_NAME}
    local dodcs_file=${dir}${DODCS_ISO_NAME}

    if [ "${RHEL_ISO_PATH}" != "${dir}" ]
    then
	verbose && echo "Copying BASE_OS_ISO:${RHEL_ISO_NAME} to shared space"

	if [ ! -d "${dir}" ]
	then
	    echo "${dir} does not exists, creating...."
	    mkdir -p ${dir}
	else
	    echo "Directory ${dir} already exists, no need to recreate"
	fi
    fi

    # Make sure iso exists
    if [ ! -e ${RHEL_ISO} ]
    then
	msg="RHEL-ISO:${RHEL_ISO}-does-not-exist"
	error_exit ${msg}
    fi

    if [ ! -e ${DODCS_ISO} ]
    then
	msg="DODCS-ISO:${DODCS_ISO}-does-not-exist"
	error_exit ${msg}
    fi

    # Now copy the ISO if file does not exist or ISO's differ
    if [ ! -e ${rhel_file} ]
    then
	echo "Copying RHEL_ISO Image to ${dir}"
	cp -r ${RHEL_ISO} ${dir}
    else
	echo "RHEL ISO:${rhel_file} already located in ${dir}"
    fi

# Now do the same for the DODCS ISO
    if [ "${DODCS_ISO_PATH}" != "${dir}" ]
    then
        echo " Copying DODCS_ISO to shared space"
        if [ ! -d "${dir}" ]
        then
            echo "${dir} does not exists, creating...."
            mkdir -p ${dir}
        else
            echo "Directory ${dir} already exists, no need to recreate"
        fi
    fi

    if [ ! -e ${dodcs_file} ]
    then
	echo "Copying DODCS_ISO Image to ${dir}"
        cp -r ${DODCS_ISO} ${dir}
    else
	echo "DODCS ISO already located in ${dir}"
    fi
    
    REPOS_CONFIG=true
}

# Separate function since this may need to be done more than once
function mount_isos() {

    set +o errexit # disable error exit in case directories already exist

    local dir="/usr/share/repo"
    local rhel_dir=${dir}"/RHEL"
    local dodcs_dir=${dir}"/DODCS/"
    local mounted

    echo "MOUNT ISOs Started"

    # create the directories as needed
    if [ ! -d ${rhel_dir} ] 
    then
	echo "Creating RHEL-repo dir: ${rhel_dir}"
	mkdir -p ${rhel_dir}
    else
	echo "RHEL-repo dir: ${rhel_dir} already exists!"
    fi

    if [ ! -d ${dodcs_dir} ] 
    then
	verbose && echo "Creating DODCS-repo dir: ${dodcs_dir}"
	mkdir -p  ${dodcs_dir}
    else
	verbose && echo "DODCS-repo dir: ${dodcs_dir} already exists!"
    fi

    # Check to see if ISOs are already mounted or if the directory is non-empty
    mounted=$(mountpoint ${rhel_dir} )
    empty=$(isDirEmpty ${rhel_dir} )
    if [ "${mounted}" == *"is a mountpoint"* ] || [ "${empty}" == "false" ]
    then
	verbose && echo "RHEL_ISO already mounted"
    else
	verbose && echo "Mounting RHEL-ISO("${RHEL_ISO}") at:"${rhel_dir}
	mount -o loop ${RHEL_ISO} ${rhel_dir}
    fi
    
    mounted=$(mountpoint ${dodcs_dir} )
    empty=$(isDirEmpty ${dodcs_dir} )
    if [ "${mounted}" == *"is a mountpoint"* ] || [ "${empty}" == "false" ]
    then
	verbose && echo "DODCS_ISO already mounted"
    else
	verbose && echo "Mounting DODCS-ISO("${DODCS_ISO}") at:"${dodcs_dir}
	mount -o loop ${DODCS_ISO} ${dodcs_dir}
    fi

    # Set global variable paths
    DODCS_REPO_PATH=${dodcs_dir}"hpc_${OS_DIST}_repo" 
    RHEL_REPO_PATH=${rhel_dir}

    set -o errexit
    echo "MOUNT ISOs DONE!"
}

# Configure yum repositories
function config_yum_repos() {

    set +o errexit # disable error exit if config file does not exist

    local filename="/etc/yum.repos.d/iso.repo"
    local option=$1
    local reponame
    local linenum

    if [ "${option}" = "clean" ]
    then
	verbose && echo "Deleting DODCS repo options"

	if [ ! -e "${filename}" ] 
	then
	    verbose && echo "Nothing to do, repo file does not exist, returning..."
	    return
	fi

	reponame="\[\dodcs-sw-iso\]"
	linenum=$(grep -n "${reponame}" ${filename} | cut -f1 -d: )
	let end=${linenum}
	let end+=6
	sed -e "${linenum},${end}d" ${filename} > "test.txt"
	mv "test.txt" ${filename}

	reponame="\[\rhel-iso\]"
        linenum=$(grep -n "${reponame}" ${filename} | cut -f1 -d: )
	let end=${linenum}
	let end+=6
        sed "${linenum},${end}d" ${filename} > "test.txt"
	mv "test.txt" ${filename}

	reponame=$(grep -R "\[" ${filename} )
	if [ ! -n "${reponame}" ]
	then
	    verbose && echo "No more repos in this file, deleting it..."
	    rm -rf ${filename}
	fi
	yum clean all
	return
    fi

    verbose && echo "Configuring yum repositories Started..."

    # Make sure file exists
    if [ ! -e ${filename} ]
    then
	echo "Creating repo file: ${filename}"
	touch ${filename}
    fi

    # check to see if yum repo file already configured for dodcs
    local found=$(grep -R "\[\dodcs-sw-iso\]" ${filename} )
    if [ -n "${found}" ]
    then
	verbose && echo "yum repo file already configured for DODCS Install"
    else
	verbose && echo "Writing to config file ..."
	cat >> ${filename} << EOF

# DODCS Repository
[dodcs-sw-iso]
name=dodcs-"${OS_DIST}"-iso
baseurl=file:///usr/share/repo/DODCS/hpc_${OS_DIST}_repo
enabled=1
gpgcheck=0
EOF
    fi

    found=$(grep -R "\[\rhel-iso\]" ${filename} )
    if [ -n "${found}" ]
    then
	verbose && echo "yum repo file already configured for RHEL Install"
    else
	cat >> ${filename} <<EOF

# RHEL Repository
[rhel-iso]
name=RHEL-iso
baseurl=file:///usr/share/repo/RHEL
enabled=1
gpgcheck=0
EOF
    fi

    set -o errexit
    REPOS_CONFIG=true
    echo "DONE!"
}

# Update the Kernel
function update_kernel() {

    KERNEL_RPM_NAME="kernel-2.6.38.2lxc0.7.4-1.x86_64.rpm"
    KERNEL_SRC_NAME="kernel-2.6.38.2lxc0.7.4-1.src.rpm"

    # prevent unbound error
    if [ "${START_INSTALL_STEP}" != "1" ]
    then
	DODCS_REPO_PATH="/usr/share/repo/DODCS/hpc_${OS_DIST}_repo/"
    fi

    local kernel_rpm=${DODCS_REPO_PATH}"/"${KERNEL_RPM_NAME}
    local kernel_src=${DODCS_REPO_PATH}"/"${KERNEL_SRC_NAME}
    local nbdmodule="/etc/sysconfig/modules/nbd.modules"
    local kernel_rpminstall_path="/root/rpmbuild/kernel-2.6.38.2lxc0.7.4"
    local kernel_srcinstall_path="/root/rpmbuild/SOURCES/kernel-2.6.38.2lxc0.7.4"
    local kernel_rpmsrc_path="/root/rpmbuild/SOURCES"
    local option=$1
    local cgroup_mounted=0
    local curr_kernel_version

    set +o errexit

    # get current kernel version
    curr_kernel_version=$(uname -r)

    # Check to see if cgroup is mounted, because if it is and user
    # does not want to clean/rebuild the kernel, then we can skip this function
    ismounted "/cgroup/"
    cgroup_mounted=$?

    if [ "${cgroup_mounted}" = "1" ]
    then
	echo "cgroup mounted"
    else
	echo "cgroup not-mounted"
    fi

    # Check to make sure repos have been configured accordingly
    if [ $REPOS_CONFIG = false ] && [ "${option}" != "clean" ] ;
    then
	error_exit 'Repos not configured, cannot install kernel'
    fi

    # Check to see if kernel is already installed
    if [ -d ${kernel_rpminstall_path} ] && [ -d ${kernel_srcinstall_path} ] && [ "${option}" != "force" ] && [ "${option}" != "clean" ]
    then
	verbose && echo "Kernel already installed, Nothing to do returning..."
	return
    elif [ -d ${kernel_rpminstall_path} ] && [ "${option}" == "force" ]
	then
	echo "Kernel already installed, but force option will reinstall"
    elif [ "${option}" = "clean" ]
    then
	echo "Cleaning Kernel Install ..."
	yum clean all # as a precaution
	rpm -e ${kernel_rpm}
	rpm -e ${kernel_src}

	if [ -d ${kernel_rpminstall_path} ]
	then
	    verbose && echo "Deleting Kernel rpm Install Directory: ${kernel_rpminstall_path}"
	    rm -rf "${kernel_rpminstall_path}"
	else
	    verbose && echo "Kernel RPM Not Installed!"
	fi

	if [ -d${kernel_srcinstall_path} ]
        then
            verbose && echo "Deleting Kernel src Install Directory: ${kernel_srcinstall_path}"
            rm -rf "${kernel_srcinstall_path}"
        else
            verbose && echo "Kernel Src Not Installed!"
        fi

	echo "Kernel Uninstallation DONE!"
	set -o errexit
	return
    elif [ -d ${kernel_srcinstall_path} ] && [ "${cgroup_mounted}" = "0" ]
	then
	# Just need to mount cgroup
	echo "Kernel Installed but cgroup filesystem not mounted, Mounting cgroup now..."
	mount none -t cgroup /cgroup/
	set -o errexit
	return
    elif [ -d ${kernel_srcinstall_path} ] && [ "${cgroup_mounted}" = "1" ]
    then
	echo "Kernel Installed and cgroup filesystem mounted, Nothing to do returning..."
	set -o errexit
	return
    fi

    echo "Updating Kernel Started..."

    # Install supplied kernel
    rpm -ivh ${kernel_rpm}

    # Install the kernel from the source
    rpm -ivh ${kernel_src}
    
    cd ${kernel_rpmsrc_path}
    tar xvzf ${kernel_rpmsrc_path}"/kernel-2.6.38.2lxc0.7.4.tar.gz"
    cd ${kernel_rpmsrc_path}"/kernel-2.6.38.2lxc0.7.4/"
    
    make oldconfig
    make

    # Ensure that the nbd kernel module is loaded on boot
    echo "modprobe nbd" >> ${nbdmodule}
    chmod 755 ${nbdmodule}

    echo "System needs to reboot for kernel update to take effect"
    echo "Reboot now?? [Y/n]"
    read input
    if [ "${input}" = "no" ] || [ "${input}" = "n" ]
        then
        echo "Aborting Installation Process, continue after rebooting machine"
        exit 1
    else
        echo "Rebooting System now..."
	reboot now
    fi

}

function config_network() {

    local network_dir="/etc/sysconfig/network-scripts/"
    local eth0_file="ifcfg-"${ETH_PORT}
    local br_file="ifcfg-"${BRIDGE}
    local bkp_ext="bkp-" #prepend extension so network does not try to bring it up
    local file
    local HWADDR
    local BOOTPROTO
    local NM_CONTROL

    echo "Configuring Network Started..."

    set +o errexit
    # If the number of NIC Cards == 1, then no need for a bridge association
    if [ "${NUM_NICS}" == 1 ]
    then
	echo "ONLY ONE NIC, no need for Bridge Association, skipping network configuration step"
	return
    fi

# If running grizzly, then no need for bridge association
    if [ "${OS_DIST}" == "grizzly" ]
    then
	echo "Grizzly Release of Nova automatically configures bridge network, exiting"
	return
    fi

    # back old eth file just in case                                                                  
    file=${network_dir}${eth0_file}
    bkp=${network_dir}${bkp_ext}${eth0_file}
    if [ ! -e "${bkp}" ]
    then
        echo "Creating backup file ${bkp} ..."
        cp "${network_dir}${eth0_file}" $bkp
    else
	verbose && echo "network backup already exists"
    fi
    
    # Record the HW Addr first before erasing file
    HWADDR=$(grep "HWADDR" ${network_dir}${eth0_file} )
    BOOTPROTO=$(grep "BOOTPROTO" ${network_dir}${eth0_file} )
    NM_CONTROL=$(grep "NM_CONTROLLED" ${network_dir}${eth0_file} )

    verbose && echo "Generating network-config for ${file}"
    rm -rf ${file}
    cat >> ${file} << EOF

# Generated ${ETH_PORT} file for OPENSTACK Installation

DEVICE="${ETH_PORT}"
TYPE="Ethernet"
${HWADDR}
IPV6INIT="no"
NM_CONTROLLED="no"
ONBOOT="yes"
BRIDGE=${BRIDGE}
EOF

# If the number of NIC Cards == 1, then no need for a bridge association
	if [ "${NUM_NICS}" == 1 ]
	then
	    verbose && echo "Machine only has 1 NIC Card, removing Bridge Association ..."
	    sed -e "/BRIDGE=/d" ${file} >& "temp.txt"
	    mv "temp.txt" ${file}
	    # put original NM_CONTROLLED option back in
	    sed -e "/NM_CONTROLLED=/d" ${file} >& "temp.txt"
	    mv "temp.txt" ${file}
	    sed '$a ${NM_CONTROL}' ${file}
	    # Also add BOOTPROTO back in at end of file
	    sed '$ a ${BOOTPROTO}' ${file}
	    
	else
	    verbose && echo "Machine has (${NUM_NICS}) NIC CARDS"
	fi

	verbose && echo "Generating network-config for Bridge file"
	file=${network_dir}${br_file}

	# delete the file if it already exists
	rm -rf ${file}

        cat >> ${file} << EOF                                                                        
 
# Generated ${BRIDGE} file for OPENSTACK Installation                                                          
                       
DEVICE=${BRIDGE}
TYPE="Bridge"
BOOTPROTO="static"
ONBOOT="yes"
IPADDR=${CC_ADDR}
NETMASK=255.255.255.0

EOF

    # Now restart the network
    set +o errexit #Disable error exit b/c wlan0 may fail to be brought up
    echo "Restarting Network for changes to take effect..."
    service network restart
    set -o errexit # reenable
    echo "Configuring Network DONE!"
}

# function to configure openstack dashboard
function config_openstack_dashboard() {

    local filename_dashboard="/etc/openstack-dashboard/local_settings"
    local filename_memcached="/etc/sysconfig/memcached"
    local memcached_port
    local memcached_address
    local disable_str="CACHE_BACKEND"
    local replace_str="CACHE_BACKEND = 'memcached\:\/\/127\.0\.0\.1\:11211\/'"
    local linenum=$(grep "${disable_str}" ${filename_dashboard} )

    echo "Configuring openstack-dashboard Started"
    # The address and port in the new value need to be equal to the ones set in /etc/sysconfig/memcached.
    if [ linenum ]
    then
	sed -e "s/${disable_str}/${replace_str}/g" ${filename_dashboard} > "temp.txt"
	mv "temp.txt" ${filename_dashboard}
    else
	error_exit "${filename_dashboard}-not found"
    fi

    echo "Configuring openstack-deashboard DONE!"
}

# Configure horizon DashBoard for Folsom
function config_horizon() {
    
    wsgi_file="/etc/httpd/conf.d"
    # These instructions assume that the localhost is the Horizon host
    echo "Configuring Horizon DashBoard Started..."

    #(a) See if wsgi.conf is configured for apache webserver
    if [ -e ${wsgi_file} ]
    then
	echo " ${wsgi_file} already exists"
    else
	mv "/etc/httpd/conf.d/wsgi.conf.isi" ${wsgi_file}
    fi
    
    #(b) setup the database for apache
    echo "Setting up the database for apache"
    cd /etc/openstack-horizon
    python manage.py syncdb
    
    dir=$(pwd)"/static"
    if [ -d "$dir" ]
    then
	chown -R apache:apache static
	verbose && echo "Setting ownership of $dir"
    else
	message="directory-does-not-exist"
	error_exit $message
    fi
    
    cd /etc/openstack-horizon/openstack_dashboard/
    chown apache:apache local
    chown apache:apache local/dashboard_openstack.sqlite3

    # Now restart apache
    chkconfig httpd on
    restart_service httpd

    echo "Configuring Horizon DashBoard DONE!"
}

# Configure firewall to allow port listening
# This should be executed on all nodes
function setup_firewall() {
    
    echo "Configuring firewall Started ...."
    local iptable_file="/etc/sysconfig/iptables"

    restart_service 'iptables'
    
    # Ensure ports are not blocked by firewall
    iptables -I INPUT 1 -p tcp --dport 5672 -j ACCEPT
    iptables -I INPUT 1 -p tcp --dport 3306 -j ACCEPT
    
    iptables -I INPUT 1 -p tcp --dport 3260 -j ACCEPT
    iptables -I INPUT 1 -p tcp --dport 9292 -j ACCEPT
    
    iptables -I INPUT 1 -p tcp --dport 6080 -j ACCEPT
    iptables -I INPUT 1 -p tcp --dport 8773 -j ACCEPT
    iptables -I INPUT 1 -p tcp --dport 8774 -j ACCEPT
    
    # Yes this is a udp port
    iptables -I INPUT 1 -p udp --dport 67 -j ACCEPT
    
    iptables -I INPUT 1 -p tcp --dport 5000 -j ACCEPT
    iptables -I INPUT 1 -p tcp --dport 35357 -j ACCEPT

    # Allow VMs to access META-DATA SERVER
    iptables -A POSTROUTING -t mangle -p udp --dport 68 -j CHECKSUM --checksum-fill

    # Now save it, otherwise firewall info will be lost on reboot
    iptables-save > ${iptable_file}

    # The following line in the iptables may prevent from assigning IP address to a VM.
    # so we remove it
    sed '/icmp-host-prohibited/d' ${iptable_file} >& "temp.txt"
    mv "temp.txt" ${iptable_file}
    
    # Also put the META-DATA SERVER port into rc.local to ensure access across reboots
    iptable_files="/etc/rc.local"
    echo "iptables -A POSTROUTING -t mangle -p udp --dport 68 -j CHECKSUM --checksum-fill" >> ${iptable_files}

    echo "Firewall Configuration DONE!"
}

# Configure MySQL for OpenStack
function setup_mysql() {
	   
    echo "MYSQL-Configured: ${MYSQL_CONFIGURED}"
    local firewall_status
    local hostname=`echo $HOSTNAME`
    if [ "${MYSQL_CONFIGURED}" == "false" ]
    then
	echo "Configuring MySQL for OpenStack"
	
	# Note if firewalls enabled, then mysqladmin may unable to connect to local host
	firewall_status=$(service_status "iptables" )
	if [ "${firewall_status}" != "stopped" ] || [ "${firewall_status}" != "" ]
	then
	    echo "FIREWALL ENABLED!, mysqladmin may fail to connect!"
	fi
	set +o errexit
	# MySQL Root Password need only be set once, otherwise changing it will fail
	mysqladmin -uroot password $MYSQL_ROOT_PASSWORD
	mysqladmin -u root -h $hostname password $MYSQL_ROOT_PASSWORD
	set -o errexit

	mysql -uroot -p$MYSQL_ROOT_PASSWORD -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;"
	mysql -uroot -p$MYSQL_ROOT_PASSWORD -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;"
	
	echo "MYSQL Configuration DONE!"
    else
	echo "MYSQL already configured for dodcs-openstack"
    fi
    
    MYSQL_CONFIGURED=true
}

function change_mysqladmin() {

    echo "Changing mysqladmin password"
    mysql_secure_installation
    echo "DONE!"
}

function setup_example_files() {

    echo "Setting up example file configurations.."

    local example_file
    local conf_file
    local pastefile="/etc/glance/glance-api-paste.ini"
    
    # keystone
    example_file="/usr/local/nova/examples/keystone/keystone.conf"
    conf_file="/etc/keystone/keystone.conf"
    if [ -e "${example_file}" ]
    then
        cp ${example_file} ${conf_file}
    else
        echo "Operation Failed because File: ${example_file} does not EXIST --> Aborting!"
        error_exit "Aborting"
    fi

    # glance
    example_file="/usr/local/nova/examples/glance/glance-api.conf"
    conf_file="/etc/glance/glance-api.conf"
    if [ -e "${example_file}" ]
    then
        cp ${example_file} ${conf_file}
    else
        echo "Operation Failed because File: ${example_file} does not EXIST --> Aborting!"
        error_exit "Aborting"
    fi

    example_file="/usr/local/nova/examples/glance/glance-api-paste.ini"
    if [ -e "${example_file}" ]
    then
        cp ${example_file} ${pastefile}
    else
        echo "Operation Failed because File: ${example_file} does not EXIST --> Aborting!"
        error_exit "Aborting"
    fi

    # example registry-file
    example_file="/usr/local/nova/examples/glance/glance-registry.conf"
    conf_file="/etc/glance/glance-registry.conf"
    if [ -e "${example_file}" ]
    then
        cp ${example_file} ${conf_file}
    else
        echo "Operation Failed because File: ${example_file} does not EXIST --> Aborting!"
        error_exit "Aborting"
    fi

    example_file="/usr/local/nova/examples/glance/glance-registry-paste.ini"
    pastefile="/etc/glance/glance-registry-paste.ini"
    if [ -e "${example_file}" ]
    then
        cp ${example_file} ${pastefile}
    else
        echo "Operation Failed because File: ${example_file} does not EXIST --> Aborting!"
        error_exit "Aborting"
    fi

    # nova
    

    echo "DONE!"
}

# Create + populate credentials file
function setup_credentials() {
    touch ${CREDENTIAL_FILE}
    update_creds "EC2\_URL" "http://127.0.0.1:8773/services/Cloud" ${CREDENTIAL_FILE}
    update_creds "OS\_USERNAME" ${ADMIN_USER} ${CREDENTIAL_FILE}
    update_creds "OS\_PASSWORD" ${ADMIN_PASSWORD} ${CREDENTIAL_FILE}
    update_creds "OS\_TENANT\_NAME" ${NOVA_ADMIN_TENANT} ${CREDENTIAL_FILE}
    update_creds "OS\_AUTH\_URL" "http://localhost:5000/v2.0/" ${CREDENTIAL_FILE}
    update_creds "MYSQL\_Root\_Password" ${MYSQL_ROOT_PASSWORD} ${CREDENTIAL_FILE}
    update_creds "LIBVIRT\_DEBUG" "yes" ${CREDENTIAL_FILE}
}

# Create + Populate KeyStone
function setup_keystone() {

    echo "setup_keystone Started..."
    echo "Creating + Populating KeyStone service..."
    initialize_keystone_python

    # Configure openstack-nova on the head node to use KeyStone
    local file="/etc/nova/api-paste.ini"
    local disable_str
    local replace_str
    local found
    local linenum

    set +o errexit

    if [ ! -e "${file}" ]
    then
        echo "${file} does not Exist!"
	error_exit "Aborting"
    else
	echo "Updating Variables in ${file}"
    fi

    # update admin_tenant_name                                                                 
    disable_str="\%SERVICE\_TENANT\_NAME\%"
    found=$(grep "${disable_str}" ${file} )
    linenum=$(grep "${disable_str}" ${file} )
    if [ found ]
    then
        verbose && echo "Updating admin_tenant_service"
        replace_str="${NOVA_ADMIN_TENANT}"
	verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
	sed -i "s/${disable_str}/${replace_str}/g" ${file}
    else
        error_exit "admin_tenant_name-not-found"
    fi    

    # update service user                                                                      
    disable_str="\%SERVICE\_USER\%"
    found=$(grep "${disable_str}" ${file} )
    linenum=$(grep "${disable_str}" ${file} )
    if [ found ]
    then
        echo "Updating admin_user"
        replace_str="admin"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${file} > "temp.txt"
        mv "temp.txt" ${file}
    else
        error_exit "service-user--not-found"
    fi

    # update service password                                                                  
    disable_str="\%SERVICE\_PASSWORD\%"
    found=$(grep "${disable_str}" ${file} )
    linenum=$(grep "${disable_str}" ${file} )
    if [ found ]
    then
        verbose && echo "Updating admin_user"
        replace_str="${MYSQL_GLANCE_PASSWORD}"
	verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${file} > "temp.txt"
        mv "temp.txt" ${file}
    else
        error_exit "admin-password--not-found"
    fi

    echo "Syncing Keystone Database..."
    keystone-manage db_sync

    # update keystone permissions
    # logs may not exist (if its a first-time run)
    set +o errexit
    echo "Updating permissions to keystone directory..."
    chown -R keystone:keystone /etc/keystone/
    chown -R keystone:keystone /var/log/keystone/*
    set -o errexit

    restart_keystone_services
    echo "setup_keystone Done!"
}

# Configure Glance
function configure_glance() {

    echo "Configuring glance from python"
    cd ${OS_INSTALL_DIR}
    clear; python OS-config.py ${CONFIG_FILE} "configure_glance"

    # Need to update glance-api/glance-registry.conf files too
    local apifile="/etc/glance/glance-api.conf"
    local regfile="/etc/glance/glance-registry.conf"
    local pastefile="/etc/glance/glance-api-paste.ini"
    local found
    local linenum
    local endlinenum
    local disable_str

    #update the sql connection line
    disable_str="sql\_connection = sqlite:\/\/\/glance.sqlite"
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    if [ found ]
    then
        verbose && echo "Updating mysql connection"
        replace_str="sql_connection=mysql:\/\/${MYSQL_GLANCE_USER}:${MYSQL_GLANCE_PASSWORD}@${GLANCE_SERVER_IP_ADDRESS}\/glance"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${apifile} > "temp.txt"
        mv "temp.txt" ${apifile}
    else
        error_exit "mysql-connection-not-found"
    fi

    # update admin_tenant_name                                                                 
    disable_str="\%SERVICE\_TENANT\_NAME\%"
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    if [ found ]
    then
        verbose && echo "Updating admin_tenant_service"
        replace_str="${NOVA_ADMIN_TENANT}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -i "s/${disable_str}/${replace_str}/g" ${apifile}
    else
        error_exit "admin_tenant_name-not-found"
    fi

    # update service user                                                                      
    disable_str="\%SERVICE\_USER\%"
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    if [ found ]
    then
        verbose && echo "Updating admin_user"
        replace_str="glance"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${apifile} > "temp.txt"
        mv "temp.txt" ${apifile}
    else
        error_exit "service-user--not-found"
    fi

    # update service password                                                                  
    disable_str="\%SERVICE\_PASSWORD\%"
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    if [ found ]
    then
        verbose && echo "Updating admin_user"
        replace_str="${MYSQL_GLANCE_PASSWORD}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${apifile} > "temp.txt"
        mv "temp.txt" ${apifile}
    else
        error_exit "admin-password--not-found"
    fi

    #update the config file location
    disable_str="\#config\_file = glance\-api\-paste\.ini"
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    if [ found ]
    then
        verbose && echo "Updating api-paste config file"
        replace_str="config\_file = \/etc\/glance\/glance\-api\-paste\.ini"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${apifile} > "temp.txt"
        mv "temp.txt" ${apifile}
    else
        error_exit "api-paste config file not found"
    fi

    disable_str="\#flavor="
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    if [ found ]
    then
        verbose && echo "updating keystone flavor"
        replace_str="flavor = keystone"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${apifile} > "temp.txt"
        mv "temp.txt" ${apifile}
    else
        error_exit "flavor not found"
    fi

    ################ Now update the glance-registry file ##################

    #update the sql connection line                                                            
    disable_str="sql\_connection = sqlite:\/\/\/glance.sqlite"
    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    if [ found ]
    then
        verbose && echo "Updating mysql connection"
        replace_str="sql_connection=mysql:\/\/${MYSQL_GLANCE_USER}:${MYSQL_GLANCE_PASSWORD}@${GLANCE_SERVER_IP_ADDRESS}\/glance"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${regfile} > "temp.txt"
        mv "temp.txt" ${regfile}
    else
        error_exit "mysql-connection-not-found"
    fi

    # update admin_tenant_name
    disable_str="\%SERVICE\_TENANT\_NAME\%"
    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    if [ found ]
    then
        verbose && echo "Updating admin_tenant_service"
        replace_str="${NOVA_ADMIN_TENANT}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -i "s/${disable_str}/${replace_str}/g" ${regfile}
    else
        error_exit "admin_tenant_name-not-found"
    fi

    # update service user
    disable_str="\%SERVICE\_USER\%"
    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    if [ found ]
    then
        verbose && echo "Updating admin_user"
        replace_str="glance"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${regfile} > "temp.txt"
        mv "temp.txt" ${regfile}
    else
        error_exit "service-user--not-found"
    fi

    # update service password
    disable_str="\%SERVICE\_PASSWORD\%"
    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    if [ found ]
    then
        verbose && echo "Updating admin_user"
        replace_str="${MYSQL_GLANCE_PASSWORD}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${regfile} > "temp.txt"
        mv "temp.txt" ${regfile}
    else
        error_exit "admin-password--not-found"
    fi

    # update the config file location
    # update the config file                                                                     
    disable_str="\#config\_file = glance\-registry\-paste\.ini"
    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    if [ found ]
    then
        verbose && echo "Updating registry-paste config file"
        replace_str="config\_file = \/etc\/glance\/glance\-registry\-paste\.ini"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -i "s/${disable_str}/${replace_str}/g" ${regfile}
    else
        error_exit "api-paste config file not found"
    fi

    # update the flavor
    disable_str="\#flavor="
    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    if [ found ]
    then
        echo "updating keystone flavor"
        replace_str="flavor = keystone"
        echo "new string: ${replace_str}"
        echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${regfile} > "temp.txt"
        mv "temp.txt" ${regfile}
    else
        error_exit "flavor-not-found"
    fi

    ################ Now update the glance-api files ################## 
    apifile="/etc/glance/glance-api-paste.ini"
    regfile="/etc/glance/glance-registry-paste.ini"

    # remove existing keystone authentication
    disable_str="Appended by openstack installation script"
    found=$(grep "${disable_str}" ${apifile} )
    linenum=$(grep "${disable_str}" ${apifile} )
    endlinenum=${linenum}
    let endlinenum=endlinenum+8
    if [ found ]
    then
	echo "removing previous script insertion of keystone authentication"
        sed "${linenum},${endlinenum},d" ${apifile}
    fi

    found=$(grep "${disable_str}" ${regfile} )
    linenum=$(grep "${disable_str}" ${regfile} )
    endlinenum=${linenum}
    let endlinenum=endlinenum+8
    if [ found ]
    then
	echo "removing previous script insertion of keystone authentication"
	sed "${linenum},${endlinenum},d" ${regfile}
    fi

    echo "Appending credentials to glance-*-paste.ini files"
    cat <<EOF >> ${apifile}
# Appended by openstack installation script
auth_host = 127.0.0.1
auth_port = 35357
auth_protocol = http
admin_token = ${YOUR_ADMIN_TOKEN}
admin_tenant_name = ${NOVA_ADMIN_TENANT}
admin_user = ${GLANCE_ADMIN_USER}
admin_password = ${GLANCE_ADMIN_PASSWORD}
EOF
    
    cat<<EOF >> ${regfile}                                                                                   
# Appended by openstack installation script
auth_host = 127.0.0.1
auth_port = 35357
auth_protocol = http
admin_token = ${YOUR_ADMIN_TOKEN}
admin_tenant_name = ${NOVA_ADMIN_TENANT}
admin_user = ${GLANCE_ADMIN_USER}
admin_password = ${GLANCE_ADMIN_PASSWORD}
EOF

    echo "Syncing Glance DataBase..."
    glance-manage db_sync

    # now update permisions to conf files
    echo "Updating permissions to glance directory..."
    chown -R glance:glance /etc/glance/
    chown -R glance:glance /var/log/glance/

    restart_glance_services

    echo "DONE!"
}

function replace_values() {
    local filename=$1
    local varname=$2
    local oldvalue=$3
    local newvalue=$4
    local disable_str="${varname}\s*=\s*${oldvalue}"
    echo "Replacing ${varname} = ${oldvalue} => ${newvalue} in ${filename}"
    found=$(grep "${disable_str}" ${filename} )
    if [ found ]
    then
        verbose && echo "Updating ${varname}"
        replace_str="${varname}=${newvalue}"
        verbose && echo "new string: ${replace_str}"
        local cmd="s/${disable_str}/${replace_str}/g"
        echo "Sed command ${cmd}"
        sed -i "${cmd}" ${filename}
    else
        error_exit "${disable_str} not found in ${filename}"
    fi

}

# Configure NOVA
function configure_nova() {

    echo "Nova configuration Started..."

    cd ${OS_INSTALL_DIR}
    clear; python OS-config.py ${CONFIG_FILE} "configure_nova"

    # Edit the hpc script as needed                             
    rebase_hpc_script "${DODCS_SCRIPT}"
    echo "NOVA configuration DONE!"
}

# Initialize keystone using python module
function initialize_keystone_python() {
    echo "Configuring keyStone from python"
    cd ${OS_INSTALL_DIR}
    python OS-config.py ${CONFIG_FILE} "initialize_keystone"

    ## Now make sure System specific parameters are set
    local dest="/etc/keystone/keystone.conf"
    local disable_str
    local replace_str
    local found
    local linenum

    set +o errexit # disable to prevent script failure if port numbers have already been replaced

    # update the MYSQL_Connection
    disable_str="connection = mysql:\/\/keystone:keystone@localhost\/keystone"
    found=$(grep "${disable_str}" ${dest} )
    linenum=$(grep "${disable_str}" ${dest} ) 
    if [ found ]
    then
	echo "Updating mysql connection"
	replace_str="connection=mysql:\/\/${MYSQL_KEYSTONE_USER}:${MYSQL_KEYSTONE_PASSWORD}@${KEYSTONE_SERVER_IP_ADDRESS}\/keystone"
	verbose && echo "new string: ${replace_str}"
	verbose && echo "Deleting line(${linenum})"
	sed -e "s/${disable_str}/${replace_str}/g" ${dest} > "temp.txt"
	mv "temp.txt" ${dest}
    else
	error_exit "mysql-connection-not-found"
    fi

    # configure the admin_token
    python OS-config.py ${CONFIG_FILE} "configure" --set ${dest} DEFAULT admin_token ${YOUR_ADMIN_TOKEN}

    # update template_file
    disable_str="template\_file = default\_catalog\.templates"
    found=$(grep "${disable_str}" ${dest} )
    linenum=$(grep "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating template catalog file"
        replace_str="template\_file = \/etc\/keystone\/default\_catalog\.templates"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${dest} > "temp.txt"
        mv "temp.txt" ${dest}
    else
        error_exit "catalog-template-not-found"
    fi

    # Now update the catalog template file with correct port numbers
    echo "Updating catalog template file with correct port numbers"
    disable_str="\\\$\(public\_port\)s"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating public port"
        replace_str="${KEYSTONE_PUBLIC_PORT}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
	perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    else
        error_exit "public-port-not-found"
    fi

    echo "Updating admin_port"
    disable_str="\\\$\(admin\_port\)s"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating admin port"
        replace_str="${KEYSTONE_ADMIN_PORT}"
        echo "new string: ${replace_str}"
        echo "Deleting line(${linenum})"
        perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    else
        error_exit "admin-port-not-found"
    fi

    echo "Updating compute_port"
    disable_str="\\\$\(compute\_port\)s"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating compute port"
        replace_str="${KEYSTONE_COMPUTE_PORT}"
        echo "new string: ${replace_str}"
        echo "Deleting line(${linenum})"
        perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    else
        error_exit "compute-port-not-found"
    fi

    # Disable error exits on grep false
    # because on single node the variable might not be present
    set +o errexit

    # replace the server IPS
    # TODO: Make a function call to do this instead of this copy/paste code
    disable_str="\\\$Keystone_server_IP_address"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating KeyStone IP Address"
        replace_str="127.0.0.1"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    fi

    disable_str="\\\$NOVA_API_server_IP_address"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating NOVA API IP Address"
        replace_str="127.0.0.1"
        echo "new string: ${replace_str}"
        echo "Deleting line(${linenum})"
        perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    fi

    disable_str="\\\$Glance_server_IP_address"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating Glance IP Address"
        replace_str="127.0.0.1"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    fi

    disable_str="\\\$Volume_server_IP_address"
    dest="/etc/keystone/default_catalog.templates"
    found=$(grep -E "${disable_str}" ${dest} )
    linenum=$(grep -E "${disable_str}" ${dest} )
    if [ found ]
    then
        echo "Updating Volume IP Address"
        replace_str="127.0.0.1"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        perl -pi -e "s:${disable_str}:${replace_str}:g" ${dest}
    fi

    set -o errexit
    echo "Initialize Keystone Done!"
}


# Configure cinder with nova and keystone
function configure_cinder() {

    echo "Configuring cinder from python"
    cd ${OS_INSTALL_DIR}
    clear; python OS-config.py ${CONFIG_FILE} "configure_cinder"

    # Change nova configuration to use cinder
    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/nova/nova.conf DEFAULT volume_api_class nova.volume.cinder.API
    # The following is the default apis with 'osapi_volume' removed
    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/nova/nova.conf DEFAULT enabled_apis ec2,osapi_compute,metadata

    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/cinder/cinder.conf DEFAULT sql_connection "mysql://${MYSQL_CINDER_USER}:${MYSQL_CINDER_PASSWORD}@localhost/cinder"
    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/cinder/cinder.conf DEFAULT auth_strategy keystone
    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/cinder/cinder.conf keystone_authtoken admin_tenant_name ${NOVA_ADMIN_TENANT}
    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/cinder/cinder.conf keystone_authtoken admin_user ${CINDER_ADMIN_USER}
    python OS-config.py ${CONFIG_FILE} "configure" --set /etc/cinder/cinder.conf keystone_authtoken admin_password ${CINDER_ADMIN_PASSWORD}

    # On RHEL, manually adjust config to integrate
    # persistent volumes on tgtd startup
    if rpm -q scsi-target-utils | grep -q el6; then
	sed -i '1iinclude /etc/cinder/volumes/*' /etc/tgt/targets.conf
    fi

    echo "Cinder configuration DONE!"
}

# Check that the keystone environment variables are set
function check_keystone_vars() {

    (isvarset ${MYSQL_KEYSTONE_USER} ) && set ${MYSQL_KEYSTONE_USER:=${DEFAULT_MYSQL_KEYSTONE_USER}}
    (isvarset ${MYSQL_KEYSTONE_PASSWORD} ) && set ${MYSQL_KEYSTONE_PASSWORD:=${DEFAULT_MYSQL_KEYSTONE_PASSWORD}}
    
    (isvarset ${KEYSTONE_SERVER_IP_ADDRESS} ) && set ${KEYSTONE_SERVER_IP_ADDRESS:=${LOCALHOST}}
    (isvarset ${KEYSTONE_PUBLIC_PORT} ) && set ${KEYSTONE_PUBLIC_PORT:=5000}
    (isvarset ${KEYSTONE_ADMIN_PORT} ) && set ${KEYSTONE_ADMIN_PORT:=35357}
    (isvarset ${KEYSTONE_COMPUTE_PORT} ) && set ${KEYSTONE_COMPUTE_PORT:=8774}
}

# Search to see if database exists in mysql
function db_exists() {
    local dbtest=$1
    local result=`mysqlshow --user=${MYSQL_ROOT_USER} --password=${MYSQL_ROOT_PASSWORD} ${dbtest}{| grep -v Wildcard | grep -o ${dbtest}`
    if [ "$result" == "$dbtest" ]; then
	echo "DB ${dbtest} Exists"
    else
	echo "DB ${dbtest} does not Exist";
    fi
}

# Run hpc_script
function run_hpc_script() {

    set -o errexit
    local hpc_script=${DODCS_SCRIPT}

    # Make sure script exists                                                                 
    if [ ! -e "${hpc_script}" ]
    then
        echo "Script: ${hpc_script} does not exist...Aborting Installation Process!"
        error_exit ""
    fi


    if [ ${NUM_NODES} = 1 ]
    then
        echo "Running ${OS_DIST}-Script for Single Node Install"
        eval "bash ${hpc_script} single-init"
    else
        error_exit "Multi-Node-install-not-supported-yet"
    fi
    echo "Running hpc-${OS_DIST}-Script Done!"
}

# Edit the hpc-script to reflect local machine (setup) parameters
function rebase_hpc_script() {

    set +o nounset
    set -e

    local script=$1
    local default="/usr/local/nova/nova-install-hpc-${OS_DIST}.sh"
    local foundline
    local linenum
    local replacestr
    local line
    
    if [ -z "${script}" ]
    then
	echo "No hpc-script specified using default: ${default}"
	script=${default}
    fi

    set +o errexit

    # Make sure script exists
    if [ ! -e "$script" ]
    then
        echo "Script: ${script} does not exist...Aborting Installation Process!"
        error_exit ""
    else
	echo "Rebasing ${script} to account for installation parameters"
    fi

    ## Replace IP_address parameters
    # Assume that the IP Address of the bridge (br100) of cloud controller is 10.99.0.1

    # Glance
    echo "Updating Glance Server IP Address of Cloud Controller to: ${CC_ADDR}"
    replacestr="Glance\_server\_IP\_address"
    linenum=$(grep -n "${replacestr}" ${script} | cut -f1 -d: )
    sed "/${replacestr}/c ${replacestr}\=${CC_ADDR}" ${script}
    
    # KeyStone
    echo "Updating Keystone Server IP Address of Cloud Controller to: ${CC_ADDR}"
    replacestr="Keystone\_server\_IP\_address"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "/${replacestr}/c ${replacestr}\=${CC_ADDR}" ${script}
    
    # Volume
    echo "Updating Volume Server IP Address of Cloud Controller to: ${CC_ADDR}"
    replacestr="Volume\_server\_IP\_address"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "/${replacestr}/c ${replacestr}\=${CC_ADDR}" ${script}

    # NOVA-API
    echo "Updating NOVA-API Server IP Address of Cloud Controller to: ${CC_ADDR}"
    replacestr="NOVA\_API\_server\_IP\_address"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "/${replacestr}/c ${replacestr}\=${CC_ADDR}" ${script}

    # NOVA
    echo "Updating NOVA Server IP Address of Cloud Controller to: ${CC_ADDR}"
    replacestr="MYSQL\_Nova\_IP\_address"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "/${replacestr}/c ${replacestr}\=${CC_ADDR}" ${script}

    ## Replace MYSQL parameters

    # Replace this first
    if [ "${OS_DIST}" == "grizzly" ]
    then
        replacestr="sql\_connection"
	line="${replacestr}.*\""
	newstr=${replacestr}"=mysql\:\/\/${MYSQL_NOVA_USER}\:${MYSQL_NOVA_PASSWORD}\@${LOCALHOST}\/nova\""
        linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
        sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
        mv "temp.txt" ${script}
    fi

    replacestr="MYSQL\_ROOT\_USR"
    line="${replacestr}.*"
    newstr="${replacestr}=${MYSQL_ROOT_USER}"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}

    echo "Updating Root Pass"
    replacestr="MYSQL\_ROOT\_PASS"
    line="${replacestr}.*"
    newstr="${replacestr}=${MYSQL_ROOT_PASSWORD}"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}    

    replacestr="MYSQL\_NOVA\_USR"
    line="${replacestr}.*"
    newstr="${replacestr}=${MYSQL_NOVA_USER}"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}

    replacestr="MYSQL\_NOVA\_PASS"
    line="${replacestr}.*"
    newstr="${replacestr}=${MYSQL_NOVA_PASSWORD}"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}

    # Repalce Keystone User/Password nova
    echo "Updating Keystone Nova User/Password..."
    replacestr="KeyStone\_User\_Nova"
    line="${replacestr}.*"
    newstr="${replacestr}=${MYSQL_NOVA_USR}"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}

    replacestr="KeyStone\_Password\_Nova"
    line="${replacestr}.*"
    newstr="${replacestr}=${MYSQL_NOVA_PASSWORD}"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}

    echo "Updating SQL_CONNECTION..."
    replacestr="SQL\_CONN"
    line="${replacestr}.*"
    newstr=${replacestr}"=mysql\:\/\/${MYSQL_NOVA_USER}\:${MYSQL_NOVA_PASSWORD}\@${LOCALHOST}\/nova"
    linenum=$(grep -n -m 1 "${replacestr}" ${script} | cut -f1 -d: )
    sed "s/${line}/${newstr}/g" ${script} > "temp.txt"
    mv "temp.txt" ${script}

    # update admin_tenant_name
    disable_str="\%SERVICE\_TENANT\_NAME\%"
    found=$(grep "${disable_str}" ${script} )
    linenum=$(grep "${disable_str}" ${script} )
    if [ found ]
    then
        verbose && echo "Updating admin_tenant_service"
        replace_str="${NOVA_ADMIN_TENANT}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -i "s/${disable_str}/${replace_str}/g" ${script}
    else
        error_exit "admin_tenant_name-not-found"
    fi

    # update service user
    disable_str="\%SERVICE\_USER\%"
    found=$(grep "${disable_str}" ${script} )
    linenum=$(grep "${disable_str}" ${script} )
    if [ found ]
    then
        echo "Updating admin_user"
        replace_str="admin"
        verbose && echo "new string: ${replace_str}"
verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${script} > "temp.txt"
        mv "temp.txt" ${script}
    else
        error_exit "service-user--not-found"
    fi

    # update service password
    disable_str="\%SERVICE\_PASSWORD\%"
    found=$(grep "${disable_str}" ${script} )
    linenum=$(grep "${disable_str}" ${script} )
    if [ found ]
    then
        verbose && echo "Updating admin_user"
        replace_str="${MYSQL_NOVA_PASSWORD}"
        verbose && echo "new string: ${replace_str}"
        verbose && echo "Deleting line(${linenum})"
        sed -e "s/${disable_str}/${replace_str}/g" ${script} > "temp.txt"
        mv "temp.txt" ${script}
    else
        error_exit "admin-password--not-found"
    fi

    # A few other things. Should probably merge it with 
    # the previous substitutions

    replace_values ${script} "PUBLIC_INTERFACE" ".*" ${PUBLIC_INTERFACE} 
    replace_values ${script} "BRIDGE" ".*" ${BRIDGE} 
    replace_values ${script} "FLAT_INTERFACE" ".*" ${FLAT_INTERFACE} 
    replace_values ${script} "admin_tenant_name" ".*\"" "${NOVA_ADMIN_TENANT}\"" 
    replace_values ${script} "Keystone_User_Nova" ".*" ${NOVA_ADMIN_USER} 
    replace_values ${script} "Keystone_Password_Nova" ".*" "${NOVA_ADMIN_PASSWORD}" 
    local head_cc_addr=`expr match "${CC_ADDR}" '\([0-9]*\.[0-9]*\.\)'`
    ## echo "CC_ADDR ${CC_ADDR}, head ${head_cc_addr}"
    replace_values ${script} "DHCP_FIXED_RANGE" "[0-9]*\.[0-9]*\." "${head_cc_addr}"
    ## read -p "Press Enter to continue"

    # update nova permissions
    # logs may not exist (if its a first-time run)
    set +o errexit
    echo "Updating permissions to nova directory..."
    chown -R nova:nova /etc/nova/
    chown -R nova:nova /var/log/nova/*
    set -o errexit
    echo "Rebasing hpc-script DONE!"
}

# Function to create keystone credentials file
function create_keystone_creds() {
    
    local adminrole
    local keystone_service_adminrole
    local keystone_adminrole
    local memberrole
    local projectrole

    local useradmin
    local userdemo
    local usernova
    local userglance

    local tenantadmin
    local tenantservice
    local tenantdemo

    local servicekeystone
    local servicenova
    local servicevolume
    local serviceimage
    local serviceec2
    local desc

    echo "Creating KeyStone Credentials..."

    (update_creds "SERVICE\_TOKEN" "${YOUR_ADMIN_TOKEN}" "${CREDENTIAL_FILE}")
    (update_creds "SERVICE\_ENDPOINT" "http\:\/\/127\.0\.0\.1\:35357\/v2.0\/" "${CREDENTIAL_FILE}")
    source_creds "${CREDENTIAL_FILE}"

    echo "Creating Roles..."
    adminrole=$(create_keystone_role "Admin")
    keystone_service_adminrole=$( create_keystone_role "KeystoneServiceAdmin")
    keystone_adminrole=$( create_keystone_role "KeystoneAdmin")
    memberrole=$( create_keystone_role "Member")
    projectrole=$( create_keystone_role "Project1")

    echo "Creating Users..."
    useradmin=$(create_keystone_user "${ADMIN_USER}" "${ADMIN_PASSWORD}")
    userdemo=$(create_keystone_user "${DEMO_USER}" "${DEMO_PASSWORD}")

    echo "Creating Tenants..."
    tenantadmin=$(create_keystone_tenant "admin" "AdminTenant")
    tenantservice=$(create_keystone_tenant "service" "ServiceTenant")
    tenantdemo=$(create_keystone_tenant "demo" "demoTenant")

    echo "Assigning roles to Users..."
    # Add Admin role to admin user with all 3 tenants
    echo "tenant: ${tenantadmin}"
    $(keystone_userrole_add "${useradmin}" "${adminrole}" "${tenantadmin}" )
    $(keystone_userrole_add "${useradmin}" "${adminrole}" "${tenantservice}" )
    $(keystone_userrole_add "${useradmin}" "${adminrole}" "${tenantdemo}" )

    # Add Member role to demo user in the tenant demo
    echo "Adding Member role to demo user in tenant demo"
    $(keystone_userrole_add "${userdemo}" "${memberrole}" "${tenantdemo}" )

    # Add Keystone Admin and KeystoneServiceAdmin demo to the user admin in tenant admin
    echo "Adding keystoneServiceAdmin and KeyStoneAdmin to user 'admin' in tenant 'admin'"
    $(keystone_userrole_add "${useradmin}" "${keystone_service_adminrole}" "${tenantadmin}" )
    $(keystone_userrole_add "${useradmin}" "${keystone_adminrole}" "${tenantadmin}" )

    # Register admin users for nova/glance and associate them with the service tenant
    echo "Registering NOVA/GLANCE Admin users with association to 'service' tenant"
    usernova=$(create_keystone_user "${NOVA_ADMIN_USER}" "${NOVA_ADMIN_PASSWORD}" "${tenantservice}")
    userglance=$(create_keystone_user "${GLANCE_ADMIN_USER}" "${GLANCE_ADMIN_PASSWORD}" "${tenantservice}")

    # Cinder
    local usercinder
    if [ "${OS_DIST}" == "grizzly" ]
    then
	usercinder=$(create_keystone_user "${CINDER_ADMIN_USER}" "${CINDER_ADMIN_PASSWORD}" "${tenantservice}")
	$(keystone_userrole_add "${usercinder}" "${adminrole}" "${tenantservice}" )
    fi

    # Add Admin role to nova/glance admin users in service tenant
    $(keystone_userrole_add "${usernova}" "${adminrole}" "${tenantservice}" )
    $(keystone_userrole_add "${userglance}" "${adminrole}" "${tenantservice}" )


    # legacy catalog template does not work in grizzly, and so it must be done manually
    if [ "${OS_DIST}" == "grizzly" ]
    then
	echo "Setting up Service + EndPoint Configuration for Keystone..."

	# Keystone service
	echo "Creating KeyStone service"
	desc="Keystone Identity Service"
	servicekeystone=$(create_keystone_service "keystone" "identity" "${desc}")
	keystone endpoint-create --region $NOVA_REGION --service-id $servicekeystone \
            --publicurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:${KEYSTONE_PUBLIC_PORT}/v2.0" \
	    --adminurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:${KEYSTONE_ADMIN_PORT}/v2.0" \
            --internalurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:${KEYSTONE_PUBLIC_PORT}/v2.0"
	
	# Nova service
	echo "Creating nova service"
	desc="Nova Compute Service"
	servicenova=$(create_keystone_service "nova" "compute" "${desc}")
	keystone endpoint-create --region $NOVA_REGION --service-id $servicenova \
	    --publicurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:${KEYSTONE_COMPUTE_PORT}/v1.1/\$(tenant_id)s" \
            --adminurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:${KEYSTONE_COMPUTE_PORT}/v1.1/\$(tenant_id)s" \
            --internalurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:${KEYSTONE_COMPUTE_PORT}/v1.1/\$(tenant_id)s"

	# Volume service
	echo "Creating Volume service"
	desc="Nova Volume Service"
	servicevolume=$(create_keystone_service "volume" "volume" "${desc}")
	keystone endpoint-create --region $NOVA_REGION --service-id $servicevolume \
            --publicurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:8776/v1/\$(tenant_id)s" \
            --adminurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:8776/v1/\$(tenant_id)s" \
            --internalurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:8776/v1/\$(tenant_id)s"

        keystone endpoint-create --region $NOVA_REGION --service-id $servicevolume \
            --publicurl "http://127.0.0.1:8776/v1/\$(tenant_id)s" \
            --adminurl "http://127.0.0.1:8776/v1/\$(tenant_id)s" \
            --internalurl "http://127.0.0.1:8776/v1/\$(tenant_id)s"

	# Image service
	echo "Creating Image service"
	desc="Glance Image Service"
	serviceimage=$(create_keystone_service "glance" "image" "${desc}")
	keystone endpoint-create --region $NOVA_REGION --service-id $serviceimage \
            --publicurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:9292" \
            --adminurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:9292" \
            --internalurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:9292"

	# EC2 service
	echo "Creating EC2 Service"
	serviceec2=$(create_keystone_service "ec2" "ec2" "EC2 Compatibility Layer")
	keystone endpoint-create --region $NOVA_REGION --service-id $serviceec2 \
            --publicurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:8773/services/Cloud" \
            --adminurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:8773/services/Admin" \
            --internalurl "http://${KEYSTONE_SERVER_IP_ADDRESS}:8773/services/Cloud"
    fi

    echo "DONE!"
}


function create_keystone_service() {

    local serviceName=$1
    local serviceType=$2
    local serviceDesc=$3
    local service=$(get_id keystone service-create --name "${serviceName}" --type "${serviceType}" --description "${serviceDesc}")
    echo "${service}"
}

function create_keystone_role() {

    local roleName=$1
    local role=$(get_id keystone role-create --name=$roleName)

    echo "${role}"
}

function create_keystone_tenant() {

    local tenant=$1
    local desc=$2
    local tenant_id
    
    tenant_id=$(get_id keystone tenant-create --name "${tenant}" --description "${desc}")
    echo "${tenant_id}"
}

function create_keystone_user() {

    local username=$1
    local userpass=$2
    # local tenant=$3 # May not be specified
    local user_id
    
    if [ $# -eq 3 ]
    then
	user_id=$(get_id keystone user-create --name "${username}" --pass "${userpass}" --tenant-id "$3")
    else
	user_id=$(get_id keystone user-create --name "${username}" --pass "${userpass}")
    fi

    echo "${user_id}"
}

function keystone_userrole_add() {

    local user=$1
    local role=$2
    local tenant=$3

    keystone user-role-add --user-id ${user} --role-id ${role} --tenant-id ${tenant}
}

function gen_euca_key() {
    
    echo "Generating euca-keypair..."
    # Make sure SElinux is disabled
    local status=$(get_SELINUX)
    if [ "${status}" != "disabled" ]
    then
	echo "Disabling SElinux"
	disable_SELINUX
    fi

    # make sure we are in the install directory
    cd ${OS_INSTALL_DIR}
    euca-add-keypair userkey > userkey.pem
    chmod 600 userkey.pem

    echo "DONE!"
}

# Generate new EC2 Token
function gen_ec2_token() {

    echo "Unsetting service_token, service_endpoint env variables"

    local auth_url
    local result
    local glanceresult
    local access_key
    local secret_key
    local cacert="${OS_INSTALL_DIR}/cacert.pem"
    local cert="${OS_INSTALL_DIR}/cert.pem"
    local pk="${OS_INSTALL_DIR}/pk.pem"

    service openstack-nova-cert restart

    echo "Sleeping to give time for nova-cert to boot..."
    sleep 35; # sleep to give time for service to restart

    unset SERVICE_TOKEN
    unset SERVICE_ENDPOINT

    auth_url="http://127.0.0.1:5000/v2.0/"
    (keystone --os-user ${ADMIN_USER}  --os-password ${ADMIN_PASSWORD} --os-tenant-name ${NOVA_ADMIN_TENANT} --os-auth-url=${auth_url} catalog --service ec2)

    echo "Regenerating EC2 credentials Token..."
    unset SERVICE_TOKEN
    unset SERVICE_ENDPOINT
    
    result=$(keystone --os-user ${ADMIN_USER} --os-password ${ADMIN_PASSWORD} --os-tenant-name demo --os-auth-url=${auth_url} ec2-credentials-create)

    echo "result: ${result}"
    
    prop=`echo "${result}" | cut -d '|' -f2`
    values=`echo "${result}" | cut -d '|' -f3`

    accessline=`echo "${prop}" | grep -n "access"`
    secretline=`echo "${prop}" | grep -n "secret"`

    echo "${accessline}"
    echo "${secretline}"

    echo "${values}" > "temp.txt"
    access_key="`sed -n 4p temp.txt`"
    secret_key="`sed -n 5p temp.txt`"
    rm -rf "temp.txt"

    access_key=$(echo "${access_key}" | tr -d ' ')
    secret_key=$(echo "${secret_key}" | tr -d ' ')
    echo "access key: ${access_key}"
    echo "secret key: ${secret_key}"

    (update_creds "EC2\_ACCESS\_KEY" "${access_key}" "${CREDENTIAL_FILE}")
    (update_creds "EC2\_SECRET\_KEY" "${secret_key}" "${CREDENTIAL_FILE}")

    echo "Generating nova certification files..."
    # These require OS_USERNAME to be set
    source_creds "${CREDENTIAL_FILE}"
    (isvarset ${OS_USERNAME} ) && set ${OS_USERNAME:=${ADMIN_USER}}

    cert_enabled=$(is_novaservice_enabled "nova\-cert")

    if [ "${cert_enabled}" == "false" ]
    then
	echo "${cert_enabled}"
	error_exit "nova-cert-not-enabled"
    else
	echo "nova-cert service is enabled"
    fi

    # make sure cacert file does not exit
    set +o errexit
    # not applicable in grizzly release
    if [ "${OS_DIST}" == "folsom" ]
    then
	if [ -e "${cacert}" ]
	then
	    echo "${cacert} file already exists! Deleting to create new one"
	    rm "${cacert}"
	fi

	nova x509-get-root-cert "${cacert}"
        # make sure cacert.pem file is not empty
	if [[ -s "${cacert}" ]] ; then
	    echo "${cacert} has data."
	else
	    echo "${cacert} is empty."
	fi

        # make sure pk file does not exit
	if [ -e "${pk}" ]
	then
            echo "${pk} file already exists! Deleting to create new one"
            rm "${pk}"
	fi
    
	nova x509-create-cert "${pk}" "${cert}"
        # make sure pk.pem file is not empty
	if [[ -s "${pk}" ]] ; then
            echo "${pk} has data."
	else
            echo "${pk} is empty."
	fi
    else
	echo "Not Creating nova x509 permission files for ${OS_DIST} release"
    fi # end of folsom check
    set -o errexit

    echo "updating credentials file with EC2 Keys..."
    (update_creds "EC2\_PRIVATE\_KEY" "${pk}" "${CREDENTIAL_FILE}")
    (update_creds "EC2\_CERT" "${cert}" "${CREDENTIAL_FILE}")
    (update_creds "NOVA\_CERT" "${cacert}" "${CREDENTIAL_FILE}")
    (update_creds "EUCALYPTUS\_CERT" "${cacert}"  "${CREDENTIAL_FILE}")

    unset SERVICE_TOKEN
    unset SERVICE_ENDPOINT

    echo "retrieving new EC2 token for keystone"

    # Leaving tenant as admin, it's not a variable
    result=$(keystone --os-user ${ADMIN_USER} --os-password ${ADMIN_PASSWORD} --os-tenant-name admin --os-auth-url=${auth_url} token-get )
    echo "${result}"
    values=`echo "${result}" | cut -d '|' -f3`
    echo "${values}" > "temp.txt"
    glanceresult="`sed -n 5p temp.txt`"
    rm -rf "temp.txt"

    echo "glanceresult: ${glanceresult}"

    # Now add it to the credentials file
    YOUR_TOKEN=${glanceresult}
    YOUR_TOKEN=$(echo "${YOUR_TOKEN}" | tr -d ' ')
    echo "YOUR_TOKEN=${YOUR_TOKEN}"
    (update_creds "YOUR\_TOKEN" "${YOUR_TOKEN}" "${CREDENTIAL_FILE}" )

    echo "DONE!"
}

# Untar/setup images
function setup_images() {

    local image_loc=$1
    local ramdiskName=${image_loc}"kvm_ramd"
    local kernelName=${image_loc}"kvm_kernel"
    local fsName=${image_loc}"kvm-fs"

    echo "Setting up Images for glance repo"
    if [ ! -e "${image_loc}" ] 
    then
	image_loc=${IMAGE_LOC}
	echo "No Image location specified, using default location: ${image_loc}"
    fi

    # go to the directory and unzip/untar if necessary
    cd ${image_loc}

    # Only tar if need to
    if [ ! -e "${ramdiskName}" ] && [ ! -e "${kernelName}" ] && [ ! -e "${fsName}" ]
    then
	verbose && echo "bunzipping files ..."
	bunzip2 *.bz2
	verbose && echo "Untarring files ..."
	tar xvf *.tar
    else
	echo "Files already untarred!"
    fi

    echo "DONE!"
}

function remove_install_files() {

    echo "Removing Installed Files ..."
    eval "bash erase-all.sh"
    eval "bash clean.sh"
    echo "DONE!"
}

# Function to remove Images/Files from Glance Repo
function remove_glance_images() {
    
    set +o errexit

    local option=$1
    local name=$2
    local iamgeline
    local numImages
    local listing
    local id_list
    local imageID
    local command
    # Need to perform a glance index and get all image IDs
    # and store them in an array

    listing=$(glance index)

    echo "Glance Repo has ${numImages}"

    if [ "${option}" = "clean" ] 
    then
	# remove all images
	echo "Removing All Images..."
	glance clear;
	rm -rf /var/lib/glance/images/*
    elif [ "${option}" == "image" ]
    then
	imageline=`echo "${listing}" | grep "${name}"`
	id_list=`echo "${imageline}" | cut -d ' ' -f1`;
	imageiD=`echo "${id_list}"`
	echo "Deleting Image Name: ${name}"
	command="glance -A ${YOUR_TOKEN} delete ${imageID}"
	$(eval "${command}" )
    fi

    set -o errexit
    echo "Done!"
}

# Add Images/Files to Glance Repo
function setup_glance_repo() {

    set -o errexit

    echo "Setting up Glance Repository with default images from path: ${IMAGE_LOC}"

    local dir=${IMAGE_LOC}
    local ramdiskName=${dir}"initrd"
    local kernelName=${dir}"vmlinuz"
    local fsName=${dir}"kvm-fs"

    local listing
    local id_list
    local imageline
    local command
    local ramdisk_id
    local kernel_id
    local fs_id

    # Make sure files exist
    if [ ! -e "${ramdiskName}" ]
    then
        echo "ramdisk file: ${ramdiskName} does not exist"
	error_exit ""
    fi

    if [ ! -e "${kernelName}" ]
    then
        echo "kernel file: ${kernelName} does not exist"
        error_exit ""
    fi

    if [ ! -e "${fsName}" ]
    then
        echo "fs file: ${fsName} does not exist"
        error_exit ""
    fi

    # Make sure glance user has sufficient permissions on write storage
    command="chown -R ${GLANCE_ADMIN_USER}:${GLANCE_ADMIN_USER} /var/lib/glance"
    $(eval "${command}" )

    # TODO: Make architecture parameter use bash architecture variable
    echo "Adding ramdisk to glance repo ..."
    command="glance -A ${YOUR_TOKEN} add name=\"kvm_ramd\" disk_format=ari container_format=ari is_public=True architecture=x86_64 < ${ramdiskName}"
    echo "${command}"
    ramdisk_id=$(eval "${command}" )

    listing=$(glance index)
    imageline=`echo "${listing}" | grep "kvm_ramd"`
    echo "ImageLine: ${imageline}"
    id_list=`echo "${imageline}" | cut -d ' ' -f1`; 
    ramdisk_id=`echo "${id_list}"`
    echo "SUCCESS! -- ramdisk imageID: ${ramdisk_id}"

    echo "Adding kernel to glance repo ..."
    command="glance -A ${YOUR_TOKEN} add name=\"kvm_kernel\" disk_format=aki container_format=aki is_public=True architecture=x86_64 < ${kernelName}"
    kernel_id=$(eval "${command}" )

    listing=$(glance index)
    imageline=`echo "${listing}" | grep "kvm_kernel"`
    echo "ImageLine: ${imageline}"
    id_list=`echo "${imageline}" | cut -d ' ' -f1`;
    kernel_id=`echo "${id_list}"`
    echo "SUCCESS! -- kernel imageID: ${kernel_id}"

    echo "Adding kvm-FS to glance repo ..."
    command="glance -A ${YOUR_TOKEN} add name=\"kvm_fs\" disk_format=ami container_format=ami is_public=True ramdisk_id=${ramdisk_id} kernel_id=${kernel_id} architecture=x86_64 < ${fsName}"
    echo "${command}"
    fs_id=$(eval "${command}" )
    echo "SUCCESS! -- fs imageID: ${fs_id}"

    echo "DONE!"
}

### Main Routine ###

# start log file
start_log

# Log xtrace to the log file when enabled
exec 3>>$LOG_FILE
BASH_XTRACEFD=3

# check distro version + root permission
check_distro
check_root_perm

# process command line -- pass all commandline args to function
process_command_line "$@"

parse_configFile_defaults
check_params

if [ ${INSTALL} == "clean" ]
    then
    clean_mysql
    clean
    exit 1
elif [ ${INSTALL} == "fullclean" ]
then
    clean_all
    exit 1
elif [ ${INSTALL} == "cleanmysql" ]
    then
    remove_glance_images "image" "kvm_kernel"
    remove_glance_images "image" "kvm_ramd"
    remove_glance_images "image" "kvm-fs"
    clean_mysql
    echo "Killing processes"
    kill_process "openstack-keystone"
    kill_process "openstack-glance"
    kill_process "openstack-nova"
    echo "cleanmysql DONE!"
    exit 1
elif [ ${INSTALL} == "genec2token" ]
    then
    gen_ec2_token
    exit 1
elif [ ${INSTALL} == "geneucakey" ]
    then
    gen_euca_key
    exit 1
elif [ ${INSTALL} == "backup" ]
    then
    create_backup
    exit 1
elif [ ${INSTALL} == "restore" ]
    then
    restore_original
    exit 1
fi

verify_install

# Any use of uninitialized variable will exit
# Set it here and not at top of script to allow
# default parameters to be used if none specified
set -o nounset

# configure repositories for package installation
set +o errexit
if [ "${INSTALL_STEP}" == "1" ]
then
    set -o errexit
    echo "<============ Step (1/21)  Started  =============>"
    config_yum_repos "all"
    echo "<============ Step (1/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Setup repositories
set +o errexit
if [ "${INSTALL_STEP}" == "2" ]
then
    set -o errexit
    echo "<============ Step (2/21)  Started  =============>"   
    config_iso_repos
    echo "<============ Step (2/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Mount the ISOs
set +o errexit
if [ "${INSTALL_STEP}" == "3" ]
then
    set -o errexit
    echo "<============ Step (3/21)  Started  =============>"
    mount_isos
    echo "<============ Step (3/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Install yum priority-plugin package
set +o errexit
if [ "${INSTALL_STEP}" == "4" ]
then
    set -o errexit
    echo "<============ Step (4/21)  Started  =============>"
    install_yum_pri "all"
    echo "<============ Step (4/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# install necessary package
set +o errexit
if [ "${INSTALL_STEP}" == "5" ]
then
    set -o errexit
    echo "<============ Step (5/21) Started   =============>"
    install_gnu_packages "all"
    install_ntp "all"
    echo "<============ Step (5/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Now update the priority field as well                                                   
#update_repo_pri

# Install kernel
set +o errexit
if [ "${INSTALL_STEP}" == "6" ] && [ "${DO_KERNEL_INSTALL}" == "true" ]
then
    set -o errexit
    echo "<============ Step (6/21)  Started  =============>"
    update_kernel "install"
    echo "<============ Step (6/21) Completed =============>"
    let INSTALL_STEP+=1
elif [ "${INSTALL_STEP}" == "6" ] && [ "${DO_KERNEL_INSTALL}" == "false" ]
then
    echo "Skipping Kernel Upgrade Step as Kernel-Upgrade flag is disabled"
    let INSTALL_STEP+=1
fi

# Install openstack
set +o errexit
if [ "${INSTALL_STEP}" == "7" ]
then
    set -o errexit
    echo "<============ Step (7/21)  Started  =============>"

    install_openstack "all"
    # Copy example files after installing nova-install package
    setup_example_files

    echo "<============ Step (7/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure the network
set +o errexit
if [ "${INSTALL_STEP}" == "8" ]
then
    set -o errexit
    echo "<============ Step (8/21)  Started  =============>"
    config_network
    echo "<============ Step (8/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure  DashBoard
set +o errexit
if [ "${INSTALL_STEP}" == "9" ]
then
    echo "<============ Step (9/21)  Started  =============>"
    if [ "${OS_DIST}" == "folsom" ]
    then
	set -o errexit
	config_horizon
    elif [ "${OS_DIST}" == "grizzly" ]
    then
	set -o errexit
	config_openstack_dashboard
    else
	echo "Unknown openstack distribution: ${OS_DIST} for configuring dashboard"
	error_exit ""
    fi
    echo "<============ Step (9/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure ipTable setting
set +o errexit
if [ "${INSTALL_STEP}" == "10" ]
then
    set -o errexit
    echo "<============ Step (10/21)  Started  =============>"
    setup_firewall
    echo "<============ Step (10/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Install MySQL/RabbitMQ
set +o errexit
if [ "${INSTALL_STEP}" == "11" ]
then
    set -o errexit
    echo "<============ Step (11/21)  Started  =============>"
    install_mysql "all"
    echo "<============ Step (11/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure MYSQL
set +o errexit
if [ "${INSTALL_STEP}" == "12" ]
then
    set -o errexit
    echo "<============ Step (12/21)  Started  =============>"
    setup_mysql
    echo "<============ Step (12/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure KeyStone
set +o errexit
if [ "${INSTALL_STEP}" == "13" ]
then
    set -o errexit
    echo "<============ Step (13/21)  Started  =============>"
    setup_credentials
    setup_keystone
    echo "<============ Step (13/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure Glance
set +o errexit
if [ "${INSTALL_STEP}" == "14" ]
then
    echo "<============ Step (14/21)  Started  =============>"
    configure_glance
    echo "<============ Step (14/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Configure NOVA
set +o errexit
if [ "${INSTALL_STEP}" == "15" ]
then
    echo "<============ Step (15/21)  Started  =============>"
    configure_nova
    if [ "${OS_DIST}" == "grizzly" ]
    then
	configure_cinder
    fi
    echo "<============ Step (15/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Run hpc-Script
set +o errexit
if [ "${INSTALL_STEP}" == "16" ]
then
    set -o errexit
    echo "<============ Step (16/21)  Started  =============>"
    run_hpc_script
    echo "<============ Step (16/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# restart all services
set +o errexit
if [ "${INSTALL_STEP}" == "17" ]
then
    set -o errexit
    echo "<============ Step (17/21)  Started  =============>"
    restart_services
    echo "<============ Step (17/21) Completed =============>"
    let INSTALL_STEP+=1
fi
# In order to enable keystone to provide authentication
# service_token, service_endpoint need to be sourced
source_creds "${CREDENTIAL_FILE}"

# Create keystone credentials
set +o errexit
if [ "${INSTALL_STEP}" == "18" ]
then
    set -o errexit
    echo "<============ Step (18/21)  Started  =============>"
    create_keystone_creds
    echo "<============ Step (18/21) Completed =============>"
    let INSTALL_STEP+=1
fi

set +o errexit
if [ "${INSTALL_STEP}" == "19" ]
then
    set -o errexit
    echo "<============ Step (19/21)  Started  =============>"
    gen_ec2_token
    echo "<============ Step (19/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Add Images to glance repo
set +o errexit
if [ "${INSTALL_STEP}" == "20" ]
then
    set -o errexit
    echo "<============ Step (20/21)  Started  =============>"
    setup_images "${IMAGE_LOC}"
    setup_glance_repo
    echo "<============ Step (20/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Generate euca-key-pair
set +o errexit
if [ "${INSTALL_STEP}" == "21" ]
then
    set -o errexit
    echo "<============ Step (21/21)  Started  =============>"
    gen_euca_key
    echo "<============ Step (21/21) Completed =============>"
    let INSTALL_STEP+=1
fi

# Finalize log
finalize_log 'installation process complete'

exit $EX_OK
