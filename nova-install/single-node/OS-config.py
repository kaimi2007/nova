#!/usr/bin/python

# OS-config.py                                                                                            
# Malek Musleh
# mmusleh@isi.edu
# May. 14, 2013
#
# (c) 2013 USC/ISI
# Filename: OS-config.py

import iniparse
import os
import sys
import subprocess

import MySQLdb as mdb
import yaml

def parse_config(fname):
    """Read the YAML config file and return a dict with the values"""
    data = yaml.load(open(fname))
    return data

def get_config_value(config, parameter):

    admin=config['admin']
    adminPass=config['adminPass']

    entry = config.get('defaults', None)
    value = entry.get(parameter, None)
    assert(value != 'None') # Sanity Check
    print "%s" % value

def version():
    try:
        con = mdb.connect('localhost', 'root',
                          'R%Fd3vhk', 'mysql');
        cur = con.cursor()
        cur.execute("SELECT VERSION()")

        data = cur.fetchall()

        print "DATABASE VERSION: %s" % data

    except mdb.Error, e:

        print "Error %d: %s" % (e.args[0],e.args[1])
        sys.exit(1)

    finally:
        if con:
            con.close()

# Python Routine to clean all users + Databases from MySQL
def clean_all(config):

    admin=config['admin']
    adminPass=config['adminPass']

    delete_db_user(config, "nova", "MYSQL_NOVA")
    delete_db_user(config, "glance", "MYSQL_GLANCE")
    delete_db_user(config, "keystone", "MYSQL_KEYSTONE")
    delete_db_user(config, "cinder", "MYSQL_CINDER")

    delete_db(config, "nova")
    delete_db(config, "keystone")
    delete_db(config, "glance")
    delete_db(config, "cinder")

def run_command(command):
    print "Running Command: %s" % command
    p = subprocess.Popen(command,
                         shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b'')

def create_keystone_role(config, roleName):

    print "Creating keystone Role: %s" % roleName
    command="keystone role-create --name %s" % roleName
    role_line=""
    role_id=""
    for line in run_command(command):
        if "id" in line:
            role_line = line
            vals=line.split('|')
            role_id=vals[2].strip()

    assert(role_id != "")
    print "role_id: %s" % role_id
    return role_id


# Create a user in Keystone with the specified Name and Password
def create_keystone_user(config, user, userpass, role, tenant):
    print "Creating keystone User %s with tenant: %s" % (user, tenant)
    assert(tenant != "")

    command="keystone user-create --name %s --pass %s --tenant-id %s" % (user, userpass, tenant)
    print "keystone_user_create command: %s" % command
    id_line=""
    id=""
    for line in run_command(command):
        #print(line)
        if "id" in line:
            id_line=line
            vals=line.split('|')
            #print "vals:", vals
            id=vals[2].strip()
            
    print "id: %s" % id
    return id

# Create a tenant in Keystone with the specified Name and Description
def create_keystone_tenant(tenant, desc):
    print "create_keystone_tenant: %s" % tenant
    command=""
    if desc == "":
        command="keystone tenant-create --name %s" % tenant
    else:
        command="keystone tenant-create --name %s --description %s" % (tenant, desc)
    print "keystone_tenant_create command: %s" % command
    id_line=""
    id=""
    for line in run_command(command):
        print line
        if "id" in line:
            id_line=line
            vals=line.split('|')
            id=vals[2].strip()

    print "id: %s" % id
    return id

# Python Function to list MYSQL Databases
def list_mysql_db():
    
    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql');

        cur = con.cursor()
        cur.execute("show databases;")

        data = cur.fetchall()
        for row in data:
            print row

    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0],e.args[1])
        sys.exit(1)

    finally:
        if con:
            con.close()

# Delete the database from MYSQL
def delete_db(config, dbName):

    admin=config['admin']
    adminPass=config['adminPass']

    print "Deleting database %s" % dbName

    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql');

        cur = con.cursor()

        command = ("DROP DATABASE IF EXISTS %s") % dbName;
        print "command: %s" % command
        cur.execute(command)

    except mdb.Error, e:

        print "Error %d: %s" % (e.args[0],e.args[1])
        sys.exit(1)

    finally:
        if con:
            con.close()

# Create a new Database in MYSQL
def create_db(config, dbName):

    admin=config['admin']
    adminPass=config['adminPass']
    con=None

    print "Creating database %s" % dbName
    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql');

        cur = con.cursor()

        command = ("CREATE DATABASE IF NOT EXISTS %s") % dbName;
        print "command: %s" % command
        cur.execute(command)
        
    except mdb.Error, e:
        
        print "Error %d: %s" % (e.args[0],e.args[1])
        sys.exit(1)
        
    finally:
        if con:
            con.close()

