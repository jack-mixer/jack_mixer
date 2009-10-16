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

import gtk
import gobject

class adjustment_dBFS(gtk.Adjustment):
    def __init__(self, scale, default_db):
        self.default_value = scale.db_to_scale(default_db)
        self.db = default_db
        self.scale = scale
        gtk.Adjustment.__init__(self, self.default_value, 0.0, 1.0, 0.02)
        self.connect("value-changed", self.on_value_changed)
        self.disable_value_notify = False

    def step_up(self):
        self.set_value(self.get_value() + self.step_increment)

    def step_down(self):
        self.set_value(self.get_value() - self.step_increment)

    def reset(self):
        self.set_value(self.default_value)

    def get_value_db(self):
        return self.db

    def set_value_db(self, db):
        self.db = db
        self.disable_value_notify = True
        self.set_value(self.scale.db_to_scale(db))
        self.disable_value_notify = False
        self.emit("volume-changed")

    def on_value_changed(self, adjustment):
        if not self.disable_value_notify:
            self.db = self.scale.scale_to_db(self.get_value())
            self.emit("volume-changed")

    def set_scale(self, scale):
        self.scale = scale
        self.disable_value_notify = True
        self.set_value(self.scale.db_to_scale(self.db))
        self.disable_value_notify = False

gobject.signal_new("volume-changed", adjustment_dBFS, gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION, gobject.TYPE_NONE, [])


class widget(gtk.VScale):
    def __init__(self, adjustment):
        gtk.VScale.__init__(self, adjustment)
        self.set_draw_value(False)
        self.set_inverted(True)
