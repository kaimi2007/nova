Name:		dodcs-openstack
Epoch:          1
Version:	2013.1
Release:	grizzly
Summary:	Installs all the DODCS OpenStack software using packages. Also writes README.1st and release notes to /usr/local/nova 

Group:		Distribution
License:	GPL
Source0:	%{name}-%{version}.tar.gz
BuildRoot:	%{_tmppath}/%{name}-buildroot
BuildArch:      noarch

Requires:	nova-install
Requires:	mysql mysql-server MySQL-python

#Requires:       qemu-img = 2:0.12.1.2-2.295.el6
#Requires:	qemu-kvm = 2:0.12.1.2-2.295.el6
#Requires:	qemu-kvm-tools = 2:0.12.1.2-2.295.el6
#Requires:       libvirt = 0.9.10-21.el6
#Requires:       libvirt-client = 0.9.10-21.el6
#Requires:       libvirt-devel = 0.9.10-21.el6
#Requires:       libvirt-python = 0.9.10-21.el6

Requires:       qemu-img
Requires:       qemu-kvm
Requires:       qemu-kvm-tools
Requires:	libvirt
Requires:	libvirt-client
Requires:	libvirt-devel
Requires:	libvirt-python
Requires:	lxc-isi

#Requires:	openstack-nova-node-full = 2013.1-grizzly
Requires:	euca2ools = 2.1.3-1.el6
Requires:	openstack-keystone = 2013.1-1.el6
Requires:	python-keystoneclient = 1:0.2.3-2.el6
Requires:       python-nova = 2013.1-grizzly
Requires:	openstack-nova-network = 2013.1-grizzly
Requires:	openstack-nova-scheduler = 2013.1-grizzly
Requires:	openstack-nova-objectstore = 2013.1-grizzly
Requires:	openstack-nova-api = 2013.1-grizzly
#Requires:	openstack-nova-conductor = 2013.1-grizzly
Requires:	openstack-nova-conductor = 2013.1-2.el6 

Requires:       python-glance = 2013.1-1.el6
Requires:	openstack-glance = 2013.1-1.el6
Requires:	openstack-dashboard = 2013.1-1.el6
Requires:	openstack-nova-cert = 2013.1-grizzly
Requires:	openstack-nova-cinder = 2013.1-1.el6
Requires:	openstack-nova-compute = 2013.1-grizzly
# Transaction check error
#Requires:	openstack-nova-common = 2013.1-2.el6
#Requires:	openstack-nova-xvpvncproxy = 2013.1-grizzly
#Requires:	openstack-nova-xvpvncproxy

%description
Installs all the DODCS OpenStack software using packages. 
Writes README.1st to /usr/local/nova
Writes Release-Notes to /usr/local/nova

%prep
%setup -q

%build

%install
install -m 0755 -d $RPM_BUILD_ROOT/usr/local/nova
install -m 0755 dodcs-openstack-readme/README.1st $RPM_BUILD_ROOT/usr/local/nova/README.1st
install -m 0755 dodcs-openstack-readme/Release-Notes $RPM_BUILD_ROOT/usr/local/nova/Release-Notes

%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
/usr/local/nova/README.1st
/usr/local/nova/Release-Notes

%changelog
* Mon Apr 29 2013 Malek Musleh <mmusleh AT isi.edu>
- Updated for grizzly release
* Mon Sep 17 2012 Mikyung Kang <mkkang AT isi.edu>
- Updated for folsom release
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
