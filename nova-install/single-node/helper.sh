#!/bin/bash
# helper.sh              
# Malek Musleh                
# mmusleh@isi.edu             
# Feb. 6, 2013          
#             
# (c) 2013 USC/ISI                          
#                                                     
# This script is provided for a reference only.                               
# Its functional correctness is not guaranteed.   
# This file just contains helper functions that can be sourced in from 
# other "Main" bash scripts

# Install a package
function install_package() {
    local pkgName=$1
    yum install "${pkgName}"
}

# Function to test if a certain package is installed
function is_installed() {
    set +o errexit
    local pkgName=$1
    local installed
    local ret=$(rpm -qa | grep "${pkgName}")
    if [ -z "${ret}" ]
    then
	installed="NO"
    else
	installed="YES"
    fi
    set -o errexit
    echo "${installed}"
}

# Function to kill process with string parameter
function kill_process() {

    set +o errexit
    kill $(ps aux | grep "${1}" | awk '{print $2}')
    set -o errexit
}

# Display hostname 
# host (FQDN hostname), for example, vivek (vivek.text.com)
function getHostName(){
    [ "$OS" == "FreeBSD" ] && echo "$($HOSTNAME -s) ($($HOSTNAME))" || :
[ "$OS" == "Linux" ] && echo "$($HOSTNAME) ($($HOSTNAME -f))" || :

}

# Check distribution version
function check_distro() {

    local installed=$(is_installed "redhat-lsb" )
    local release

    if [ "${installed}" == "NO" ]
    then
	echo "Need to install lsb-release package for checking distro version"
	yum install redhat-lsb
    fi

    release=$(lsb_release -r | awk '{print $2}') 
    if [ "${release}" != "6.1" ] && [ "${release}" != "6.3" ]
    then
	echo "[WARNING] Current Operating System Version: ${release} not part of official tested platforms"
    else
        echo "Verified running supported OS distro"
    fi
}

# Check that we are running as root                                                                         
function check_root_perm() {
if [ "$(id -u)" != "0" ]; then
    msg="This-script-must-be-run-as-root"
    error_exit $msg
fi
}

function get_id () {
    echo `"$@" | grep ' id ' | awk '{print $4}'`
}

function get_ec2_secretkey() {
    echo `"$@" | grep ' secret ' | awk '{print $3}'`
}

function get_ec2_accesskey() {
    echo `"$@" | grep ' access ' | awk '{print $2}'`
}

# Function to check whether or not there is enough
# free space
function has_enough_space() {

    local loc=$(get_free_space "${1}" )
    local size=$2    
}

# Function to return the amount of free space for a specified directory
function get_free_space() {

    set +o errexit
    local loc=$1
    if [ -z "${loc}" ]
    then
	loc="./"
    fi

    set -o errexit
    echo $(($(stat -f --format="%a*%S" ${loc} )))
}

# Function to determine the number of network cards a machine has
function get_num_nics() {
    
    local listing=$(lspci | egrep -i 'ethernet')
    echo "$listing" | wc -l
}

# Print message to stderr and exit with the given status code, if one was supplied                          
function error_exit() {

    set +o nounset

    local message="$1"
    local status="$2"
    local max_status=255  # highest legal status code                                                   
    set -o xtrace
    echo "ERROR: $message" 1>&2
    set +o xtrace

    finalize_log 'installation process aborted due to error'
    
    if is_integer "$status" "$max_status"; then
        exit $status
    else
        exit 1
    fi

    set -o nounset
}


# Return whether or not the provided input is an integer, and optionally, less 
# than or equal to the given maximum
function is_integer() {
    local input="$1"
    # maximum might not be set
    set +o nounset
    local maximum="$2"
    set -o nounset

    case "$input" in
                # reject the following:
                #   empty strings
                #   anything other than digits
        ""|*[!0-9]*) return 1 ;;
    esac

    if [[ -n $maximum ]]; then
        (( $input <= $maximum ))
    fi
}

# Display a subsection separator with the provided message
function subsection_banner() {
    echo -e "\n$*"
    echo -e "${*//?/#}\n"
}

# Create the log file (if necessary) and append a timestamp
function start_log() {
    # delete the log file if it exists from previous installation
    rm -rf ${LOG_FILE}
    set -o xtrace
    touch ${LOG_FILE}
    chmod 600 ${LOG_FILE}
    set +o xtrace
    echo "$(date) $BASENAME: installation process initiated ($PARAMETERS)" >> $LOG_FILE

}

# Remove clutter from log and append a timestamp                                                            
function finalize_log() {
    local message="$1"
    cd ${OS_INSTALL_DIR}
    sed -i'' -e '/^+ set +o xtrace$/d' $LOG_FILE
    echo "$(date) $BASENAME: $message ($PARAMETERS)" >> $LOG_FILE
}

