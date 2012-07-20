%global prj nova
%global with_doc 0
%global short_name openstack-nova
#%global os_release essex
#KDS
%global isi_prj openstack-nova

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

Name:             %{short_name}
Version:          2012.6
#Version:          2012.1
#Release:	b3119
Release:	  essex
Epoch:            1
Summary:          OpenStack Compute (nova)

Group:            Development/Languages
License:          ASL 2.0
Vendor:           Grid Dynamics Consulting Services, Inc. / USC Information Sciences Institute
URL:              http://openstack.org/projects/compute/
Source0:          nova-%{version}.tar.gz  
Source1:          %{short_name}-README.rhel6
Source6:          %{short_name}.logrotate

# Initscripts
Source11:         %{prj}-api.init
Source12:         %{prj}-compute.init
Source13:         %{prj}-network.init
Source14:         %{prj}-objectstore.init
Source15:         %{prj}-scheduler.init
Source16:         %{prj}-volume.init
Source17:         %{prj}-direct-api.init
Source18:         %{prj}-ajax-console-proxy.init
Source19:         %{prj}-xvpvncproxy.init
#KDS changed from nova-sudoers to ISI's file
Source20:         openstack-nova-sudoers
Source21:         %{short_name}-polkit.pkla
Source22:         %{short_name}-rhel-ifc-template
#AP: moved nova.conf to ./etc/nova/ in the repo
#Source23:         nova.conf
Source25:         %{prj}-api-os-compute.init
Source26:         %{prj}-api-os-volume.init
#Source28:         api-paste.ini
Source29:         %{prj}-cert.init

#KDS ISI's service files
#AP: these files have been moved inside repo, not required
##Source30:       openstack-nova-ajax-console-proxy
##Source31:       openstack-nova-api
##Source32:       openstack-nova-compute
##Source33:       openstack-nova-db-setup
##Source34:       openstack-nova-direct-api
##Source35:       openstack-nova-network
##Source36:       openstack-nova-objectstore
##Source37:       openstack-nova-scheduler
##Source38:       openstack-nova-vncproxy
##Source39:       openstack-nova-volume
##Source40:	openstack-nova-cert
##Source41:	dhcp_release

#KDS
%define usrlocaldir /usr/local


Patch0001:        0001-fix-useexisting-deprecation-warnings.patch


BuildRoot:        %{_tmppath}/nova-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:        noarch
BuildRequires:    python-devel
BuildRequires:    python-setuptools
BuildRequires:    python-distutils-extra >= 2.18
BuildRequires:    python-netaddr
BuildRequires:    python-lockfile >= 0.8
BuildRequires:    python-eventlet >= 0.9.16

BuildRequires:    python-nose
BuildRequires:    python-IPy
BuildRequires:    python-boto
BuildRequires:    python-gflags
BuildRequires:    python-routes >= 1.12.3
BuildRequires:    python-sqlalchemy
BuildRequires:    python-tornado
BuildRequires:    python-webob
BuildRequires:    intltool
#BuildRequires:    python-distutils-extra >= 1:2.29

Requires:         python-nova  = %{epoch}:%{version}-%{release}
Requires:         sudo

Requires(post):   chkconfig grep sudo libselinux-utils
Requires(postun): initscripts
Requires(preun):  chkconfig
Requires(pre):    shadow-utils qemu-kvm

Obsoletes:        %{short_name}-instancemonitor
Obsoletes:        %{short_name}-nova-cc-config
Obsoletes:        %{short_name}-compute-config

Conflicts:        %{short_name} =< 2011.3.2

%description
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

Nova is intended to be easy to extend, and adapt. For example, it currently
uses an LDAP server for users and groups, but also includes a fake LDAP server,
that stores data in Redis. It has extensive test coverage, and uses the Sphinx
toolkit (the same as Python itself) for code and user documentation.

%package          node-full
Summary:          OpenStack Nova full node installation
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:   %{name}-api = %{epoch}:%{version}-%{release}
Requires:   %{name}-compute = %{epoch}:%{version}-%{release}
Requires:   %{name}-network = %{epoch}:%{version}-%{release}
Requires:   %{name}-objectstore = %{epoch}:%{version}-%{release}
Requires:   %{name}-scheduler = %{epoch}:%{version}-%{release}
Requires:   %{name}-volume = %{epoch}:%{version}-%{release}
Requires:   openstack-client = %{epoch}:2012.1-%{release}
Requires:   openstack-glance = %{epoch}:2012.1.1-%{release}
#Requires:   openstack-client = %{epoch}:%{version}
#Requires:   openstack-glance = %{epoch}:%{version}
%if 0%{?with_doc}
Requires:   %{name}-doc = %{epoch}:%{version}-%{release}
%endif

