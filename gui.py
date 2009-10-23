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

try:
    import gconf
except:
    print "Cannot load Python bindings for GConf, your preferences will not be preserved across jack_mixer invocations"
    gconf = None

def lookup_scale(scales, scale_id):
    for scale in scales:
        if scale_id == scale.scale_id:
            return scale
    return None

class factory(gobject.GObject):
    def __init__(self, topwindow, meter_scales, slider_scales):
        gobject.GObject.__init__(self)
        self.topwindow = topwindow
        self.meter_scales = meter_scales
        self.slider_scales = slider_scales

        if gconf:
            self.gconf_client = gconf.client_get_default()

            scale_id = self.gconf_client.get_string("/apps/jack_mixer/default_meter_scale")
            self.default_meter_scale = lookup_scale(meter_scales, scale_id)
            if not self.default_meter_scale:
                self.default_meter_scale = meter_scales[0]

            scale_id = self.gconf_client.get_string("/apps/jack_mixer/default_slider_scale")
            self.default_slider_scale = lookup_scale(slider_scales, scale_id)
            if not self.default_slider_scale:
                self.default_slider_scale = slider_scales[0]

            self.vumeter_color_scheme = self.gconf_client.get_string(
                            '/apps/jack_mixer/vumeter_color_scheme')
            self.vumeter_color = self.gconf_client.get_string(
                            '/apps/jack_mixer/vumeter_color')
            if not self.vumeter_color:
                self.vumeter_color = '#ccb300'

            self.use_custom_widgets = self.gconf_client.get_bool(
                            '/apps/jack_mixer/use_custom_widgets')

            self.gconf_client.add_dir("/apps/jack_mixer", gconf.CLIENT_PRELOAD_NONE)
            self.gconf_client.notify_add("/apps/jack_mixer/default_meter_scale", self.on_gconf_default_meter_scale_changed)
            self.gconf_client.notify_add("/apps/jack_mixer/default_slider_scale", self.on_gconf_default_slider_scale_changed)
            self.gconf_client.notify_add('/apps/jack_mixer/vumeter_color',
                            self.on_gconf_vumeter_color_change)
            self.gconf_client.notify_add('/apps/jack_mixer/vumeter_color_scheme',
                            self.on_gconf_vumeter_color_scheme_change)
            self.gconf_client.notify_add('/apps/jack_mixer/use_custom_widgets',
                            self.on_gconf_use_custom_widgets_change)
        else:
            self.default_meter_scale = meter_scales[0]
            self.default_slider_scale = slider_scales[0]
            self.vumeter_color = '#ccb300'
            self.vumeter_color_scheme = 'default'
            self.use_custom_widgets = False

    def on_gconf_default_meter_scale_changed(self, client, connection_id, entry, args):
        #print "GConf default_meter_scale changed"
        scale_id = entry.get_value().get_string()
        scale = lookup_scale(self.meter_scales, scale_id)
        self.set_default_meter_scale(scale, from_gconf=True)

    def set_default_meter_scale(self, scale, from_gconf=False):
        if scale:
            if gconf and not from_gconf:
                self.gconf_client.set_string("/apps/jack_mixer/default_meter_scale", scale.scale_id)
            else:
                self.default_meter_scale = scale
                self.emit("default-meter-scale-changed", self.default_meter_scale)
        else:
            print "Ignoring GConf default_meter_scale setting, because \"%s\" scale is not known" % scale_id

    def on_gconf_default_slider_scale_changed(self, client, connection_id, entry, args):
        #print "GConf default_slider_scale changed"
        scale_id = entry.get_value().get_string()
        scale = lookup_scale(self.slider_scales, scale_id)
        self.set_default_slider_scale(scale, from_gconf=True)

    def set_default_slider_scale(self, scale, from_gconf=False):
        if scale:
            if gconf and not from_gconf:
                self.gconf_client.set_string("/apps/jack_mixer/default_slider_scale", scale.scale_id)
            else:
                self.default_slider_scale = scale
                self.emit("default-slider-scale-changed", self.default_slider_scale)
        else:
            print "Ignoring GConf default_slider_scale setting, because \"%s\" scale is not known" % scale_id

    def set_vumeter_color(self, color, from_gconf=False):
        if gconf and not from_gconf:
            self.gconf_client.set_string('/apps/jack_mixer/vumeter_color', color)
        else:
            self.vumeter_color = color
            self.emit('vumeter-color-changed', self.vumeter_color)

    def on_gconf_vumeter_color_change(self, client, connection_id, entry, args):
        color = entry.get_value().get_string()
        self.set_vumeter_color(color, from_gconf=True)

    def set_vumeter_color_scheme(self, color_scheme, from_gconf=False):
        if gconf and not from_gconf:
            self.gconf_client.set_string('/apps/jack_mixer/vumeter_color_scheme', color_scheme)
        else:
            self.vumeter_color_scheme = color_scheme
            self.emit('vumeter-color-scheme-changed', self.vumeter_color_scheme)

    def on_gconf_vumeter_color_scheme_change(self, client, connection_id, entry, args):
        color_scheme = entry.get_value().get_string()
        self.set_vumeter_color_scheme(color_scheme, from_gconf=True)

    def set_use_custom_widgets(self, use_custom, from_gconf=False):
        if gconf and not from_gconf:
            self.gconf_client.set_bool('/apps/jack_mixer/use_custom_widgets', use_custom)
        else:
            self.use_custom_widgets = use_custom
            self.emit('use-custom-widgets-changed', self.use_custom_widgets)

    def on_gconf_use_custom_widgets_change(self, client, connection_id, entry, args):
        use_custom = entry.get_value().get_bool()
        self.set_use_custom_widgets(use_custom, from_gconf=True)

    def get_default_meter_scale(self):
        return self.default_meter_scale

    def get_default_slider_scale(self):
        return self.default_slider_scale

    def get_vumeter_color(self):
        return self.vumeter_color

    def get_vumeter_color_scheme(self):
        return self.vumeter_color_scheme

    def get_use_custom_widgets(self):
        return self.use_custom_widgets

gobject.signal_new("default-meter-scale-changed", factory, gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION, gobject.TYPE_NONE, [gobject.TYPE_PYOBJECT])
gobject.signal_new("default-slider-scale-changed", factory, gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION, gobject.TYPE_NONE, [gobject.TYPE_PYOBJECT])
gobject.signal_new('vumeter-color-changed', factory,
                gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                gobject.TYPE_NONE, [str])
gobject.signal_new('vumeter-color-scheme-changed', factory,
                gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                gobject.TYPE_NONE, [str])
gobject.signal_new('use-custom-widgets-changed', factory,
                gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                gobject.TYPE_NONE, [bool])
