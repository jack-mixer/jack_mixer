# This file is part of jack_mixer
#
# Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
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

# Install prefix
INSTALL_PREFIX=/usr

# Where to install GConf schema, this must match the way GConf is configured
INSTALL_GCONF_SCHEMAS_DIR=/etc/gconf/schemas

CC = gcc -c -I/usr/include/python2.4 -Wall -Werror -D_GNU_SOURCE -fPIC

.PHONY: run test install uninstall

_jack_mixer_c.so: jack_mixer.o jack_mixer_wrap.o
	ld -shared jack_mixer.o jack_mixer_wrap.o -o _jack_mixer_c.so -ljack -lm

jack_mixer_wrap.c: jack_mixer.h
	swig -python jack_mixer.h

jack_mixer.o: jack_mixer.c jack_mixer.h
	$(CC) jack_mixer.c

jack_mixer_wrap.o: jack_mixer_wrap.c
	$(CC) jack_mixer_wrap.c

clean:
	-@rm jack_mixer_wrap.o jack_mixer.o jack_mixer_wrap.c jack_mixer_c.py jack_mixer_c.pyc _jack_mixer_c.so

run: _jack_mixer_c.so
	./jack_mixer.py

test: _jack_mixer_c.so
	@./test.py

FILES = _jack_mixer_c.so jack_mixer_c.py abspeak.py channel.py gui.py jack_mixer.py meter.py scale.py serialization.py serialization_xml.py slider.py jack_mixer.glade

install: _jack_mixer_c.so
	mkdir -p $(INSTALL_PREFIX)/share/jack_mixer/
	cp $(FILES) $(INSTALL_PREFIX)/share/jack_mixer/
	ln -nfs $(INSTALL_PREFIX)/share/jack_mixer/jack_mixer.py $(INSTALL_PREFIX)/bin/jack_mixer
	cp jack_mixer.schemas $(INSTALL_GCONF_SCHEMAS_DIR)
	GCONF_CONFIG_SOURCE=`gconftool-2 --get-default-source` gconftool-2 --makefile-install-rule $(INSTALL_GCONF_SCHEMAS_DIR)/jack_mixer.schemas

uninstall:
	GCONF_CONFIG_SOURCE=`gconftool-2 --get-default-source` gconftool-2 --makefile-uninstall-rule $(INSTALL_GCONF_SCHEMAS_DIR)/jack_mixer.schemas
	rm $(INSTALL_GCONF_SCHEMAS_DIR)/jack_mixer.schemas
	rm -r $(INSTALL_PREFIX)/share/jack_mixer/
	rm $(INSTALL_PREFIX)/bin/jack_mixer
