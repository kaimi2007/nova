Name: kernel
Summary: The Linux Kernel
Version: 2.6.38.2lxc0.7.4
Release: 1
License: GPL
Group: System Environment/Kernel
Vendor: The Linux Community
URL: http://www.kernel.org
Source: kernel-2.6.38.2lxc0.7.4.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{PACKAGE_VERSION}-root
Provides:  kernel-2.6.38.2-lxc-0.7.4
%define __spec_install_post /usr/lib/rpm/brp-compress || :
%define debug_package %{nil}

%description
The Linux Kernel, the operating system core itself

%prep
%setup -q

%build
make clean && make %{?_smp_mflags}

%install
%ifarch ia64
mkdir -p $RPM_BUILD_ROOT/boot/efi $RPM_BUILD_ROOT/lib/modules
mkdir -p $RPM_BUILD_ROOT/lib/firmware
%else
mkdir -p $RPM_BUILD_ROOT/boot $RPM_BUILD_ROOT/lib/modules
mkdir -p $RPM_BUILD_ROOT/lib/firmware
%endif
INSTALL_MOD_PATH=$RPM_BUILD_ROOT make %{?_smp_mflags} KBUILD_SRC= modules_install
%ifarch ia64
cp $KBUILD_IMAGE $RPM_BUILD_ROOT/boot/efi/vmlinuz-2.6.38.2-lxc-0.7.4
ln -s efi/vmlinuz-2.6.38.2-lxc-0.7.4 $RPM_BUILD_ROOT/boot/
%else
%ifarch ppc64
cp vmlinux arch/powerpc/boot
cp arch/powerpc/boot/$KBUILD_IMAGE $RPM_BUILD_ROOT/boot/vmlinuz-2.6.38.2-lxc-0.7.4
%else
cp $KBUILD_IMAGE $RPM_BUILD_ROOT/boot/vmlinuz-2.6.38.2-lxc-0.7.4
%endif
%endif
cp System.map $RPM_BUILD_ROOT/boot/System.map-2.6.38.2-lxc-0.7.4
cp .config $RPM_BUILD_ROOT/boot/config-2.6.38.2-lxc-0.7.4
%ifnarch ppc64
cp vmlinux vmlinux.orig
bzip2 -9 vmlinux
#mv vmlinux.bz2 $RPM_BUILD_ROOT/boot/vmlinux-2.6.38.2-lxc-0.7.4.bz2
mv vmlinux.orig vmlinux
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr (-, root, root)
%dir /lib/modules
/lib/modules/2.6.38.2-lxc-0.7.4
/lib/firmware
/boot/*

%post
dracut -H "/boot/initramfs-2.6.38.2-lxc-0.7.4.img" 2.6.38.2-lxc-0.7.4
grubby --add-kernel=/boot/vmlinuz-2.6.38.2-lxc-0.7.4 --initrd=/boot/initramfs-2.6.38.2-lxc-0.7.4.img --title="Kernel 2.6.38.2-lxc-0.7.4" --copy-default --make-default

%postun
rm -rf /boot/initramfs-2.6.38.2-lxc-0.7.4.img
grubby --remove-kernel=/boot/vmlinuz-2.6.38.2-lxc-0.7.4
