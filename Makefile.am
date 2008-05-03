#
# This file is part of jack_mixer
#
# Copyright (C) 2007 Nedko Arnaudov <nedko@arnaudov.name>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.
#

AM_CFLAGS = @JACK_CFLAGS@ -D_GNU_SOURCE -Wall -fno-strict-aliasing
if DEV_VERSION
AM_CFLAGS +=  -Werror
endif

INCLUDES = $(PYTHON_INCLUDES)

jack_mixerdir = $(pkgdatadir)
pkgpyexecdir = $(pythondir)
pkgpyexec_LTLIBRARIES = _jack_mixer_c.la

_jack_mixer_c_la_LDFLAGS = -module -avoid-version

_jack_mixer_c_la_LIBADD = @JACK_LIBS@

dist_jack_mixer_DATA = abspeak.py channel.py gui.py meter.py scale.py serialization.py serialization_xml.py slider.py jack_mixer.glade

jack_mixer_c.py jack_mixer_wrap.c: $(top_srcdir)/jack_mixer.h
	swig -o jack_mixer_wrap.c -I$(top_srcdir) -python $(top_srcdir)/jack_mixer.h

pkgpyexec_SCRIPTS = jack_mixer_c.py

CLEANFILES = jack_mixer_c.py jack_mixer_wrap.c *.pyc
EXTRA_DIST = test.py gpl.txt jack_mixer.schemas jack_mixer.py jack_mixer_c.py CHANGES

_jack_mixer_c_la_SOURCES = jack_mixer.c jack_mixer.h list.h jack_mixer_wrap.c memory_atomic.c memory_atomic.h log.h log.c scale.c jack_compat.h

bin_SCRIPTS = $(srcdir)/jack_mixer.py

_jack_mixer_c.so: _jack_mixer_c.la
	ln -nfs .libs/_jack_mixer_c.so

test: _jack_mixer_c.so
	@./test.py

schemadir = @GCONF_SCHEMA_FILE_DIR@
schema_DATA = jack_mixer.schemas

install-exec-hook:
	ln -vfs jack_mixer.py $(DESTDIR)$(bindir)/jack_mixer

if GCONF_SCHEMAS_INSTALL
install-data-hook:
	GCONF_CONFIG_SOURCE=$(GCONF_SCHEMA_CONFIG_SOURCE) $(GCONFTOOL) --makefile-install-rule $(srcdir)/$(schema_DATA)

uninstall-hook:
	GCONF_CONFIG_SOURCE=$(GCONF_SCHEMA_CONFIG_SOURCE) $(GCONFTOOL) --makefile-uninstall-rule $(srcdir)/$(schema_DATA)
	rm -vf $(DESTDIR)$(bindir)/jack_mixer
endif

pacoinstall:
	test `whoami` == root # test for root
	-paco -rvB jack_mixer
	-paco -lE `pwd` -E /etc -p jack_mixer-`svnversion` "make install"
	-paco -i jack_mixer