%description      node-full
This package installs full set of OpenStack Nova packages and Cloud Controller
configuration.

%package          node-compute
Summary:          OpenStack Nova compute node installation
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:   %{name}-compute = %{epoch}:%{version}-%{release}
Requires:   %{name}-network = %{epoch}:%{version}-%{release}
Requires:         MySQL-python

%description      node-compute
This package installs compute set of OpenStack Nova packages and Compute node
configuration.

%package -n       python-nova
Summary:          Nova Python libraries
Group:            Applications/System

Requires:         vconfig
Requires:         PyXML
Requires:         curl
Requires:         m2crypto
Requires:         libvirt-python
Requires:         python-anyjson >= 0.2.4
Requires:         python-IPy >= 0.70
Requires:         python-boto >= 1.9b
Requires:         python-carrot >= 0.10.5
Requires:         python-daemon = 1.5.5
Requires:         python-eventlet >= 0.9.16
Requires:         python-gflags >= 1.3
Requires:         python-lockfile >= 0.8
Requires:         python-mox >= 0.5.0
Requires:         python-paste
Requires:         python-paste-deploy >= 1.5.0
Requires:         python-redis
Requires:         python-routes >= 1.12.3
Requires:         python-sqlalchemy >= 0.6
Requires:         python-suds >= 0.4.0
Requires:         python-tornado
Requires:         python-webob
Requires:         python-netaddr
Requires:         python-glance
Requires:         python-novaclient = %{epoch}:2012.1-%{release}
Requires:         python-lxml
Requires:         python-sqlalchemy-migrate
Requires:         radvd
Requires:         iptables iptables-ipv6
Requires:         iscsi-initiator-utils
Requires:         scsi-target-utils
Requires:         lvm2
Requires:         socat
Requires:         coreutils
Requires:         python-libguestfs >= 1.7.17
Requires:         python-kombu

#Arrived with essex
Requires:         python-iso8601
Requires:         python-pycrypto
Requires:         MySQL-python
Requires:         python-paramiko
Requires:         python-ldap
Requires:         python-memcached



%description -n   python-nova
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} Python library.

%package          api
Summary:          A nova API server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon

%description      api
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} API Server.

%package          compute
Summary:          A nova compute server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon
Requires:         libvirt-python
Requires:         libvirt >= 0.8.7
Requires:         libxml2-python
Requires:         rabbitmq-server
Requires:         python-cheetah
Requires:         dmidecode
Requires:         libguestfs-mount
Requires:         fuse

%description      compute
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} Compute Worker.

%package          network
Summary:          A nova network server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon

%description      network
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} Network Controller.

%package          xvpvncproxy
Summary:          A nova xvpvncproxy server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon

%description      xvpvncproxy
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} VNC proxy.

%package          objectstore
Summary:          A nova objectstore server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon

%description      objectstore
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} object store server.

%package          scheduler
Summary:          A nova scheduler server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon

%description      scheduler
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} Scheduler.

%package          volume
Summary:          A nova volume server
Group:            Applications/System

Requires:   %{name} = %{epoch}:%{version}-%{release}
Requires:         start-stop-daemon

%description      volume
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains the %{name} Volume service.

%if 0%{?with_doc}
%package doc
Summary:          Documentation for %{name}
Group:            Documentation

BuildRequires:    python-sphinx

%description      doc
Nova is a cloud computing fabric controller (the main part of an IaaS system)
built to match the popular AWS EC2 and S3 APIs. It is written in Python, using
the Tornado and Twisted frameworks, and relies on the standard AMQP messaging
protocol, and the Redis KVS.

This package contains documentation files for %{name}.
%endif

%prep
%setup -q -n nova-%{version}

%patch0001 -p1

install %{SOURCE1} README.rhel6

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
#mv %{buildroot}/usr/bin/nova{-api,}-metadata

%if 0%{?with_doc}
export PYTHONPATH="$( pwd ):$PYTHONPATH"
pushd doc
sphinx-build -b html source build/html
popd

# Fix hidden-file-or-dir warnings
rm -fr doc/build/html/.doctrees doc/build/html/.buildinfo
%endif

