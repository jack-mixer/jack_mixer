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
import cairo

class MeterWidget(gtk.DrawingArea):
    def __init__(self, scale):
        gtk.DrawingArea.__init__(self)

        self.scale = scale

        self.connect("expose-event", self.on_expose)
        self.connect("size-request", self.on_size_request)
        self.connect("size_allocate", self.on_size_allocate)

        self.color_bg = gtk.gdk.Color(0,0,0)
        self.color_value = None
        self.color_mark = gtk.gdk.Color(int(65535 * 0.2), int(65535 * 0.2), int(65535 * 0.2))
        self.width = 0
        self.height = 0
        self.cache_surface = None

    def set_color(self, color):
        self.color_value = color
        self.cache_surface = None
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
        self.cache_surface = None

    def on_size_request(self, widget, requisition):
        #print "size-request, %u x %u" % (requisition.width, requisition.height)
        requisition.width = 20
        return

    def invalidate_all(self):
        self.queue_draw_area(0, 0, int(self.width), int(self.height))

    def draw_background(self, cairo_ctx):
        if not self.cache_surface:
            self.cache_surface = cairo.Surface.create_similar(
                            cairo_ctx.get_target(),
                            cairo.CONTENT_COLOR,
                            int(self.width),
                            int(self.height))
            cache_cairo_ctx = cairo.Context(self.cache_surface)

            cache_cairo_ctx.set_source_rgba(0, 0, 0, 0)
            cache_cairo_ctx.rectangle(0, 0, self.width, self.height)
            cache_cairo_ctx.fill()

            cache_cairo_ctx.set_source_rgba(0.2, 0.2, 0.2, 1)
            cache_cairo_ctx.select_font_face("Fixed")
            cache_cairo_ctx.set_font_size(self.font_size)
            glyph_width = self.font_size * 3 / 5 # avarage glyph ratio
            for mark in self.scale.get_marks():
                mark_position = int(self.height * (1 - mark.scale))
                cache_cairo_ctx.move_to(0, mark_position)
                cache_cairo_ctx.line_to(self.width, mark_position)
                cache_cairo_ctx.stroke()
                x_correction = self.width / 2 - glyph_width * len(mark.text) / 2
                cache_cairo_ctx.move_to(x_correction, mark_position - 2)
                cache_cairo_ctx.show_text(mark.text)
        cairo_ctx.set_source_surface(self.cache_surface, 0, 0)
        cairo_ctx.paint()

    def draw_value(self, cairo_ctx, value, x, width):
        if self.color_value is not None:
            cairo_ctx.set_source_color(self.color_value)
        else:
            height = self.allocation.height
            gradient = cairo.LinearGradient(1, 1, width-1, height-1)
            gradient.add_color_stop_rgb(0, 1, 0, 0)
            gradient.add_color_stop_rgb(0.2, 1, 1, 0)
            gradient.add_color_stop_rgb(1, 0, 1, 0)
            cairo_ctx.set_source(gradient)
        cairo_ctx.rectangle(x, self.height * (1 - value), width, self.height * value)
        cairo_ctx.fill()

    def set_scale(self, scale):
        self.scale = scale
        self.cache_surface = None
        self.invalidate_all()

class MonoMeterWidget(MeterWidget):
    def __init__(self, scale):
        MeterWidget.__init__(self, scale)
        self.value = 0.0
        self.raw_value = 0.0

    def draw(self, cairo_ctx):
        self.draw_background(cairo_ctx)
        self.draw_value(cairo_ctx, self.value, self.width/4.0, self.width/2.0)

    def set_value(self, value):
        if value != self.raw_value:
            self.raw_value = value
            self.value = self.scale.db_to_scale(value)
            self.invalidate_all()
        if value == self.raw_value:
            return
        self.raw_value = value
        old_value = self.value
        self.value = self.scale.db_to_scale(value)
        if (abs(old_value-self.value) * self.height) > 1:
            self.invalidate_all()

class StereoMeterWidget(MeterWidget):
    def __init__(self, scale):
        MeterWidget.__init__(self, scale)
        self.left = 0.0
        self.right = 0.0

        self.raw_left = 0.0
        self.raw_right = 0.0

    def draw(self, cairo_ctx):
        self.draw_background(cairo_ctx)
        self.draw_value(cairo_ctx, self.left, self.width/5.0, self.width/5.0)
        self.draw_value(cairo_ctx, self.right, self.width/5.0 * 3.0, self.width/5.0)

    def set_values(self, left, right):
        if left == self.raw_left and right == self.raw_right:
            return
        self.raw_left = left
        self.raw_right = right
        old_left = self.left
        old_right = self.right
        self.left = self.scale.db_to_scale(left)
        self.right = self.scale.db_to_scale(right)
        if (abs(old_left-self.left) * self.height) > 1 or (abs(old_right-self.right) * self.height) > 1:
            self.invalidate_all()
