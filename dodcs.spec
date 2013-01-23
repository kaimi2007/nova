Name:		dodcs-openstack
Epoch:          1
Version:	2012.1.1
#MK
#Release:	essex
Release: 	folsom	
Summary:	Installs all the DODCS OpenStack software using packages. Also writes README.1st and release notes to /usr/local/nova 

Group:		Distribution
License:	GPL
Source0:	%{name}-%{version}.tar.gz
BuildRoot:	%{_tmppath}/%{name}-buildroot
BuildArch:      noarch

Requires:	nova-install
Requires:	mysql mysql-server MySQL-python
Requires:   	bridge-utils
Requires:       nodejs nodejs-binary
#Requires:       Django >= 1.3 django-nose
#Requires:       horizon = %{epoch}:%{version}-%{release} httpd mod_wsgi memcached python-memcached
#Requires:       qemu-img = 2:0.14.0-0.1.el6.isi
#Requires:	qemu-kvm = 2:0.14.0-0.1.el6.isi
#Requires:	qemu-kvm-debuginfo = 2:0.14.0-0.1.el6.isi
#Requires:	qemu-kvm-tools = 2:0.14.0-0.1.el6.isi
Requires:       qemu-img
Requires:	qemu-kvm
Requires:	qemu-kvm-debuginfo
Requires:	qemu-kvm-tools
#Requires:	libvirt = 0.9.4-23.el6.6_isi
#Requires:	libvirt-client = 0.9.4-23.el6.6_isi
#Requires:	libvirt-debuginfo = 0.9.4-23.el6.6_isi
#Requires:	libvirt-devel = 0.9.4-23.el6.6_isi
#Requires:	libvirt-python = 0.9.4-23.el6.6_isi
Requires:	libvirt >= 0.9.6
Requires:	libvirt-client >= 0.9.6
Requires:	libvirt-daemon >= 0.9.6
Requires:	libvirt-daemon-config-network >= 0.9.6
Requires:	libvirt-daemon-config-nwfilter >= 0.9.6
Requires:	libvirt-daemon-driver-interface >= 0.9.6
Requires:	libvirt-daemon-driver-lxc >= 0.9.6
Requires:	libvirt-daemon-driver-network >= 0.9.6
Requires:	libvirt-daemon-driver-nodedev >= 0.9.6
Requires:	libvirt-daemon-driver-nwfilter >= 0.9.6
Requires:	libvirt-daemon-driver-qemu >= 0.9.6
Requires:	libvirt-daemon-driver-secret >= 0.9.6
Requires:	libvirt-daemon-driver-storage >= 0.9.6
Requires:	libvirt-daemon-kvm >= 0.9.6
Requires:	libvirt-daemon-lxc >= 0.9.6
Requires:	libvirt-devel >= 0.9.6
Requires:	libvirt-docs >= 0.9.6
Requires:	libvirt-lock-sanlock >= 0.9.6
Requires:	libvirt-python >= 0.9.6
Requires:	lxc-isi
Requires:	python-paste-deploy = 1.5.0-4.el6
Requires:	openstack-nova-node-full = 1:2012.6-folsom
Requires:	euca2ools = 1:1.3.1-gd5
Requires:       openstack-keystone = 1:2012.1.1-folsom
#Requires:       python-keystoneclient = 1:2.7-b3045
Requires:       python-keystoneclient = 1:2012.1-folsom 
Requires:       python-nova = 1:2012.6-folsom
Requires:	openstack-nova-network = 1:2012.6-folsom
Requires:	openstack-nova-scheduler = 1:2012.6-folsom
Requires:	openstack-nova-objectstore = 1:2012.6-folsom
Requires:	openstack-nova-api = 1:2012.6-folsom
Requires:	openstack-nova-volume = 1:2012.6-folsom
Requires:       python-glance = 1:2012.1.1-folsom
Requires:	openstack-glance = 1:2012.1.1-folsom
Requires:	openstack-nova-compute = 1:2012.6-folsom
Requires:	openstack-dashboard = 1:2012.1.1-folsom	
Requires:	horizon = 1:2012.1.1-folsom


%description
Installs all the DODCS OpenStack software using packages. 
Writes README.1st to /usr/local/nova
Writes Release-Notes to /usr/local/nova

%prep
%setup -q

%build

%install
install -m 0755 -d $RPM_BUILD_ROOT/usr/local/nova
install -m 0755 README.1st $RPM_BUILD_ROOT/usr/local/nova/README.1st
install -m 0755 Release-Notes $RPM_BUILD_ROOT/usr/local/nova/Release-Notes

%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
/usr/local/nova/README.1st
/usr/local/nova/Release-Notes

%changelog
* Mon Jun 25 2012 Karandeep Singh <karan AT isi.edu>
- Changed version of glance and keystone to 2012.1.1 from 2012.1
- Used bug-fixed essex code from lp for nova, glance,keystone and horizon
* Fri Jun 15 2012 Karandeep Singh <karan AT isi.edu>
- Updated for essex release
* Wed May 2 2012 Karandeep Singh <karan AT isi.edu>
- Updated for alchemist limited release
- 'Release' changed along with dependencies specification
* Wed Apr 12 2012 Karandeep Singh <karan AT isi DOT edu>
- Updated for gold release
* Wed Apr 4 2012 Karandeep Singh <karan AT isi DOT edu>
- Copies Release-Notes also
- Updated for alchemist silver release
* Fri Mar 23 2012 Karandeep Singh <karan AT isi DOT edu>
- Updated to write glance conf files also -disabled for now
* Fri Mar 15 2012 Karandeep Singh <karan AT isi DOT edu>
- Created the rpm
