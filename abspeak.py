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

from gi.repository import Gtk
from gi.repository import Gdk
import fpconst
from gi.repository import Pango
from gi.repository import GObject

class AbspeakWidget(Gtk.EventBox):
    def __init__(self):
        GObject.GObject.__init__(self)
        self.label = Gtk.Label()
        #attrs = Pango.AttrList()
        #font_attr =  Pango.AttrFamily("monospace")
        #attrs.insert(font_attr)
        #self.label.set_attributes(attrs)
        self.add(self.label)
        self.connect("button-press-event", self.on_mouse)
        self.peak = fpconst.NegInf

    def on_mouse(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button == 1:
                self.emit("reset")
            elif event.button == 2:
                adjust = -self.peak
                if abs(adjust) < 30:    # we better don't adjust more than +- 30 dB
                    self.emit("volume-adjust", adjust)

    def set_peak(self, peak):
        self.peak = peak
        if fpconst.isNaN(peak):
            self.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(int(65535 * 0.7), 0, 0))
            self.label.set_text("NaN")
        else:
            text = "%+.1f" % peak

            if peak > 0:
                self.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(int(65535 * 0.8), int(65535 * 0.3), 0))
            else:
                pass
                #self.modify_bg(Gtk.StateType.NORMAL, self.label.style.bg[Gtk.StateType.NORMAL])

            self.label.set_text(text)

GObject.signal_new("reset", AbspeakWidget,
                   GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION, None, [])
GObject.signal_new("volume-adjust", AbspeakWidget,
                   GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION, None, [GObject.TYPE_FLOAT])
