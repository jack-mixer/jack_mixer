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

import configparser
import logging
import os

import gi  # noqa: F401
from gi.repository import GObject

try:
    import platformdirs

    confdir = platformdirs.user_config_dir("jack_mixer")
    datadir = platformdirs.user_data_dir("jack_mixer")
except ImportError:
    confdir = None
    datadir = None

from .serialization import SerializedObject


log = logging.getLogger(__name__)


def lookup_scale(scales, scale_id):
    for scale in scales:
        if scale_id == scale.scale_id:
            return scale
    return None


class Factory(GObject.GObject, SerializedObject):
    def __init__(self, topwindow, meter_scales, slider_scales):
        self.languages = [
            (None, _("Use system setting")),
            ("de", "Deutsch"),
            ("en", "English"),
            ("es", "Español"),
            ("fr", "Français"),
        ]
        self.midi_behavior_modes = ["Jump To Value", "Pick Up"]
        GObject.GObject.__init__(self)
        self.topwindow = topwindow
        self.meter_scales = meter_scales
        self.slider_scales = slider_scales
        self.set_default_preferences()
        if confdir:
            os.makedirs(confdir, exist_ok=True)
            self.config = configparser.ConfigParser()
            self.path = os.path.join(confdir, "preferences.ini")
            if os.path.isfile(self.path):
                self.read_preferences()
            else:
                self.write_preferences()
        else:
            log.warning(
                _("Cannot load platformdirs. ")
                + _("Your preferences will not be preserved across jack_mixer invocations.")
            )

    def set_default_preferences(self):
        self.confirm_quit = False
        self.default_meter_scale = self.meter_scales[0]
        self.default_project_path = None
        self.default_slider_scale = self.slider_scales[0]
        self.language = None
        self.midi_behavior_mode = 0
        self.use_custom_widgets = False
        self.vumeter_color = "#ccb300"
        self.vumeter_color_scheme = "default"
        self.auto_reset_peak_meters = False
        self.auto_reset_peak_meters_time_seconds = 2.0
        self.meter_refresh_period_milliseconds = 33

    def read_preferences(self):
        self.config.read(self.path)
        self.confirm_quit = self.config.getboolean(
            "Preferences", "confirm_quit", fallback=self.confirm_quit
        )

        scale_id = self.config["Preferences"]["default_meter_scale"]
        self.default_meter_scale = lookup_scale(self.meter_scales, scale_id)
        if not self.default_meter_scale:
            self.default_meter_scale = self.meter_scales[0]

        scale_id = self.config["Preferences"]["default_slider_scale"]
        self.default_slider_scale = lookup_scale(self.slider_scales, scale_id)
        if not self.default_slider_scale:
            self.default_slider_scale = self.slider_scales[0]

        self.default_project_path = self.config["Preferences"].get("default_project_path")
        self.language = self.config["Preferences"].get("language")

        try:
            self.midi_behavior_mode = self.config.getint(
                "Preferences", "midi_behavior_mode", fallback=self.midi_behavior_mode
            )
        except (TypeError, ValueError):
            # use default value
            pass

        self.use_custom_widgets = self.config.getboolean(
            "Preferences", "use_custom_widgets", fallback=self.use_custom_widgets
        )
        self.vumeter_color = self.config.get(
            "Preferences", "vumeter_color", fallback=self.vumeter_color
        )
        self.vumeter_color_scheme = self.config.get(
            "Preferences", "vumeter_color_scheme", fallback=self.vumeter_color_scheme
        )
        self.auto_reset_peak_meters = self.config.getboolean(
            "Preferences", "auto_reset_peak_meters", fallback=self.auto_reset_peak_meters
        )
        self.auto_reset_peak_meters_time_seconds = self.config.getfloat(
            "Preferences", "auto_reset_peak_meters_time_seconds",
            fallback=self.auto_reset_peak_meters_time_seconds
        )
        self.meter_refresh_period_milliseconds = self.config.getint(
            "Preferences", "meter_refresh_period_milliseconds",
            fallback=self.meter_refresh_period_milliseconds
        )

    def write_preferences(self):
        self.config["Preferences"] = {}
        self.config["Preferences"]["confirm_quit"] = str(self.confirm_quit)
        self.config["Preferences"]["default_meter_scale"] = self.default_meter_scale.scale_id
        self.config["Preferences"]["default_project_path"] = self.default_project_path or ""
        self.config["Preferences"]["default_slider_scale"] = self.default_slider_scale.scale_id
        self.config["Preferences"]["language"] = self.language or ""
        self.config["Preferences"]["midi_behavior_mode"] = str(self.midi_behavior_mode)
        self.config["Preferences"]["use_custom_widgets"] = str(self.use_custom_widgets)
        self.config["Preferences"]["vumeter_color"] = self.vumeter_color
        self.config["Preferences"]["vumeter_color_scheme"] = self.vumeter_color_scheme
        self.config["Preferences"]["auto_reset_peak_meters"] = str(self.auto_reset_peak_meters)
        self.config["Preferences"]["auto_reset_peak_meters_time_seconds"] = \
            str(self.auto_reset_peak_meters_time_seconds)
        self.config["Preferences"]["meter_refresh_period_milliseconds"] = \
            str(self.meter_refresh_period_milliseconds)

        with open(self.path, "w") as configfile:
            self.config.write(configfile)
            configfile.close()

    def _update_setting(self, name, value):
        if value != getattr(self, name):
            setattr(self, name, value)
            if confdir:
                self.write_preferences()
            signal = "{}-changed".format(name.replace("_", "-"))
            self.emit(signal, value)

    def set_confirm_quit(self, confirm_quit):
        self._update_setting("confirm_quit", confirm_quit)

    def set_default_meter_scale(self, scale):
        if scale:
            self._update_setting("default_meter_scale", scale)
        else:
            log.warning(
                _("Ignoring default_meter_scale setting, because '%s' scale is not known."), scale
            )

    def set_default_project_path(self, path):
        self._update_setting("default_project_path", path)

    def set_default_slider_scale(self, scale):
        if scale:
            self._update_setting("default_slider_scale", scale)
        else:
            log.warning(
                _("Ignoring default_slider_scale setting, because '%s' scale is not known."), scale
            )

    def set_language(self, lang):
        self._update_setting("language", lang)

    def set_midi_behavior_mode(self, mode):
        self._update_setting("midi_behavior_mode", int(mode))

    def set_use_custom_widgets(self, use_custom):
        self._update_setting("use_custom_widgets", use_custom)

    def set_vumeter_color(self, color):
        self._update_setting("vumeter_color", color)

    def set_vumeter_color_scheme(self, color_scheme):
        self._update_setting("vumeter_color_scheme", color_scheme)

    def set_auto_reset_peak_meters(self, auto_reset):
        self._update_setting("auto_reset_peak_meters", auto_reset)

    def set_auto_reset_peak_meters_time_seconds(self, time):
        self._update_setting("auto_reset_peak_meters_time_seconds", time)

    def set_meter_refresh_period_milliseconds(self, period):
        self._update_setting("meter_refresh_period_milliseconds", period)

    def get_confirm_quit(self):
        return self.confirm_quit

    def get_default_meter_scale(self):
        return self.default_meter_scale

    def get_default_project_path(self):
        if self.default_project_path:
            return os.path.expanduser(self.default_project_path)
        elif datadir:
            os.makedirs(datadir, exist_ok=True)
            return datadir

    def get_default_slider_scale(self):
        return self.default_slider_scale

    def get_language(self):
        return self.language

    def get_midi_behavior_mode(self):
        return self.midi_behavior_mode

    def get_use_custom_widgets(self):
        return self.use_custom_widgets

    def get_vumeter_color(self):
        return self.vumeter_color

    def get_vumeter_color_scheme(self):
        return self.vumeter_color_scheme

    def get_auto_reset_peak_meters(self):
        return self.auto_reset_peak_meters

    def get_auto_reset_peak_meters_time_seconds(self):
        return self.auto_reset_peak_meters_time_seconds

    def get_meter_refresh_period_milliseconds(self):
        return self.meter_refresh_period_milliseconds

    def emit_midi_behavior_mode(self):
        self.emit("midi-behavior-mode-changed", self.midi_behavior_mode)

    @classmethod
    def serialization_name(cls):
        return "gui_factory"

    def serialize(self, object_backend):
        object_backend.add_property("confirm-quit", str(self.get_confirm_quit()))
        object_backend.add_property("default_meter_scale", self.get_default_meter_scale().scale_id)
        # serialize the value, even if it's empty, not the default fallback directories
        object_backend.add_property("default_project_path", self.default_project_path or "")
        object_backend.add_property(
            "default_slider_scale", self.get_default_slider_scale().scale_id
        )
        object_backend.add_property("midi_behavior_mode", str(self.get_midi_behavior_mode()))
        object_backend.add_property("use_custom_widgets", str(self.get_use_custom_widgets()))
        object_backend.add_property("vumeter_color", self.get_vumeter_color())
        object_backend.add_property("vumeter_color_scheme", self.get_vumeter_color_scheme())
        object_backend.add_property(
            "auto_reset_peak_meters", str(self.get_auto_reset_peak_meters())
        )
        object_backend.add_property(
            "auto_reset_peak_meters_time_seconds", str(
                self.get_auto_reset_peak_meters_time_seconds()
            )
        )
        object_backend.add_property(
            "meter_refresh_period_milliseconds", str(
                self.get_meter_refresh_period_milliseconds()
            )
        )

    def unserialize_property(self, name, value):
        if name == "confirm_quit":
            self.set_confirm_quit(value == "True")
            return True
        elif name == "default_meter_scale":
            self.set_default_meter_scale(lookup_scale(self.meter_scales, value))
            return True
        elif name == "default_project_path":
            self.set_default_project_path(value or None)
            return True
        elif name == "default_slider_scale":
            self.set_default_slider_scale(lookup_scale(self.slider_scales, value))
            return True
        elif name == "midi_behavior_mode":
            self.set_midi_behavior_mode(int(value))
            return True
        elif name == "use_custom_widgets":
            self.set_use_custom_widgets(value == "True")
            return True
        elif name == "vumeter_color":
            self.set_vumeter_color(value)
            return True
        elif name == "vumeter_color_scheme":
            self.set_vumeter_color_scheme(value)
            return True
        elif name == "auto_reset_peak_meters":
            self.set_auto_reset_peak_meters(value)
            return True
        elif name == "auto_reset_peak_meters_time_seconds":
            self.set_auto_reset_peak_meters_time_seconds(float(value))
            return True
        elif name == "meter_refresh_period_milliseconds":
            self.set_meter_refresh_period_milliseconds(int(value))
        return False


GObject.signal_new(
    "confirm-quit-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [bool],
)
GObject.signal_new(
    "default-meter-scale-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [GObject.TYPE_PYOBJECT],
)
GObject.signal_new(
    "default-project-path-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [str],
)
GObject.signal_new(
    "default-slider-scale-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [GObject.TYPE_PYOBJECT],
)
GObject.signal_new(
    "language-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [str],
)
GObject.signal_new(
    "midi-behavior-mode-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [int],
)
GObject.signal_new(
    "use-custom-widgets-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [bool],
)
GObject.signal_new(
    "vumeter-color-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [str],
)
GObject.signal_new(
    "vumeter-color-scheme-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [str],
)
GObject.signal_new(
    "auto-reset-peak-meters-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [bool],
)
GObject.signal_new(
    "auto-reset-peak-meters-time-seconds-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [float],
)
GObject.signal_new(
    "meter-refresh-period-milliseconds-changed",
    Factory,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [int],
)
