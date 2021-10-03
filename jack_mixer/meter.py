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
from gi.repository import Gtk
from gi.repository import Gdk

from . import scale as scalemod


log = logging.getLogger(__name__)

METER_MIN_WIDTH = 24
METER_MAX_WIDTH = 40

class MeterWidget(Gtk.DrawingArea):
    def __init__(self, scale):
        log.debug("Creating MeterWidget for scale %s", scale)
        super().__init__()
        self.color_bg = Gdk.Color(0, 0, 0)
        self.color_value = None
        self.color_mark = Gdk.Color(int(65535 * 0.2), int(65535 * 0.2), int(65535 * 0.2))
        self.width = 0
        self.height = 0
        self.cache_surface = None

        self.min_width = METER_MIN_WIDTH
        self.preferred_width = METER_MAX_WIDTH
        self.current_width_size_request = self.preferred_width
        self.preferred_height = 200
        self.set_scale(scale)

        self.widen()

        self.connect("draw", self.draw)
        self.connect("size-allocate", self.on_size_allocate)

    def narrow(self):
        return self.widen(False)

    def widen(self, flag=True):
        self.current_width_size_request = self.preferred_width if flag else self.min_width
        self.set_size_request(self.current_width_size_request, self.preferred_height)

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
        self.width = float(allocation.width)
        self.height = float(allocation.height)
        self.font_size = 10
        self.cache_surface = None

    def invalidate_all(self):
        self.queue_draw_area(0, 0, int(self.width), int(self.height))

    def draw_background(self, cairo_ctx):
        if not self.cache_surface:
            self.cache_surface = cairo.Surface.create_similar(
                cairo_ctx.get_target(), cairo.CONTENT_COLOR, int(self.width), int(self.height)
            )
            cache_cairo_ctx = cairo.Context(self.cache_surface)

            cache_cairo_ctx.set_source_rgba(0, 0, 0, 0)
            cache_cairo_ctx.rectangle(0, 0, self.width, self.height)
            cache_cairo_ctx.fill()

            cache_cairo_ctx.set_source_rgba(0.2, 0.2, 0.2, 1)
            cache_cairo_ctx.select_font_face("Fixed")
            cache_cairo_ctx.set_font_size(self.font_size)
            glyph_width = self.font_size * 3 / 5  # avarage glyph ratio

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
            cairo_ctx.set_source_rgb(
                self.color_value.red / 65535.0,
                self.color_value.green / 65535.0,
                self.color_value.blue / 65535.0,
            )
        else:
            height = self.height
            gradient = cairo.LinearGradient(1, 1, width - 1, height - 1)

            if self.scale.scale_id == "K20":
                gradient.add_color_stop_rgb(0, 1, 0, 0)
                gradient.add_color_stop_rgb(0.38, 1, 1, 0)
                gradient.add_color_stop_rgb(0.5, 0, 1, 0)
                gradient.add_color_stop_rgb(1, 0, 0, 1)
            elif self.scale.scale_id == "K14":
                gradient.add_color_stop_rgb(0, 1, 0, 0)
                gradient.add_color_stop_rgb(1 - self.scale.db_to_scale(-14), 1, 1, 0)
                gradient.add_color_stop_rgb(1 - self.scale.db_to_scale(-24), 0, 1, 0)
                gradient.add_color_stop_rgb(1, 0, 0, 1)
            else:
                gradient.add_color_stop_rgb(0, 1, 0, 0)
                gradient.add_color_stop_rgb(0.2, 1, 1, 0)
                gradient.add_color_stop_rgb(1, 0, 1, 0)

            cairo_ctx.set_source(gradient)

        cairo_ctx.rectangle(x, self.height * (1 - value), width, self.height * value)
        cairo_ctx.fill()

    def draw_peak(self, cairo_ctx, value, x, width):
        cairo_ctx.set_source_rgb(1, 1, 1)
        cairo_ctx.rectangle(x, self.height * (1 - value), width, 2.5)
        cairo_ctx.fill()

    def set_scale(self, scale):
        self.kmetering = isinstance(scale, (scalemod.K14, scalemod.K20))
        self.scale = scale
        self.cache_surface = None
        self.invalidate_all()


