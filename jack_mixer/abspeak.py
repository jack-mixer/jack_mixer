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

import math

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib


class AbspeakWidget(Gtk.EventBox):
    def __init__(self, app):
        super().__init__()
        self.label = Gtk.Label()
        self.add(self.label)
        self.connect("button-press-event", self.on_mouse)
        self.peak = -math.inf
        self.gui_factory = app.gui_factory
        self.gui_factory.connect(
            "auto-reset-peak-meters-changed", self.on_auto_reset_peak_meters_changed
        )
        self.gui_factory.connect(
            "auto-reset-peak-meters-time-seconds-changed",
            self.on_auto_reset_peak_meters_time_seconds_changed
        )
        self.reset_timer_id = None

    def emit_reset(self):
        self.emit("reset")
        context = self.get_style_context()
        context.remove_class("over_zero")
        context.remove_class("is_nan")
        self.reset_timer_id = None
        return False

    def reset_timer(self):
        if self.reset_timer_id is not None:
            GLib.source_remove(self.reset_timer_id)
        self.reset_timer_id = GLib.timeout_add(
            self.gui_factory.auto_reset_peak_meters_time_seconds * 1000, self.emit_reset
        )

    def on_auto_reset_peak_meters_changed(self, widget, event):
        if event is True:
            self.reset_timer()

    def on_auto_reset_peak_meters_time_seconds_changed(self, widget, event):
        self.reset_timer()

    def get_style_context(self):
        return self.label.get_style_context()

    def on_mouse(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button == 1 or event.button == 2 or event.button == 3:
                context = self.get_style_context()
                context.remove_class("over_zero")
                context.remove_class("is_nan")

            if event.button == 1 or event.button == 3:
                self.emit("reset")
            elif event.button == 2:
                adjust = -self.peak

                if abs(adjust) < 30:  # we better don't adjust more than +- 30 dB
                    self.emit("volume-adjust", adjust)

    def set_peak(self, peak):
        if self.gui_factory.auto_reset_peak_meters:
            if peak > self.peak:
                self.reset_timer()
        self.peak = peak
        context = self.get_style_context()

        if math.isnan(peak):
            context.remove_class("over_zero")
            context.add_class("is_nan")
            self.label.set_text("NaN")
        else:
            # TODO: l10n
            text = "%+.1f" % peak
            context.remove_class("is_nan")

            if peak > 0:
                context.add_class("over_zero")

            self.label.set_text(text)


GObject.signal_new(
    "reset", AbspeakWidget, GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION, None, []
)
GObject.signal_new(
    "volume-adjust",
    AbspeakWidget,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [GObject.TYPE_FLOAT],
)
