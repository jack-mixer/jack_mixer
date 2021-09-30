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

import logging

import cairo
from gi.repository import Gdk, GObject, Gtk

log = logging.getLogger(__name__)

FADER_MIN_WIDTH = 24
FADER_MAX_WIDTH = 40


class AdjustmentdBFS(Gtk.Adjustment):
    def __init__(self, scale, default_db, step_inc):
        self.default_value = scale.db_to_scale(default_db)
        self.db = default_db
        self.scale = scale
        self.step_increment = step_inc
        super().__init__(self.default_value, 0.0, 1.0, step_inc)
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

    def set_value_db(self, db, from_midi=False):
        self.db = db
        self.disable_value_notify = True
        self.set_value(self.scale.db_to_scale(db))
        self.disable_value_notify = False
        if from_midi:
            self.emit("volume-changed-from-midi")
        else:
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


GObject.signal_new(
    "volume-changed",
    AdjustmentdBFS,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [],
)

GObject.signal_new(
    "volume-changed-from-midi",
    AdjustmentdBFS,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [],
)


class BalanceAdjustment(Gtk.Adjustment):
    def __init__(self):
        super().__init__(0.0, -1.0, 1.0, 0.1)
        self.connect("value-changed", self.on_value_changed)
        self.disable_value_notify = False

    def set_balance(self, value, from_midi=False):
        self.disable_value_notify = True
        self.set_value(value)
        self.disable_value_notify = False
        if not from_midi:
            self.emit("balance-changed")

    def on_value_changed(self, adjustment):
        if not self.disable_value_notify:
            self.emit("balance-changed")


GObject.signal_new(
    "balance-changed",
    BalanceAdjustment,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [],
)


class VolumeSlider(Gtk.Scale):
    def __init__(self, adjustment):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.adjustment = adjustment
        self.set_adjustment(adjustment)
        self.set_draw_value(False)
        self.set_inverted(True)
        self._button_down = False
        self._button_down_y = 0
        self._button_down_value = 0
        self.min_width = FADER_MIN_WIDTH
        self.preferred_width = FADER_MAX_WIDTH
        self.preferred_height = 200

        self.connect("button-press-event", self.button_press_event)
        self.connect("button-release-event", self.button_release_event)
        self.connect("motion-notify-event", self.motion_notify_event)
        self.connect("scroll-event", self.scroll_event)

    def narrow(self):
        return self.widen(False)

    def widen(self, flag=True):
        self.set_size_request(
            self.preferred_width if flag else self.min_width, self.preferred_height
        )

    def button_press_event(self, widget, event):
        if event.button == 1:
            if event.state & Gdk.ModifierType.CONTROL_MASK:
                if event.type == Gdk.EventType.BUTTON_PRESS:
                    self.adjustment.set_value_db(0)
                    return True
            elif event.type == Gdk.EventType.BUTTON_PRESS:
                self._button_down = True
                self._button_down_y = event.y
                self._button_down_value = self.adjustment.get_value()
                return True
            elif event.type == Gdk.EventType._2BUTTON_PRESS:
                self.adjustment.set_value(0)
                return True

        return False

    def button_release_event(self, widget, event):
        self._button_down = False
        return False

    def motion_notify_event(self, widget, event):
        slider_length = widget.get_allocation().height - widget.get_style_context().get_property(
            "min-height", Gtk.StateFlags.NORMAL
        )
        if self._button_down:
            delta_y = (self._button_down_y - event.y) / slider_length
            y = self._button_down_value + delta_y
            if y >= 1:
                y = 1
            elif y <= 0:
                y = 0

            self.adjustment.set_value(y)
            return True

    def scroll_event(self, widget, event):
        delta = self.adjustment.step_increment
        value = self.adjustment.get_value()
        if event.direction == Gdk.ScrollDirection.UP:
            y = value + delta
        elif event.direction == Gdk.ScrollDirection.DOWN:
            y = value - delta
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            y = value - event.delta_y * delta

        if y >= 1:
            y = 1
        elif y <= 0:
            y = 0

        self.adjustment.set_value(y)
        return True


