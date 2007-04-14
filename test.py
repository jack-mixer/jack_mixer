#!/usr/bin/env python
#
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

import jack_mixer_c

jack_mixer_c.init("test")

print "Channels count: %u" % jack_mixer_c.get_channels_count()

channel = jack_mixer_c.add_channel("Channel 1", True)

if jack_mixer_c.channel_is_stereo(channel):
    channel_type = "Stereo"
else:
    channel_type = "Mono"

channel_name = jack_mixer_c.channel_get_name(channel)

print "%s channel \"%s\"" % (channel_type, channel_name)

print "Channel stereo read %s" % repr(jack_mixer_c.channel_stereo_meter_read(channel))
print "Channel mono read %s" % repr(jack_mixer_c.channel_mono_meter_read(channel))

print "Channels count: %u" % jack_mixer_c.get_channels_count()

jack_mixer_c.remove_channel(channel)

print "Channels count: %u" % jack_mixer_c.get_channels_count()

jack_mixer_c.uninit()