class MonoMeterWidget(MeterWidget):
    def __init__(self, scale):
        super().__init__(scale)
        self.value = 0.0
        self.pk = 0.0
        self.raw_value = 0.0
        self.raw_pk = 0.0

    def draw(self, widget, cairo_ctx):
        self.draw_background(cairo_ctx)
        width = self.current_width_size_request / 1.5
        x = 0.5 * (self.width - width)
        self.draw_value(cairo_ctx, self.value, x, width)

        if self.kmetering:
            self.draw_peak(cairo_ctx, self.pk, x, width)

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

    def set_value_kmeter(self, value, pk):
        if value == self.raw_value and pk == self.raw_pk:
            return

        self.raw_value = value
        self.raw_pk = pk
        old_value = self.value
        old_pk = self.pk
        self.value = self.scale.db_to_scale(value)
        self.pk = self.scale.db_to_scale(pk)

        if (abs(old_value - self.value) * self.height) > 0.01 or (
            abs(old_pk - self.pk) * self.height
        ) > 0.01:
            self.invalidate_all()


class StereoMeterWidget(MeterWidget):
    def __init__(self, scale):
        super().__init__(scale)
        self.pk_left = 0.0
        self.pk_right = 0.0

        self.left = 0.0
        self.right = 0.0

        self.raw_left_pk = 0.0
        self.raw_right_pk = 0.0

        self.raw_left = 0.0
        self.raw_right = 0.0

    def draw(self, widget, cairo_ctx):
        self.draw_background(cairo_ctx)

        width = self.current_width_size_request / 5.0
        left_x = 0.5 * self.width - self.current_width_size_request / 5.0 - 0.5 * width
        right_x = 0.5 * self.width + self.current_width_size_request / 5.0 - 0.5 * width

        self.draw_value(cairo_ctx, self.left, left_x, width)
        self.draw_value(cairo_ctx, self.right, right_x, width)

        if self.kmetering:
            self.draw_peak(cairo_ctx, self.pk_left, left_x, width)
            self.draw_peak(cairo_ctx, self.pk_right, right_x, width)

    def set_values(self, left, right):
        if left == self.raw_left and right == self.raw_right:
            return

        self.raw_left = left
        self.raw_right = right
        old_left = self.left
        old_right = self.right
        self.left = self.scale.db_to_scale(left)
        self.right = self.scale.db_to_scale(right)

        if (
            (abs(old_left - self.left) * self.height) > 0.01
            or (abs(old_right - self.right) * self.height) > 0.01
        ):
            self.invalidate_all()

    def set_values_kmeter(self, left, right, pk_l, pk_r):
        if (
            left == self.raw_left
            and right == self.raw_right
            and pk_l == self.raw_left_pk
            and pk_r == self.raw_right_pk
        ):
            return

        self.raw_left = left
        self.raw_right = right
        self.raw_left_pk = pk_l
        self.raw_right_pk = pk_r
        old_left = self.left
        old_right = self.right
        old_pk_left = self.pk_left
        old_pk_right = self.pk_right
        self.left = self.scale.db_to_scale(left)
        self.right = self.scale.db_to_scale(right)
        self.pk_left = self.scale.db_to_scale(pk_l)
        self.pk_right = self.scale.db_to_scale(pk_r)

        if (
            (abs(old_left - self.left) * self.height) > 0.01
            or (abs(old_right - self.right) * self.height) > 0.01
            or (abs(old_pk_left - self.pk_left) * self.height) > 0.01
            or (abs(old_pk_right - self.pk_right) * self.height) > 0.01
        ):
            self.invalidate_all()