class BalanceSlider(Gtk.Scale):
    def __init__(self, adjustment, preferred_width, preferred_height):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.adjustment = adjustment
        self.set_adjustment(adjustment)
        self.set_has_origin(False)
        self.set_draw_value(False)
        self.set_property("has-tooltip", True)
        self._preferred_width = preferred_width
        self._preferred_height = preferred_height
        self._button_down = False

        self.add_mark(-1.0, Gtk.PositionType.TOP)
        self.add_mark(0.0, Gtk.PositionType.TOP)
        self.add_mark(1.0, Gtk.PositionType.TOP)

        self.connect("button-press-event", self.on_button_press_event)
        self.connect("button-release-event", self.on_button_release_event)
        self.connect("motion-notify-event", self.on_motion_notify_event)
        self.connect("scroll-event", self.on_scroll_event)
        self.connect("query-tooltip", self.on_query_tooltip)

    def get_preferred_width(self):
        return self._preferred_width

    def get_preferred_height(self):
        return self._preferred_height

    def on_button_press_event(self, widget, event):
        if event.button == 1:
            if event.type == Gdk.EventType.BUTTON_PRESS:
                self._button_down = True
                self._button_down_x = event.x
                self._button_down_value = self.get_value()
                return True
            elif event.type == Gdk.EventType._2BUTTON_PRESS:
                self.adjustment.set_balance(0)
                return True

        return False

    def on_button_release_event(self, widget, event):
        self._button_down = False
        return False

    def on_motion_notify_event(self, widget, event):
        slider_length = widget.get_allocation().width - widget.get_style_context().get_property(
            "min-width", Gtk.StateFlags.NORMAL
        )

        if self._button_down:
            delta_x = (event.x - self._button_down_x) / slider_length
            x = self._button_down_value + 2 * delta_x
            self.adjustment.set_balance(min(1, max(x, -1)))
            return True

        return False

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip, *args):
        val = int(self.adjustment.get_value() * 50)
        if val == 0:
            tooltip.set_text(_("Center"))
        else:
            tooltip.set_text(
                _("Left: {left} / Right: {right}").format(left=50 - val, right=val + 50)
            )

        return True

    def on_scroll_event(self, widget, event):
        delta = self.get_adjustment().get_step_increment()
        value = self.get_value()

        if event.direction == Gdk.ScrollDirection.UP:
            x = value - delta
        elif event.direction == Gdk.ScrollDirection.DOWN:
            x = value + delta
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            x = value - event.delta_y * delta

        self.set_value(min(1, max(x, -1)))
        return True


