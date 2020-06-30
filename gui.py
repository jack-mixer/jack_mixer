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

import gi
from gi.repository import GObject
import os
import configparser
from serialization import SerializedObject

try:
    import xdg
    from xdg import BaseDirectory
except:
    xdg = None

def lookup_scale(scales, scale_id):
    for scale in scales:
        if scale_id == scale.scale_id:
            return scale
    return None

class Factory(GObject.GObject, SerializedObject):

    def __init__(self, topwindow, meter_scales, slider_scales):
        self.midi_behavior_modes = [ 'Jump To Value', 'Pick Up' ]
        GObject.GObject.__init__(self)
        self.topwindow = topwindow
        self.meter_scales = meter_scales
        self.slider_scales = slider_scales
        self.set_default_preferences()
        if xdg:
            self.config = configparser.ConfigParser()
            self.path = os.path.join(BaseDirectory.save_config_path('jack_mixer'), 'preferences.ini')
            if os.path.isfile(self.path):
                self.read_preferences()
            else:
                self.write_preferences()
        else:
            print("Cannot load PyXDG. Your preferences will not be preserved across jack_mixer invocations")

    def set_default_preferences(self):
        self.default_meter_scale = self.meter_scales[0]
        self.default_slider_scale = self.slider_scales[0]
        self.vumeter_color = '#ccb300'
        self.vumeter_color_scheme = 'default'
        self.use_custom_widgets = False
        self.midi_behavior_mode = 0

    def read_preferences(self):
        self.config.read(self.path)
        scale_id = self.config['Preferences']['default_meter_scale']
        self.default_meter_scale = lookup_scale(self.meter_scales, scale_id)
        if not self.default_meter_scale:
            self.default_meter_scale = meter_scales[0]

        scale_id = self.config['Preferences']['default_slider_scale']
        self.default_slider_scale = lookup_scale(self.slider_scales, scale_id)
        if not self.default_slider_scale:
            self.default_slider_scale = slider_scales[0]

        self.vumeter_color_scheme = self.config['Preferences']['vumeter_color_scheme']
        if not self.vumeter_color_scheme:
            self.vumeter_color_scheme = 'default'

        self.vumeter_color = self.config['Preferences']['vumeter_color']
        if not self.vumeter_color:
            self.vumeter_color = '#ccb300'

        self.use_custom_widgets = self.config["Preferences"]["use_custom_widgets"] == 'True'

    def write_preferences(self):
        self.config['Preferences'] = {}
        self.config['Preferences']['default_meter_scale'] = self.default_meter_scale.scale_id
        self.config['Preferences']['default_slider_scale'] = self.default_slider_scale.scale_id
        self.config['Preferences']['vumeter_color_scheme'] = self.vumeter_color_scheme
        self.config['Preferences']['vumeter_color'] = self.vumeter_color
        self.config['Preferences']['use_custom_widgets'] = str(self.use_custom_widgets)
        with open(self.path, 'w') as configfile:
            self.config.write(configfile)

    def set_default_meter_scale(self, scale):
        if scale:
            self.default_meter_scale = scale
            if xdg:
                self.write_preferences()
            self.emit("default-meter-scale-changed", self.default_meter_scale)
        else:
            print("Ignoring default_meter_scale setting, because \"%s\" scale is not known" % scale_id)

    def set_default_slider_scale(self, scale):
        if scale:
            self.default_slider_scale = scale
            if xdg:
                self.write_preferences()
            self.emit("default-slider-scale-changed", self.default_slider_scale)
        else:
            print("Ignoring default_slider_scale setting, because \"%s\" scale is not known" % scale_id)

    def set_vumeter_color(self, color):
        self.vumeter_color = color
        if xdg:
            self.write_preferences()
        self.emit('vumeter-color-changed', self.vumeter_color)

    def set_vumeter_color_scheme(self, color_scheme):
        self.vumeter_color_scheme = color_scheme
        if xdg:
            self.write_preferences()
        self.emit('vumeter-color-scheme-changed', self.vumeter_color_scheme)

    def set_use_custom_widgets(self, use_custom):
        self.use_custom_widgets = use_custom
        if xdg:
            self.write_preferences()
        self.emit('use-custom-widgets-changed', self.use_custom_widgets)

    def set_midi_behavior_mode(self, mode):
        self.midi_behavior_mode = mode
        self.emit("midi-behavior-mode-changed", self.midi_behavior_mode)

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

    def get_midi_behavior_mode(self):
        return self.midi_behavior_mode

    @classmethod
    def serialization_name(cls):
        return 'gui_factory'

    def serialize(self, object_backend):
        object_backend.add_property("midi_behavior_mode",
                self.midi_behavior_modes[self.get_midi_behavior_mode()])

    def unserialize_property(self, name, value):
        if name == "midi_behavior_mode":
            self.set_midi_behavior_mode(self.midi_behavior_modes.index(value))
            return True
        return False

GObject.signal_new("default-meter-scale-changed", Factory,
                GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
                None, [GObject.TYPE_PYOBJECT])
GObject.signal_new("default-slider-scale-changed", Factory,
                GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
                None, [GObject.TYPE_PYOBJECT])
GObject.signal_new('vumeter-color-changed', Factory,
                GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
                None, [str])
GObject.signal_new('vumeter-color-scheme-changed', Factory,
                GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
                None, [str])
GObject.signal_new('use-custom-widgets-changed', Factory,
                GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
                None, [bool])
GObject.signal_new('midi-behavior-mode-changed', Factory,
                GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
                None, [int])
