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
from gi.repository import GObject
import cairo

class AdjustmentdBFS(Gtk.Adjustment):
    def __init__(self, scale, default_db):
        self.default_value = scale.db_to_scale(default_db)
        self.db = default_db
        self.scale = scale
        Gtk.Adjustment.__init__(self, self.default_value, 0.0, 1.0, 0.02)
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

GObject.signal_new("volume-changed", AdjustmentdBFS,
                   GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION, None, [])


class GtkSlider(Gtk.VScale):
    def __init__(self, adjustment):
        Gtk.VScale.__init__(self)#, adjustment)
        self.set_adjustment(adjustment)
        self.set_draw_value(False)
        self.set_inverted(True)

        # HACK: we want the behaviour you get with the middle button, so we
        # mangle the events. Clicking with other buttons moves the slider in
        # step increments, clicking with the middle button moves the slider
        # to the location of the click.
        self.connect('button-press-event', self.button_press_event)
        self.connect('button-release-event', self.button_release_event)

    def button_press_event(self, widget, event):
        print "button press", event.button
       # event.button = 2
        return False

    def button_release_event(self, widget, event):
        #event.button = 2
        return False


class CustomSliderWidget(Gtk.DrawingArea):
    def __init__(self, adjustment):
        Gtk.DrawingArea.__init__(self)

        self.adjustment = adjustment

        self.connect("draw", self.on_expose)
        self.connect("size_allocate", self.on_size_allocate)
        adjustment.connect("value-changed", self.on_value_changed)
        self.connect("button-press-event", self.on_mouse)
        self.connect("motion-notify-event", self.on_mouse)
        self.connect("scroll-event", self.on_scroll)
        self.set_events(Gdk.EventMask.BUTTON1_MOTION_MASK |
                Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)

    def on_scroll(self, widget, event):
        delta = 0.05
        value = self.adjustment.get_value()
        if event.direction == Gdk.ScrollDirection.UP:
            y = value + delta
        elif event.direction == Gdk.ScrollDirection.DOWN:
            y = value - delta
        if y >= 1:
            y = 1
        elif y <= 0:
            y = 0
        self.adjustment.set_value(y)
        return True

    def on_mouse(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            #print "mouse button %u pressed %u:%u" % (event.button, event.x, event.y)
            if event.button == 1:
                if event.y >= self.slider_rail_up and event.y < self.slider_rail_up + self.slider_rail_height:
                    self.adjustment.set_value(1 - float(event.y - self.slider_rail_up)/float(self.slider_rail_height))
        elif event.type == Gdk.EventType.MOTION_NOTIFY:
            #print "mouse motion %u:%u" % (event.x, event.y)
            if event.y < self.slider_rail_up:
                y = self.slider_rail_up
            elif event.y > self.slider_rail_up + self.slider_rail_height:
                y = self.slider_rail_up + self.slider_rail_height
            else:
                y = event.y
            self.adjustment.set_value(1 - float(y - self.slider_rail_up)/float(self.slider_rail_height))

        return False

    def on_value_changed(self, adjustment):
        self.invalidate_all()

    def on_expose(self, widget, cairo_ctx):

        self.draw(cairo_ctx)

        return False

    def get_preferred_width(self, widget):
        minimal_width = natural_width = self.width
        return (minimal_width, natural_width)

    def get_preferred_height(self, widget):
        requisition = Gtk.Requisition()
        on_size_request(self, widget, requisition)
        minimal_height = natural_heigt = requisition.height
        return (minimal_height, natural_height)


    def on_size_allocate(self, widget, allocation):
        self.width = float(allocation.width)
        self.height = float(allocation.height)
        self.font_size = 10

    def on_size_request(self, widget, requisition):
        #print "size-request, %u x %u" % (requisition.width, requisition.height)
        requisition.width = 20
        return

    def invalidate_all(self):
        self.queue_draw_area(0, 0, int(self.width), int(self.height))

    def draw(self, cairo_ctx):
        if self.has_focus():
            state = Gtk.StateType.PRELIGHT
        else:
            state = Gtk.StateType.NORMAL

        #cairo_ctx.rectangle(0, 0, self.width, self.height)
        #cairo_ctx.set_source_color(self.style.bg[state])
        #cairo_ctx.fill_preserve()
        #Gdk.cairo_set_source_color(cairo_ctx,
        #        self.get_style_context().get_color(state).to_color())
        #cairo_ctx.stroke()

        slider_knob_width = self.width * 3 / 4
        slider_knob_height = self.width * 3 / 2
        slider_knob_height -= slider_knob_height % 2
        slider_knob_height += 1

        slider_x = self.width/2

        cairo_ctx.set_line_width(1)

        # slider rail
        Gdk.cairo_set_source_color(cairo_ctx,
                self.get_style_context().get_color(state).to_color())
        self.slider_rail_up = slider_knob_height/2 + (self.width - slider_knob_width)/2
        self.slider_rail_height = self.height - 2 * self.slider_rail_up
        cairo_ctx.move_to(slider_x, self.slider_rail_up)
        cairo_ctx.line_to(slider_x, self.slider_rail_height + self.slider_rail_up)
        cairo_ctx.stroke()

        # slider knob
        slider_y = round(self.slider_rail_up + self.slider_rail_height * (1 - self.adjustment.get_value()))
        lg = cairo.LinearGradient(slider_x -
                float(slider_knob_width)/2, slider_y - slider_knob_height/2,
                slider_x - float(slider_knob_width)/2, slider_y +
                slider_knob_height/2)
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
        cairo_ctx.rectangle(slider_x - float(slider_knob_width)/2,
                            slider_y - slider_knob_height/2,
                            float(slider_knob_width),
                            slider_knob_height)
        Gdk.cairo_set_source_color(cairo_ctx,
                self.get_style_context().get_background_color(state).to_color())
        cairo_ctx.fill_preserve()
        cairo_ctx.set_source(lg)
        cairo_ctx.fill()