# Function to check status of service
function service_status() {
    local serv="$1"
    local ret=`service $serv status`
    echo ${ret}
}

# Restart service specified by parameter                                                                    
function restart_service() {
    local serv="$1"
    service $serv restart
}

function isvarset(){
    local v="$1"
    #[[ ! ${!v} && ${!v-unset} ]] && echo "Variable ${v} not found." || echo "Variable ${v} found."         
    [[ ! ${!v} && ${!v-unset} ]] || echo "is set"
}

function isDirEmpty() {

    local dir=$1
    [[ $(ls -A ${dir} ) ]] && echo "false" || echo "true"
}


function ismounted() {
    local y="$1"
    local __ret
    echo "Checking to see if ${y} is mounted..."
    if [[ $(mountpoint ${y} )  ]]
    then
        echo "mounted"
        return 1
    else
        echo "not-mounted"
        return 0
    fi
}

# Disable SELINUX                                                                                           
function disable_SELINUX() {
    set +o errexit
    setenforce 0
    set -o errexit
}

# return status of SELinux
function get_SELINUX() {
    local res=$(sestatus)
    echo "${res}" > "sestatus.txt"
    local status=`grep -w "disabled" "sestatus.txt"`
    if [ -s "sestatus.txt" ]
    then
        echo "disabled"
    else
        echo "enabled"
    fi
    rm -rf "sestatus.txt"
}

# Function to check if nova-services are ok                                                                 
function is_novaservice_enabled() {

    set +o errexit

    local service=$1
    local host=""
    local status=""
    local zone=""
    local state=""
    local found=false
    local count=0
    local result=$(nova-manage service list)
    declare -a array=$(nova-manage service list)
    declare -a arr

    temp=$(echo ${array} | tr " " "|")
    userList=`echo ${temp} | sed 's/^|//; s/|$//; s/[ ]*|[ ]*/|/g;'`
    echo "${userList}"
    oIFS="$IFS"; IFS='|'

    for line in $userList; do
        arr=($line)
        binary=${arr[0]}
        count=$((count+1))

        if [ "${binary}" == "${service}" ]
        then
            found="true"
            binary=${line}
        elif [ "${found}" == "true" ]
        then
            if [ -z "${host}" ]
            then
                host=${line}
            elif [ -z "${zone}" ]
            then
                zone=${line}
            elif [ -z "${status}" ]
            then
                status=${line}
            elif [ -z "${state}" ]
            then
                state=${line}
            fi
        else
            continue;
        fi
    done

    IFS="$oIFS"
    if [ "${status}" == "enabled" ] && [ "${state}" == ":-)" ]
    then
	echo "true"
    else
	echo "false"
    fi

    set -o errexit
}

# Function to delete certain variable credentials
function delete_creds() {

    set +o errexit
    local filename="/root/openrc"
    local var=$1

    if [ -e "{var}" ]
	then
	filename=${var}
    fi

    echo "Deleting ${var} from credentials file"
    sed "/${var}/d" ${filename} > "temp.txt"
    mv "temp.txt" ${filename}

    set -o errexit
    source_creds "${filename}"
}

# Source Environment Credentials                                                                           
# Specify default credential file                                                                          
function source_creds() {

    set +o errexit
    local filename=$1

    if [ ! -e "${filename}" ]
    then
	filename="/root/openrc"
    fi

    echo "Sourcing Credentials File: ${filename}"
    if [ -e "${filename}" ]
    then
        source ${filename} 
    else
        echo "Credentials File: ${filename} does not exist, cannot source!"
    fi
    echo "DONE!"
}

# Update credentials and then source it to ENV
function update_creds() {

    set +o errexit

    local var=$1
    local newval=$2
    local filename=$3
    local replace="*export "${var}"*"
    local newstr="export "${var}"\="${newval}
    local found

    if [ ! -e "${filename}" ]
    then
	filename="/root/openrc"
    fi

    echo "Updating Credentials File: ${filename}"
    if [ -e "${filename}" ]
    then
        # file exists, now find variable in file
	found=$(grep -m 1 ${var} ${filename} )
        if [ -n "${found}" ]
        then
            echo "Variable: ${var} found!"
            echo "oldstr: ${replace} | newstr: ${newstr}"
	    delete_creds "${var}"
            # sed "$ a ${newstr}" ${filename} > "temp.txt"
            #sed "s/${replace}/${newstr}/g" ${filename} > "temp.txt"
            # mv "temp.txt" ${filename}
        else
            echo "Variable: ${var} not found!, adding it to credentials file..."
	fi

        echo "newstr: ${newstr}"
        sed "$ a ${newstr}" ${filename} > "temp.txt"
        mv "temp.txt" ${filename}

    else
        echo "Credentials File: ${filename} does not exist, cannot source!"
    fi

    set -o errexit

    source_creds "${filename}"
}