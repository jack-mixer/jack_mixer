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

jack_mixerdir = $(pkgdatadir)

ACLOCAL_AMFLAGS = -I m4
AM_CFLAGS = $(JACKMIXER_CFLAGS) -D_GNU_SOURCE -Wall -fno-strict-aliasing
if DEV_VERSION
AM_CFLAGS +=  -Werror
endif


jack_mixer_c_la_LDFLAGS = -module -avoid-version

jack_mixer_c_la_LIBADD = $(JACKMIXER_LIBS)

jack_mixer_c_la_SOURCES = \
	jack_mixer.c jack_mixer.h list.h log.h log.c scale.c scale.h jack_compat.h \
	jack_mixer_c.c

EXTRA_DIST = COPYING NEWS

bin_PROGRAMS = jack_mix_box


jack_mix_box_SOURCES = jack_mix_box.c jack_mixer.c scale.c log.c

jack_mix_box_CFLAGS = $(JACKMIXER_CFLAGS)

jack_mix_box_LDADD = $(JACKMIXER_LIBS) -lm




if ENABLE_GUI

SUBDIRS = data

AM_CPPFLAGS = $(PYTHON_INCLUDES)

pkgpyexec_LTLIBRARIES = jack_mixer_c.la

dist_jack_mixer_DATA = \
	abspeak.py \
	channel.py \
	gui.py \
	meter.py \
	nsmclient.py \
	preferences.py \
	scale.py \
	serialization.py \
	serialization_xml.py \
	slider.py \
	styling.py \
	version.py

CLEANFILES = *.pyc
EXTRA_DIST += test.py jack_mixer.py

bin_SCRIPTS = $(srcdir)/jack_mixer.py


jack_mixer_c.so: jack_mixer_c.la
	ln -nfs .libs/jack_mixer_c.so

test: _jack_mixer_c.so
	@./test.py

install-exec-hook:
	ln -vfs jack_mixer.py $(DESTDIR)$(bindir)/jack_mixer

pacoinstall:
	test `whoami` == root # test for root
	-paco -rvB jack_mixer
	-paco -lE `pwd` -E /etc -p jack_mixer-`svnversion` "make install"
	-paco -i jack_mixer

endif