# Setup directories
#Essex
install -d -m 755 %{buildroot}%{_localstatedir}/run/nova
install -d -m 755 %{buildroot}%{_localstatedir}/lock/nova

install -d -m 755 %{buildroot}%{_sysconfdir}/nova
#AP: since we moved nova.conf to inside of ./etc/nova/ inside the repository,
#no need to move SOURCE23 explicitly anymore
#install -p -D -m 600 etc/nova/* %{SOURCE23} %{buildroot}%{_sysconfdir}/nova/
install -p -D -m 600 etc/nova/* %{buildroot}%{_sysconfdir}/nova/
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/images
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/instances
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/keys
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/networks
install -d -m 755 %{buildroot}%{_sharedstatedir}/nova/tmp
install -d -m 755 %{buildroot}%{_localstatedir}/log/nova
cp -rp nova/CA %{buildroot}%{_sharedstatedir}/nova
#AP: move the /etc/rc.d/init.d scirpts 
cp -rp etc/rc.d/init.d/* %{buildroot}%{_initrddir}/
rm -rf %{buildroot}%{_initrddir}/openstack-nova-ajax-console-proxy

#KDS use /usr/local/nova for installation
install -d -m 755 %{buildroot}%{usrlocaldir}/nova
install -d -m 755 %{buildroot}%{usrlocaldir}/nova/images
install -d -m 755 %{buildroot}%{usrlocaldir}/nova/instances
install -d -m 755 %{buildroot}%{usrlocaldir}/nova/keys
install -d -m 755 %{buildroot}%{usrlocaldir}/nova/networks
install -d -m 755 %{buildroot}%{usrlocaldir}/nova/tmp
#KDS copy ISI's Openstack code to /usrl/local/nova
cp -rp * %{buildroot}%{usrlocaldir}/nova/
cp -rp nova/CA %{buildroot}%{usrlocaldir}/nova
#KDS: remove /usr/local/nova//CA/ it should only be under /usr/local/nova/nova/CA/ 
#KDS remove /usr/local/nova/nova/nova, /usr/bin/nova-manage
rm -rf %{buildroot}%{usrlocaldir}/nova/CA/
rm -rf %{buildroot}%{usrlocaldir}/nova/nova/nova/
rm -rf %{_bindir}/nova-manage

# Install initscripts for Nova services
# KDS to avaoid confusino don't put files at this location. use only the ones in  next set
#install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{prj}-api
#install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{prj}-compute
#install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{prj}-network
#install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/%{prj}-objectstore
#install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/%{prj}-scheduler
#install -p -D -m 755 %{SOURCE16} %{buildroot}%{_initrddir}/%{prj}-volume
#install -p -D -m 755 %{SOURCE17} %{buildroot}%{_initrddir}/%{prj}-direct-api
install -p -D -m 755 %{SOURCE19} %{buildroot}%{_initrddir}/%{prj}-xvpvncproxy
#install -p -D -m 755 %{SOURCE29} %{buildroot}%{_initrddir}/%{prj}-cert

#KDS Also copy ISI's files to /etc/init.d
#install -p -D -m 755 %{SOURCE30} %{buildroot}%{_initrddir}/openstack-nova-ajax-console-proxy
#AP: the init files have been moved to /etc/rc.d/init.d directory in the repo, these are not required
##install -p -D -m 755 %{SOURCE31} %{buildroot}%{_initrddir}/openstack-nova-api
##install -p -D -m 755 %{SOURCE32} %{buildroot}%{_initrddir}/openstack-nova-compute
##install -p -D -m 755 %{SOURCE33} %{buildroot}%{_initrddir}/openstack-nova-db-setup
##install -p -D -m 755 %{SOURCE34} %{buildroot}%{_initrddir}/openstack-nova-direct-api
##install -p -D -m 755 %{SOURCE35} %{buildroot}%{_initrddir}/openstack-nova-network
##install -p -D -m 755 %{SOURCE36} %{buildroot}%{_initrddir}/openstack-nova-objectstore
##install -p -D -m 755 %{SOURCE37} %{buildroot}%{_initrddir}/openstack-nova-scheduler
#install -p -D -m 755 %{SOURCE38} %{buildroot}%{_initrddir}/openstack-nova-vncproxy
##install -p -D -m 755 %{SOURCE39} %{buildroot}%{_initrddir}/openstack-nova-volume
##install -p -D -m 755 %{SOURCE40} %{buildroot}%{_initrddir}/openstack-nova-cert
#KDS copy dhcp_release to /usr/bin
#install -p -D -m 755 %{SOURCE41} %{buildroot}%{_bindir}/dhcp_release
#cp -p %{SOURCE41} %{buildroot}%{_bindir}/

# Install sudoers
install -p -D -m 440 %{SOURCE20} %{buildroot}%{_sysconfdir}/sudoers.d/%{name}

# Install logrotate
install -p -D -m 644 %{SOURCE6} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}


# Install template files
install -p -D -m 644 nova/auth/novarc.template %{buildroot}%{_datarootdir}/nova/novarc.template
install -p -D -m 644 nova/cloudpipe/client.ovpn.template %{buildroot}%{_datarootdir}/nova/client.ovpn.template
install -p -D -m 644 nova/virt/libvirt.xml.template %{buildroot}%{_datarootdir}/nova/libvirt.xml.template

#KDS install nova.conf
#KDS change permissions from 600
#AP: using chmod
#install -p -D -m 644 %{SOURCE23} %{buildroot}%{_sysconfdir}/nova/nova.conf
chmod 644  %{buildroot}%{_sysconfdir}/nova/nova.conf

# Network configuration templates for injection engine
install -d -m 755 %{buildroot}%{_datarootdir}/nova/interfaces
#install -p -D -m 644 nova/virt/interfaces.template %{buildroot}%{_datarootdir}/nova/interfaces/interfaces.ubuntu.template
install -p -D -m 644 %{SOURCE22} %{buildroot}%{_datarootdir}/nova/interfaces.template

# Clean CA directory
find %{buildroot}%{_sharedstatedir}/nova/CA -name .gitignore -delete
find %{buildroot}%{_sharedstatedir}/nova/CA -name .placeholder -delete

install -d -m 755 %{buildroot}%{_sysconfdir}/polkit-1/localauthority/50-local.d
install -p -D -m 644 %{SOURCE21} %{buildroot}%{_sysconfdir}/polkit-1/localauthority/50-local.d/50-%{short_name}.pkla

# Remove unneeded in production stuff
rm -fr %{buildroot}%{python_sitelib}/run_tests.*
rm -f %{buildroot}%{_bindir}/nova-combined
rm -f %{buildroot}/usr/share/doc/nova/README*

mv %{buildroot}/usr/bin/nova{-api,}-metadata

#KDS remove that stuff from /usr/bin that we put in /usr/local/nova/bin
rm -f %{buildroot}%{_bindir}/api-paste.ini
rm -f %{buildroot}%{_bindir}/clear_rabbit_queues
rm -f %{buildroot}%{_bindir}/instance-usage-audit
rm -f %{buildroot}%{_bindir}/nova-a*
rm -f %{buildroot}%{_bindir}/nova-c*
rm -f %{buildroot}%{_bindir}/nova-dhcpbridge
rm -f %{buildroot}%{_bindir}/nova-direct-api
rm -f %{buildroot}%{_bindir}/nova-l*
rm -f %{buildroot}%{_bindir}/nova-m*
rm -f %{buildroot}%{_bindir}/nova-n*
rm -f %{buildroot}%{_bindir}/nova-o*
rm -f %{buildroot}%{_bindir}/nova-r*
rm -f %{buildroot}%{_bindir}/nova-s*
rm -f %{buildroot}%{_bindir}/nova-v*
rm -f %{buildroot}%{_bindir}/nova-x*
rm -f %{buildroot}%{_bindir}/stack

%clean
rm -rf %{buildroot}

%pre
getent group nova >/dev/null || groupadd -r nova
getent passwd nova >/dev/null || \
useradd -r -g nova -G nova,nobody,qemu -d %{_sharedstatedir}/nova -s /sbin/nologin \
-c "OpenStack Nova Daemons" nova
exit 0

%post -p /bin/bash

if ! fgrep '#includedir /etc/sudoers.d' /etc/sudoers 2>&1 >/dev/null; then
        echo '#includedir /etc/sudoers.d' >> /etc/sudoers
fi
if %{_sbindir}/selinuxenabled; then
	echo -e "\033[47m\033[1;31m***************************************************\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m                                                \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m >> \033[5mYou have SELinux enabled on your host !\033[25m <<  \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m                                                \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31mPlease disable it by setting \`SELINUX=disabled' \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31min /etc/sysconfig/selinux and don't forget      \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31mto reboot your host to apply that change!       \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m*\033[0m \033[40m\033[1;31m                                                \033[47m\033[1;31m*\033[0m"
	echo -e "\033[47m\033[1;31m***************************************************\033[0m"
fi

# api
#KDS: there are no nova-* service now. they have been replaced by openstack-nova-*
# so replacing %{prj} below with %{isi_prj}
#%preun api
#if [ $1 -eq 0 ] ; then
#    /sbin/service %{prj}-api stop >/dev/null 2>&1
#    /sbin/service %{prj}-direct-api stop >/dev/null 2>&1
#fi

#%postun api
#if [ $1 -eq 1 ] ; then
#    /sbin/service %{prj}-api condrestart
#    /sbin/service %{prj}-direct-api condrestart
#fi
##mv /usr/bin/nova{-api,}-metadata

# compute

#%preun compute
#if [ $1 -eq 0 ] ; then
#    /sbin/service %{prj}-ajax-console-proxy stop >/dev/null 2>&1
#    /sbin/service %{prj}-compute stop >/dev/null 2>&1
#fi

#%postun compute
#if [ $1 -eq 1 ] ; then
#    /sbin/service %{prj}-ajax-console-proxy condrestart
#    /sbin/service %{prj}-compute condrestart
#fi

# network

%preun network
if [ $1 -eq 0 ] ; then
    /sbin/service %{isi_prj}-network stop >/dev/null 2>&1
fi

%postun network
if [ $1 -eq 1 ] ; then
    /sbin/service %{isi_prj}-network condrestart
fi

# xvpvncproxy

#%preun xvpvncproxy
#if [ $1 -eq 0 ] ; then
#    /sbin/service %{prj}-xvpvncproxy stop >/dev/null 2>&1
#fi

#%postun xvpvncproxy
#if [ $1 -eq 1 ] ; then
#    /sbin/service %{prj}-xvpvncproxy condrestart
#fi

# objectstore

%preun objectstore
if [ $1 -eq 0 ] ; then
    /sbin/service %{isi_prj}-objectstore stop >/dev/null 2>&1
fi

%postun objectstore
if [ $1 -eq 1 ] ; then
    /sbin/service %{isi_prj}-objectstore condrestart
fi

# scheduler

%preun scheduler
if [ $1 -eq 0 ] ; then
    /sbin/service %{isi_prj}-scheduler stop >/dev/null 2>&1
fi

%postun scheduler
if [ $1 -eq 1 ] ; then
    /sbin/service %{isi_prj}-scheduler condrestart
fi

# volume
#KDS
#%preun volume
#if [ $1 -eq 0 ] ; then
#    /sbin/service %{prj}-volume stop >/dev/null 2>&1
#fi

#%postun volume
#if [ $1 -eq 1 ] ; then
#    /sbin/service %{prj}-volume condrestart
#fi

%files
%defattr(-,root,root,-)
%doc README.rst README.rhel6
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%config(noreplace) %{_sysconfdir}/sudoers.d/%{name}

%defattr(-,nova,nobody,-)
%dir %{_sysconfdir}/nova
%config(noreplace) %{_sysconfdir}/nova/nova.conf
%config(noreplace) %{_sysconfdir}/nova/nova.conf.sample
%config(noreplace) %{_sysconfdir}/nova/logging_sample.conf
%config(noreplace) %{_sysconfdir}/nova/policy.json
%dir %{_localstatedir}/log/nova
%dir %{_localstatedir}/run/nova
%dir %{_localstatedir}/lock/nova

%defattr(-,root,root,-)
#%{_bindir}/instance-usage-audit
#%{_bindir}/nova-console
#%{_bindir}/nova-consoleauth
#%{_bindir}/nova-manage
#%{_bindir}/clear_rabbit_queues
#%{_bindir}/stack
#%{_bindir}/nova-rootwrap
#%{_bindir}/nova-all
%{_bindir}/nova-debug

%{_datarootdir}/nova
#KDS
#%defattr(-,nova,nobody,-)
%defattr(-,nova,nova,-)
%dir %{_sharedstatedir}/nova
%{_sharedstatedir}/nova/CA
%{_sharedstatedir}/nova/images
%{_sharedstatedir}/nova/instances
%{_sharedstatedir}/nova/keys
%{_sharedstatedir}/nova/networks
%{_sharedstatedir}/nova/tmp

#KDS
%dir %{usrlocaldir}/nova
%{usrlocaldir}/nova/*
#KDS new files installed. these need to be packaged:
%{_initrddir}/openstack-nova-db-setup
#/usr/bin/dhcp_release

%files xvpvncproxy
%defattr(-,root,root,-)
#%{_bindir}/nova-xvpvncproxy
%{_initrddir}/%{prj}-xvpvncproxy
#%doc %{_sharedstatedir}/nova/noVNC/LICENSE.txt
#%doc %{_sharedstatedir}/nova/noVNC/README.md

%files -n python-nova
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/nova
#KDS becuase of glob can't find this file
#%{python_sitelib}/nova-%{version}-*.egg-info
%{python_sitelib}/nova-*.egg-info

%files api
%defattr(-,root,root,-)
#KDS no longer copied
#%{_bindir}/%{prj}-api
%{_initrddir}/%{isi_prj}-api
#%{_bindir}/%{prj}-api-ec2
#%{_bindir}/%{prj}-direct-api
%{_initrddir}/%{isi_prj}-direct-api
#%{_bindir}/%{prj}-cert
#%{_bindir}/%{prj}-metadata
#%{_bindir}/%{prj}-api-os-compute
#%{_bindir}/%{prj}-api-os-volume
#%{_bindir}/%{prj}-api-metadata
#%{_bindir}/%{isi_prj}-ajax-console-proxy
#%{_bindir}/%{prj}-ajax-console-proxy
#KDS no longer copied
#%{_initrddir}/%{prj}-api
#%{_initrddir}/%{prj}-direct-api

#KDS
#%defattr(-,nova,nobody,-)
%defattr(-,nova,nova,-)
%config(noreplace) %{_sysconfdir}/nova/api-paste.ini
#mv /usr/bin/nova{-api,}-metadata

%files compute
%defattr(-,root,root,-)
%config %{_sysconfdir}/polkit-1/localauthority/50-local.d/50-openstack-nova.pkla
#%{_bindir}/nova-compute
#KDS
#%{_initrddir}/%{prj}-compute
%{_initrddir}/%{isi_prj}-compute
%{_initrddir}/%{isi_prj}-cert

%files network
%defattr(-,root,root,-)
#%{_bindir}/nova-network
#%{_bindir}/nova-dhcpbridge
#KDS
#%{_initrddir}/%{prj}-network
%{_initrddir}/%{isi_prj}-network

%files objectstore
%defattr(-,root,root,-)
#%{_bindir}/nova-objectstore
#KDS
#%{_initrddir}/%{prj}-objectstore
%{_initrddir}/%{isi_prj}-objectstore

%files scheduler
%defattr(-,root,root,-)
#%{_bindir}/nova-scheduler
#KDS
#%{_initrddir}/%{prj}-scheduler
%{_initrddir}/%{isi_prj}-scheduler

%files volume
%defattr(-,root,root,-)
#%{_bindir}/nova-volume
#KDS
#%{_initrddir}/%{prj}-volume
%{_initrddir}/%{isi_prj}-volume

%if 0%{?with_doc}
%files doc
%defattr(-,root,root,-)
%doc LICENSE doc/build/html
%endif

%files node-full

%files node-compute

%changelog
* Wed Jun 13 2012 Karandeep Singh <karan AT isi DOT edu>
- Updated for ISI's heterogeneous Openstack Essex release

* Fri Dec 20 2011 Boris Filippov <bfilippov@griddynamics.com> - 2011.3
- Obsolete nova-cc-config
- Add nova.conf to compute package 

* Fri Dec 16 2011 Boris Filippov <bfilippov@griddynamics.com> - 2011.3
- Make init scripts LSB conformant
- Rename init scripts
- Disable services autorun
- Disable db sync during install

* Tue Aug 29 2011 Alessio Ababilov <aababilov@griddynamics.com> - 2011.3
- Drop openstack-noVNC dependency

* Fri Aug 26 2011 Alessio Ababilov <aababilov@griddynamics.com> - 2011.3-0.20110826.1448
- Fixed openstack-nova-scsi-target-utils-support.patch

* Mon Aug 22 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.20110822.1819
- Added nova-api-{ec2,os}

* Thu Aug 18 2011 Alessio Ababilov <aababilov@griddynamics.com> - 2011.4-0.20110818.1721
- Return type of server's IP patch

* Thu Aug 11 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.4-0.20110810.1412
- Removed /usr/bin/nova-import-canonical-imagestore
  https://bugs.launchpad.net/nova/+bug/820062

* Fri Aug 05 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.20110804.1364
- Removed openstack-nova-instancemonitor

* Mon Jul 25 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.20110724.1308
- Added MySQL-python as dep for openstack-nova-node-compute
- Added nova-network for compute-only nodes due recent changes in network HA code
  https://code.launchpad.net/~vishvananda/nova/ha-net/+merge/67078
- Fixed db upgrade in postscript, changed postscript to /bin/bash
- Removed duplicate entry for /usr/bin/instance-usage-audit

* Tue Jul 12 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.20110711.1265
- Removed lots of meaningless changelog entries from Jenkins
- Added dependency on dmidecode to openstack-nova-compute because it's missing
  in libvirt package
- Changed versioning for better upgrade experience

* Tue May 03 2011 Mr. Jenkins GD <openstack@griddynamics.net> - 2011.3-0.36.bzr1052
- Added support for scsi-target-utils

* Wed Apr 27 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.23.bzr1032
- created separate package for noVNC due licensing issue

* Tue Apr 26 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.21.bzr1031
- Updated patch6

* Mon Apr 25 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.19.bzr1030
- Floating IPs merged to trunk

* Tue Apr 19 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.11.bzr1000
- Updated dependency on python-routes with version 1.12.3

* Tue Apr 19 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.10.bzr1000
- Updated floating IP patch, kudos to Ilya Alekseyev

* Fri Apr 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.3-0.1.bzr990
- Diablo versioning

* Thu Apr 14 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.111.bzr988
- Uncommented initial db sync on fresh install
- Added banner with link to instructions

* Thu Apr 14 2011 Ilya Alekseyev <ialekseev@griddynamics.com> - 2011.2-0.110.bzr988
- Patch for auto assigning floating ips (AWS EC2 behaviour emulation) added

* Thu Apr 14 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.108.bzr987
- Fixed an odd typo

* Tue Apr 12 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.101.bzr980
- Added initscript for vncproxy

* Mon Apr 11 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.97.bzr975
- Removed openssl.cnf patch (included in upstream)

* Mon Apr 11 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.94.bzr973
- Removed temp patch

* Mon Apr 11 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.93.bzr973
- Added dependency libvirt >= 0.8.2 for openstack-nova-compute package, see
  https://bugs.launchpad.net/nova/+bug/757283

* Mon Apr 11 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.91.bzr972
- Added temp patch for bug LP755666

* Sun Apr 10 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.89.bzr971
- Added quick fix for s3server.py which restoring euca-upload-bundle

* Fri Apr 08 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.84.bzr967
- Fixed initscript for objectstore

* Fri Apr 08 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.82.bzr965
- Added noVNC tarball

* Wed Apr 06 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.65.bzr946
- Update to bzr946
- Migrated openssl.cnf patch
- Relocated CA directory
- Disabled manual api-paste.ini installation
- Moved ajaxterm to /usr/share/nova

* Wed Apr 06 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.65.bzr942
- Updated network injection patch wich bugfix

* Tue Apr 05 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.64.bzr942
- Updated network injection patch (Ilya Alekseyev)

* Mon Apr 04 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.55.bzr932
- Removed patch for euca-get-ajax-console due it's inclution in upstream

* Fri Apr 01 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.52.bzr930
- Changed location of ajaxterm.py
- Patched netcat binary name s/netcat/nc/

* Fri Apr 01 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.51.bzr930
- Added dependency on our version of euca2ools

* Thu Mar 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.47.bzr926
- s/config-cc/cc-config/

* Thu Mar 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.46.bzr926
- Added empty files sections for meta packages to enable RPM generation

* Thu Mar 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.45.bzr926
- Added SELinux banner

* Thu Mar 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.43.bzr925
- Added openstack-nova-node-full, openstack-nova-node-compute meta packages

* Wed Mar 30 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.33.bzr913
- Added nova-vncproxy

* Wed Mar 30 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.28.bzr908
- Migrated guestfs patch

* Tue Mar 29 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.23.bzr905
- Enabled doc build 

* Fri Mar 25 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.20.bzr890
- Migrated guestfs patch

* Fri Mar 25 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.17.bzr886
- Added dependency on python-suds

* Fri Mar 25 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.15.bzr885
- Added dependency on python-novaclient

* Thu Mar 17 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.9.bzr815
- Update to bzr815
- Removed libvirt-xml-cpus.patch

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.8.bzr807
- Update to bzr807

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.7.bzr806
- Update to bzr806

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.6.bzr805
- Added database migration
- Temporary disabled documentation build until release

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.5.bzr805
- Update to bzr805

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.4.bzr802
- Added openstack-nova-libvirt-xml-cpus.patch to prevent error with nova-compute startup

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.3.bzr802
- sudo configuration updated

* Tue Mar 15 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.2-0.2.bzr802
- Update to bzr802

* Mon Mar 14 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.2-0.1.bzr795
- Cactus pre-release build
- Changed release to better comply packaging policy
  https://fedoraproject.org/wiki/Packaging:NamingGuidelines
- /etc/nova/nova-api.conf -> /etc/nova/api-paste.ini
- guestfs patch migrated
- rhel config paths patch - added handling of api-paste.ini

* Wed Mar 02 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1.1-5
- Changed logrotate script - it should not rotate empty logs

* Wed Mar 02 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1.1-4
- Updated logrotate script with nova-ajax-console-proxy and nova-direct-api
  logfiles

* Wed Mar 02 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1.1-3
- Added initscript for nova-ajax-console-proxy

* Wed Mar 02 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1.1-2
- Added initscript for nova-direct-api

* Wed Mar 02 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1.1-1
- Bugfix release 2011.1.1
- Added python-distutils-extra to BuildReqs

* Fri Feb 25 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-5
- Merged updated guestfs patch from Ilya Alekseyev
- Refactored guestfs patch - now it creates directory only if it does not exist

* Fri Feb 18 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-4
- Added patch with network interface template for RHEL guest OS
  (kudos to Ilya Alekseyev)

* Fri Feb 18 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-3
- Disabled SELinux for KVM images in libvirt.xml.template
- Added patch for image injection (kudos to Ilya Alekseyev).
- Updated dependencies

* Mon Feb 07 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-1
- Bexar release

* Wed Feb 02 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr642
- Deleted patch from bzr638 rev because it was merged to trunk
- Updated dependencies
- Updated sudo configuration for nova user

* Mon Jan 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr640
- Updated to bzr640

* Mon Jan 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr639
- Added condrestart target to initscripts
- Added condrestart on package upgrade

* Mon Jan 31 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr638
- Added patch openstack-nova-logging.py - re-routing unhandled exceptions to logs

* Thu Jan 27 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr629
- Update to bzr629
- Refactored initscripts with start-stop-daemon since standard RHEL initscripts
  does not support creation of pidfiles
- Removed dependency on upstart
- All daemons are once again running under user nova instead of root

* Wed Jan 26 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr621
- Updated to bzr621

* Mon Jan 24 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr604
- Update to bzr604
- Added dependency on python-sqlalchemy-migrate

* Fri Jan 21 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr598
- Updated to bzr598
- Updated patch for rhel paths

* Fri Jan 21 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> 2011.1-bzr597
- Added dependency for python-glance

* Tue Jan 18 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr572
- Added /etc/nova/nova-api.conf
- Reworked openstack-nova-rhel-paths.patch
- Added dependencies for openstack-nova-api for paste & paste-deploy modules

* Mon Jan 17 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr569
- Temporary commented logrotate script

* Fri Jan 14 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr565
- Added build and runtime dep on python-netaddr

* Wed Jan 12 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr553
- Added dep on python-cheetah from standard RHEL distro
- Temporary disabled build of -doc package to speed up testing env

* Wed Jan 12 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr552
- Fixed bug with upstart configs

* Wed Jan 12 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr551
- Moved initscripts to upstart

* Sat Jan 01 2011 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr509
- Updated config patch
- Removed templates

* Tue Dec 14 2010 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr464
- Changed dependency for python-daemon to = 1.5.5

* Tue Dec 14 2010 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr460
- Added vconfig as a dep for python-nova

* Thu Dec 09 2010 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr454
- Added postscript to openstac-nova package to add inclution of files to
  /etc/sudoers

* Thu Dec 09 2010 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr453
- Added dependency >= 10.1.0 for twisted-core and twisted-web - 8.2.0 from RHEL6
  is not ok for use with nova-objectstore

* Wed Dec 01 2010 Andrey Brindeyev <abrindeyev@griddynamics.com> - 2011.1-bzr435
- Moved config files to separate package openstack-nova-cc-config for easy
  package-based deployment

* Thu Nov 04 2010 Silas Sewell <silas@sewell.ch> - 2010.1-2
- Fix various issues (init, permissions, config, etc..)

* Thu Oct 21 2010 Silas Sewell <silas@sewell.ch> - 2010.1-1
- Initial build