class CustomSliderWidget(Gtk.DrawingArea):
    def __init__(self, adjustment):
        super().__init__()
        self.adjustment = adjustment
        self._button_down = False
        self._button_down_y = 0
        self._button_down_value = 0
        self.min_width = FADER_MIN_WIDTH
        self.preferred_width = FADER_MAX_WIDTH
        self.preferred_height = 200

        self.connect("draw", self.on_expose)
        self.connect("size_allocate", self.on_size_allocate)
        adjustment.connect("value-changed", self.on_value_changed)
        self.connect("button-release-event", self.on_button_release_event)
        self.connect("button-press-event", self.on_button_press_event)
        self.connect("motion-notify-event", self.on_motion_notify_event)
        self.connect("scroll-event", self.on_scroll)
        self.set_events(
            Gdk.EventMask.BUTTON1_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
        )

    def narrow(self):
        return self.widen(False)

    def widen(self, flag=True):
        self.set_size_request(
            self.preferred_width if flag else self.min_width, self.preferred_height
        )

    def on_button_press_event(self, widget, event):
        log.debug("Mouse button %u pressed %ux%u", event.button, event.x, event.y)
        if event.button == 1:
            if (
                event.state & Gdk.ModifierType.CONTROL_MASK
                and event.type == Gdk.EventType.BUTTON_PRESS
            ):
                self.adjustment.set_value_db(0)
                return True
            elif event.type == Gdk.EventType.BUTTON_PRESS:
                self._button_down = True
                self._button_down_y = event.y
                self._button_down_value = self.adjustment.get_value()
                return True
            elif event.type == Gdk.EventType._2BUTTON_PRESS:
                self.adjustment.set_value(0)
                return True

        return False

    def on_button_release_event(self, widget, event):
        self._button_down = False
        return False

    def on_motion_notify_event(self, widget, event):
        slider_length = self.slider_rail_height
        if self._button_down:
            delta_y = (self._button_down_y - event.y) / slider_length
            y = self._button_down_value + delta_y
            if y >= 1:
                y = 1
            elif y <= 0:
                y = 0

            self.adjustment.set_value(y)
            return True

    def on_value_changed(self, adjustment):
        self.invalidate_all()

    def on_expose(self, widget, cairo_ctx):
        self.draw(cairo_ctx)
        return False

    def on_scroll(self, widget, event):
        delta = self.adjustment.step_increment
        y = self.adjustment.get_value()
        if event.direction == Gdk.ScrollDirection.UP:
            y = y + delta
        elif event.direction == Gdk.ScrollDirection.DOWN:
            y = y - delta
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            y = y - event.delta_y * delta

        if y >= 1:
            y = 1
        elif y <= 0:
            y = 0

        self.adjustment.set_value(y)
        return True

    def on_size_allocate(self, widget, allocation):
        self.width = float(allocation.width)
        self.height = float(allocation.height)
        self.font_size = 10

    def on_size_request(self, widget, requisition):
        requisition.width = 666

    def invalidate_all(self):
        if hasattr(self, "width") and hasattr(self, "height"):
            self.queue_draw_area(0, 0, int(self.width), int(self.height))

    def draw(self, cairo_ctx):
        if self.has_focus():
            state = Gtk.StateType.PRELIGHT
        else:
            state = Gtk.StateType.NORMAL

        # cairo_ctx.rectangle(0, 0, self.width, self.height)
        # cairo_ctx.set_source_color(self.style.bg[state])
        # cairo_ctx.fill_preserve()
        # Gdk.cairo_set_source_color(cairo_ctx,
        #        self.get_style_context().get_color(state).to_color())
        # cairo_ctx.stroke()

        slider_knob_width = self.preferred_width * 3 / 4 if self.width * 3 / 4 > \
            self.preferred_width * 3 / 4 else self.width * 3 / 4
        slider_knob_height = slider_knob_width * 2
        slider_knob_height -= slider_knob_height % 2
        slider_knob_height += 1

        slider_x = self.width / 2

        cairo_ctx.set_line_width(1)

        # slider rail
        Gdk.cairo_set_source_color(cairo_ctx, self.get_style_context().get_color(state).to_color())
        self.slider_rail_up = slider_knob_height / 2
        self.slider_rail_height = self.height - 2 * self.slider_rail_up
        cairo_ctx.move_to(slider_x, self.slider_rail_up)
        cairo_ctx.line_to(slider_x, self.slider_rail_height + self.slider_rail_up)
        cairo_ctx.stroke()

        # slider knob
        slider_y = round(
            self.slider_rail_up + self.slider_rail_height * (1 - self.adjustment.get_value())
        )
        lg = cairo.LinearGradient(
            slider_x - float(slider_knob_width) / 2,
            slider_y - slider_knob_height / 2,
            slider_x - float(slider_knob_width) / 2,
            slider_y + slider_knob_height / 2,
        )
        slider_alpha = 1.0
        lg.add_color_stop_rgba(0, 0.55, 0.55, 0.55, slider_alpha)
        lg.add_color_stop_rgba(0.1, 0.65, 0.65, 0.65, slider_alpha)
        lg.add_color_stop_rgba(0.1, 0.75, 0.75, 0.75, slider_alpha)
        lg.add_color_stop_rgba(0.125, 0.75, 0.75, 0.75, slider_alpha)
        lg.add_color_stop_rgba(0.125, 0.15, 0.15, 0.15, slider_alpha)
        lg.add_color_stop_rgba(0.475, 0.35, 0.35, 0.35, slider_alpha)
        lg.add_color_stop_rgba(0.475, 0, 0, 0, slider_alpha)
        lg.add_color_stop_rgba(0.525, 0, 0, 0, slider_alpha)
        lg.add_color_stop_rgba(0.525, 0.35, 0.35, 0.35, slider_alpha)
        lg.add_color_stop_rgba(0.875, 0.65, 0.65, 0.65, slider_alpha)
        lg.add_color_stop_rgba(0.875, 0.75, 0.75, 0.75, slider_alpha)
        lg.add_color_stop_rgba(0.900, 0.75, 0.75, 0.75, slider_alpha)
        lg.add_color_stop_rgba(0.900, 0.15, 0.15, 0.15, slider_alpha)
        lg.add_color_stop_rgba(1.000, 0.10, 0.10, 0.10, slider_alpha)
        cairo_ctx.rectangle(
            slider_x - float(slider_knob_width) / 2,
            slider_y - slider_knob_height / 2,
            float(slider_knob_width),
            slider_knob_height,
        )
        Gdk.cairo_set_source_color(
            cairo_ctx, self.get_style_context().get_background_color(state).to_color()
        )
        cairo_ctx.fill_preserve()
        cairo_ctx.set_source(lg)
        cairo_ctx.fill()