# Check to see if user is in database
def is_user_in_db(config, userName, dbName):

    admin=config['admin']
    adminPass=config['adminPass']
    entry = config.get(userName, None)

    user = entry.get('user', None)
    password = entry.get('password', None)
    con=None
    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql')
        cur = con.cursor()

        command = ("select User from mysql.user;")
        cur.execute(command)
        userlist = cur.fetchall()

        for line in userlist:
            if user in line:
                print "User %s exists in database" % user
                return True

        # User not found
        print "User %s not Found in db" % user
        return False
        
    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0], e.args[1])
        sys.exit(1)
        

    finally:
        if con:
            con.close()

# Create a new User for specified Database in MYSQL
def create_db_user(config, dbName, userName):

    admin=config['admin']
    adminPass=config['adminPass']
    entry = config.get(userName, None)

    user = entry.get('user', None)
    password = entry.get('password', None)

    print "Creating new user/password: %s %s for db: %s" % (user, password, dbName)

    # Check to make sure user doesn't already exist
    user_found = is_user_in_db(config, userName, dbName)

    if user_found:
        print "User %s already exists not recreating" % user
        return

    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql')
        cur = con.cursor()
        
        # Create the user
        if not user_found:
            command=("CREATE USER \'%s\'" % user) + "@'%\'" + (" IDENTIFIED BY \'%s\';" % password)
            print "Command: %s" % command
            cur.execute(command)

            command=("CREATE USER \'%s\'" % user) + "@'localhost\'" + (" IDENTIFIED BY \'%s\';" % password)
            cur.execute(command)

        # Set the privileges (do so again even if the user already exists)
        command=("GRANT ALL PRIVILEGES ON %s.* TO '%s'@\'") % (dbName, user) + "%\' WITH GRANT OPTION;"
        print "Command: %s" % command
        cur.execute(command)
         
        command=("GRANT ALL PRIVILEGES ON %s.* TO '%s'@\'localhost\'") % (dbName, user) + " WITH GRANT OPTION;"
        print "Command: %s" % command
        cur.execute(command)

        # if dbName == nova, then permission needs to be granted to the bridge too

        command=("GRANT ALL PRIVILEGES ON %s.* TO '%s'@\'10.99.0.1\'") % (dbName, user) + " WITH GRANT OPTION;"
        print "Command: %s" % command
        cur.execute(command)

        # Need to flush to force db to reread permissions
        command ="FLUSH PRIVILEGES";
        cur.execute(command)

        # Always delete the wildcard user
        command = "DELETE FROM mysql.user WHERE user = '';"
        cur.execute(command)
        command = "FLUSH PRIVILEGES;"
        cur.execute(command)

    except mdb.Error, e:
        print "Error %d: %s" % (e.args[0],e.args[1]) 
        sys.exit(1)


    finally:
        if con:
            con.close()


# Delete a user from the Database
def delete_db_user(config, dbName, userName):

    admin=config['admin']
    adminPass=config['adminPass']

    print "deleting userName %s" % userName

    entry = config.get(userName, None)
    user = entry.get('user', None)
    password = entry.get('password', None)

    print "Deleting new user/password: %s %s for db: %s" % (user, password, dbName)
    # Check to make sure user exists                                                                         
    user_found = is_user_in_db(config, userName, dbName)
    if user_found:

        try:
            con = mdb.connect('localhost', admin,
                              adminPass, 'mysql')
            cur = con.cursor()

            command="DELETE FROM mysql.user WHERE user = '%s';" % user
            cur.execute(command)
            command=("DROP USER \'%s\'" % user) + "@'%\'"
            cur.execute(command)
            command=("DROP USER \'%s\'" % user) + "@'localhost\'"
            cur.execute(command)
            command ="FLUSH PRIVILEGES";
            cur.execute(command)

        except mdb.Error, e:
            print "Error %d: %s" % (e.args[0],e.args[1])
            sys.exit(1)

        finally:
            if con:
                con.close()

    else:
        print "User %s does not Exist, cannot delete" % user

def configure_glance(config):

    print "Configuring glance ..."

    admin=config['admin']
    adminPass=config['adminPass']
    mysql_glance_user=config['MYSQL_GLANCE']['user']
    mysql_glance_password=config['MYSQL_GLANCE']['password']

    print "admin: %s" % admin
    print "adminPass: %s" % adminPass

    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql');
        cur = con.cursor()

        # Create the Glance Database                                               
        create_db(config, "glance")

        # Create the glance user
        create_db_user(config, "glance", "MYSQL_GLANCE")

    except mdb.Error, e:
         print "Error %d: %s" % (e.args[0],e.args[1])


