Name:		nova-install
Version:	2013.1

Release: 	grizzly
Summary:	Copies nova install script and examples config files for grizzly release to /usr/local/nova/

Group:		Distribution
License:	GPL
Source0:	%{name}-grizzly.tar.gz

Source1:	%{name}-hpc-%{Release}.sh
#MK: needs to be checked
#Source2:	dhcp_release
BuildRoot:	%{_tmppath}/%{name}-buildroot
#BuildArch:      noarch

%define usrlocaldir /usr/local

%description
Copies nova install script for grizzly release in /usr/local/nova/ and example config files under /usr/local/nova/examples/
Also copies dhcp_release to /usr/bin

%prep
%setup -q -n %{name}-%{version}

%build

%install
install -m 0755 -d $RPM_BUILD_ROOT%{usrlocaldir}/nova
install -m 0755 -d $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples
install -m 0755 -d $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/glance
install -m 0755 -d $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/keystone
install -m 0755 -d $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/nova

install -p -D -m 755 %{SOURCE1} $RPM_BUILD_ROOT%{usrlocaldir}/nova/

cp -rp examples/* $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/
cp -rp examples/glance/* $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/glance/
cp -rp examples/keystone/* $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/keystone/
cp -rp examples/nova/* $RPM_BUILD_ROOT%{usrlocaldir}/nova/examples/nova/
#MK: needs to be checked
#cp -p %{SOURCE2} $RPM_BUILD_ROOT%{_bindir}/dhcp_release
#install -p -D -m 755 %{SOURCE2} %{buildroot}%{_bindir}/dhcp_release
%clean

rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
#MK: needs to be checked
%{usrlocaldir}/nova/nova-install-hpc-grizzly.sh
%dir %{usrlocaldir}/nova/examples
%dir %{usrlocaldir}/nova/examples/glance
%dir %{usrlocaldir}/nova/examples/keystone
%dir %{usrlocaldir}/nova/examples/nova
%{usrlocaldir}/nova/examples/*
%{usrlocaldir}/nova/examples/glance/*
%{usrlocaldir}/nova/examples/keystone/*
%{usrlocaldir}/nova/examples/nova/*
#MK: needs to be checked
#%{_bindir}/dhcp_release

%changelog
* Mon Apr 29 2013 Malek Musleh <mmusleh AT isi.edu>
- updated for grizzly release
* Mon Sep 17 2012 Mikyung Kang <mkkang AT isi.edu>
- updated for folsom release
* Mon Jul 2 2012 Karandeep Singh <karan AT isi.edu>
- deleted /usr/bin/nova-manage symlink from install script
* Fri Jun 29 2012 Karandeep Singh <karan AT isi.edu>
- Updated for essex release
- copies dhcp_release to /usr/bin
* Wed May 2 2012 Karandeep Singh <karan AT isi.edu>
- Updated for alchemist limited release; 'Release' changed
- Updated nova.conf example file and install script
* Wed Apr 13 2012 Karandeep Singh <karan AT isi DOT edu>
- Also provides some example files
- Updated for gold release
* Wed Apr 4 2012 Karandeep Singh <karan AT isi DOT edu>
- Recreated for updated script with new Release #
* Fri Mar 09 2012 Karandeep Singh <karan AT isi DOT edu>
- Created the simple rpm
