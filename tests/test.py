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

mixer = jack_mixer_c.Mixer("test")

print("Channels count: %u" % mixer.channels_count)
channel = mixer.add_channel("Channel 1", True)

if channel.is_stereo:
    channel_type = "Stereo"
else:
    channel_type = "Mono"

channel_name = channel.name

print('%s channel "%s"' % (channel_type, channel_name))

print("Channel meter read %s" % repr(channel.meter))
print("Channels count: %u" % mixer.channels_count)

channel.remove()

print("Channels count: %u" % mixer.channels_count)