def configure_nova(config):
                      
    print "Configuring nova ..."

    admin=config['admin']
    adminPass=config['adminPass']

    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql');
        cur = con.cursor()

        # Create the NOVA Database                                                      
        create_db(config, "nova")

        # Create the nova user                                                           
        create_db_user(config, "nova", "MYSQL_NOVA")

    except mdb.Error, e:
         print "Error %d: %s" % (e.args[0],e.args[1])


# configure cinder
def configure_cinder(config):

    print "Configuring cinder ..."

    admin=config['admin']
    adminPass=config['adminPass']

    try:
        con = mdb.connect('localhost', admin,
                          adminPass, 'mysql');
        cur = con.cursor()

        # Create the Cinder Database
        create_db(config, "cinder")
        # Create the cinder user 
        create_db_user(config, "cinder", "MYSQL_CINDER")

    except mdb.Error, e:
         print "Error %d: %s" % (e.args[0],e.args[1])


def configure_usage():
    sys.stderr.write(sys.argv[0] +
                     " --set|--del config_file section [parameter] [value]\n")
    sys.exit(1)

# General configuration method that reads in config-filename, parameter, and value
# as arguments to update
def configure(cfgfile, section, mode, parameter, value):
    try:
        if mode not in ('--set', '--del'):
            configure_usage()
            
        if mode == '--set':
            if parameter is None or value is None:
                configure_usage()
        else:
            if mode == '--del' and value is not None:
                configure_usage()
    except IndexError:
        configure_usage()

    conf = iniparse.ConfigParser()
    conf.readfp(open(cfgfile))

    if mode == '--set':
        if not conf.has_section(section):
            conf.add_section(section)
            value += '\n'
        conf.set(section, parameter, value)
    else:
        if parameter is None:
            conf.remove_section(section)
        elif value is None:
            conf.remove_option(section, parameter)

    with open(cfgfile, 'w') as f:
        print "Updating File: %s Section: %s | parameter: %s | value: %s" % (cfgfile, section, parameter, value)
        conf.write(f)

# Initialize keystone Database Authentication
def initialize_keystone(config):

    print "Initializing keystone authentication ..."

    admin=config['admin']
    adminPass=config['adminPass']

    print "admin: %s" % admin
    print "adminPass: %s" % adminPass
    
    # Create the keystone Database
    create_db(config, "keystone")
    # Create the keystone user
    create_db_user(config, "keystone", "MYSQL_KEYSTONE")



#############################
# MAIN               
#############################
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print "Usage: OS-config.py config-file.yaml module-to-execute"
        print "OR"
        print "OS-config.py config-file.yaml module-to-execute parameter"
        sys.exit(-1)

    config_file = parse_config("config.yaml")

    try:
        module_name = sys.argv[2]
    except:
        print "No Module Name Specified"
        sys.exit(-1)

    try:
        parameter_name = sys.argv[3]
    except:
        parameter_name = ""

    if   module_name == "version":
        version()
    elif module_name == "get_config_value":
        get_config_value(config_file, parameter_name)
    elif module_name == "initialize_keystone":
        initialize_keystone(config_file)
    elif module_name == "configure_keystone":
        configure_keystone(config_file)
    elif module_name == "configure_glance":
        configure_glance(config_file)
    elif module_name == "configure_nova":
        configure_nova(config_file)
    elif module_name == "configure_cinder":
        configure_cinder(config_file)
    elif module_name == "delete_db_user":
        dbName = sys.argv[3]
        userName = sys.argv[4]
        delete_db_user(config_file, dbName, userName)
    elif module_name == "create_keystone_user":

        try:
            user = sys.argv[3]
            password = sys.argv[4]

        except:
            "User Name and Password Not Specified on command line"
            sys.exit(1)

        create_keystone_user(config_file, user, password, "", "")
 
    elif module_name == "create_keystone_role":
        create_keystone_role(config_file, "Admin")
    elif module_name == "create_keystone_tenant":

        try:
            tenant = sys.argv[3]
            desc   = sys.argv[4]
        except:
            "Tenant Name and/or description not Specified on command line"
            sys.exit(1)

        create_keystone_tenant(tenant, desc)
    elif module_name == "configure":
        try:
            mode = sys.argv[3]
            cfgfile = sys.argv[4]
            section = sys.argv[5]
            parameter = sys.argv[6]
            value = sys.argv[7]

            configure(cfgfile, section, mode, parameter, value)
        except:
            print "Not enough parameters specified for configure()"
            configure_usage()
    elif module_name == "clean":
        clean_all(config_file)
    else:
        print "Unrecognized Module Name: %s" % module_name

