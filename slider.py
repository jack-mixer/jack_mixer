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

class AdjustmentdBFS(gtk.Adjustment):
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

gobject.signal_new("volume-changed", AdjustmentdBFS,
                   gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION, gobject.TYPE_NONE, [])


class GtkSlider(gtk.VScale):
    def __init__(self, adjustment):
        gtk.VScale.__init__(self, adjustment)
        self.set_draw_value(False)
        self.set_inverted(True)

        # HACK: we want the behaviour you get with the middle button, so we
        # mangle the events. Clicking with other buttons moves the slider in
        # step increments, clicking with the middle button moves the slider
        # to the location of the click.
        self.connect('button-press-event', self.button_press_event)
        self.connect('button-release-event', self.button_release_event)

    def button_press_event(self, widget, event):
        event.button = 2
        return False

    def button_release_event(self, widget, event):
        event.button = 2
        return False


class CustomSliderWidget(gtk.DrawingArea):
    def __init__(self, adjustment):
        gtk.DrawingArea.__init__(self)

        self.adjustment = adjustment

        self.connect("expose-event", self.on_expose)
        self.connect("size-request", self.on_size_request)
        self.connect("size_allocate", self.on_size_allocate)
        adjustment.connect("value-changed", self.on_value_changed)
        self.connect("button-press-event", self.on_mouse)
        self.connect("motion-notify-event", self.on_mouse)
        self.set_events(gtk.gdk.BUTTON1_MOTION_MASK | gtk.gdk.BUTTON1_MOTION_MASK | gtk.gdk.BUTTON_PRESS_MASK)

    def on_mouse(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            #print "mouse button %u pressed %u:%u" % (event.button, event.x, event.y)
            if event.button == 1:
                if event.y >= self.slider_rail_up and event.y < self.slider_rail_up + self.slider_rail_height:
                    self.adjustment.set_value(1 - float(event.y - self.slider_rail_up)/float(self.slider_rail_height))
            elif event.button == 2:
                self.adjustment.reset()
        elif event.type == gtk.gdk.MOTION_NOTIFY:
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

    def on_expose(self, widget, event):
        cairo_ctx = widget.window.cairo_create()

        # set a clip region for the expose event
        cairo_ctx.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
        cairo_ctx.clip()

        self.draw(cairo_ctx)

        return False

    def on_size_allocate(self, widget, allocation):
        #print allocation.x, allocation.y, allocation.width, allocation.height
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
        if self.flags() & gtk.HAS_FOCUS:
            state = gtk.STATE_PRELIGHT
        else:
            state = gtk.STATE_NORMAL

        #cairo_ctx.rectangle(0, 0, self.width, self.height)
        #cairo_ctx.set_source_color(self.style.bg[state])
        #cairo_ctx.fill_preserve()
        cairo_ctx.set_source_color(self.style.fg[state])
        #cairo_ctx.stroke()

        slider_knob_width = self.width * 3 / 4
        slider_knob_height = self.width * 3 / 2
        slider_knob_height -= slider_knob_height % 2
        slider_knob_height += 1

        slider_x = self.width/2

        cairo_ctx.set_line_width(1)

        # slider rail
        cairo_ctx.set_source_color(self.style.dark[state])
        self.slider_rail_up = slider_knob_height/2 + (self.width - slider_knob_width)/2
        self.slider_rail_height = self.height - 2 * self.slider_rail_up
        cairo_ctx.move_to(slider_x, self.slider_rail_up)
        cairo_ctx.line_to(slider_x, self.slider_rail_height + self.slider_rail_up)
        cairo_ctx.stroke()

        # slider knob
        slider_y = round(self.slider_rail_up + self.slider_rail_height * (1 - self.adjustment.get_value()))
        cairo_ctx.rectangle(slider_x - float(slider_knob_width)/2,
                            slider_y - slider_knob_height/2,
                            float(slider_knob_width),
                            slider_knob_height)
        cairo_ctx.set_source_color(self.style.bg[state])
        cairo_ctx.fill_preserve()
        cairo_ctx.set_source_color(self.style.fg[state])
        cairo_ctx.stroke()
        # slider knob marks
        cairo_ctx.set_source_color(self.style.fg[state])
        for i in range(int(slider_knob_height/2))[8:]:
            if i % 2 == 0:
                correction = 1.0 + (float(slider_knob_height)/2.0 - float(i)) / 10.0
                correction *= 2
                y = slider_y - i
                w = float(slider_knob_width)/2.0 - correction
                x1 = slider_x - w
                x2 = slider_x + w
                cairo_ctx.move_to(x1, y+0.5)
                cairo_ctx.line_to(x2, y+0.5)
                y = slider_y + i
                cairo_ctx.move_to(x1, y-0.5)
                cairo_ctx.line_to(x2, y-0.5)
        cairo_ctx.set_line_width(1)
        cairo_ctx.stroke()
        # slider knob middle mark
        cairo_ctx.move_to(slider_x - float(slider_knob_width)/2, slider_y)
        cairo_ctx.line_to(slider_x + float(slider_knob_width)/2, slider_y)
        cairo_ctx.set_line_width(2)
        cairo_ctx.stroke()
