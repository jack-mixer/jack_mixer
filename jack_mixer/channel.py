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

import gi  # noqa: F401
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Pango

from . import abspeak
from . import meter
from . import slider
from .serialization import SerializedObject
from .styling import set_background_color, random_color


log = logging.getLogger(__name__)
BUTTON_PADDING = 1


class Channel(Gtk.Box, SerializedObject):
    """Widget with slider and meter used as base class for more specific
    channel widgets"""

    num_instances = 0

    def __init__(self, app, name, stereo=True, direct_output=True, initial_vol=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.app = app
        self.mixer = app.mixer
        self.channel = None
        self.gui_factory = app.gui_factory
        self._channel_name = name
        self.stereo = stereo
        self.initial_vol = initial_vol
        self.meter_scale = self.gui_factory.get_default_meter_scale()
        self.slider_scale = self.gui_factory.get_default_slider_scale()
        self.slider_adjustment = slider.AdjustmentdBFS(self.slider_scale, 0.0, 0.02)
        self.balance_adjustment = slider.BalanceAdjustment()
        self.wants_direct_output = direct_output
        self.post_fader_output_channel = None
        self.future_out_mute = None
        self.future_volume_midi_cc = None
        self.future_balance_midi_cc = None
        self.future_mute_midi_cc = None
        self.future_solo_midi_cc = None
        self.css_name = "css_name_%d" % Channel.num_instances
        self.label_name = None
        self.wide = True
        self.meter_prefader = False
        self.prefader_button = None
        self.label_chars_wide = 12
        self.label_chars_narrow = 7
        self.channel_properties_dialog = None
        self.monitor_button = None
        Channel.num_instances += 1

    # ---------------------------------------------------------------------------------------------
    # Properties

    @property
    def channel_name(self):
        return self._channel_name

    @channel_name.setter
    def channel_name(self, name):
        self.app.on_channel_rename(self._channel_name, name)
        self._channel_name = name
        if self.label_name:
            self.label_name.set_text(name)
            if len(name) > (self.label_chars_wide if self.wide else self.label_chars_narrow):
                self.label_name.set_tooltip_text(name)
        if self.channel:
            self.channel.name = name
        if self.post_fader_output_channel:
            self.post_fader_output_channel.name = "{channel_name} Out".format(channel_name=name)

    # ---------------------------------------------------------------------------------------------
    # UI creation and (de-)initialization

    def create_balance_widget(self):
        parent = None
        if self.balance:
            parent = self.balance.get_parent()
            self.balance.destroy()

        self.balance = slider.BalanceSlider(self.balance_adjustment, (20, 20), (0, 100))

        if parent:
            parent.pack_end(self.balance, False, True, 0)

        self.balance.show()

    def create_buttons(self):
        # Mute, Solo and Monitor buttons
        self.hbox_mutesolo = Gtk.Box(False, 0, orientation=Gtk.Orientation.HORIZONTAL)

        self.mute = Gtk.ToggleButton()
        self.mute.set_label(_("M"))
        self.mute.get_style_context().add_class("mute")
        self.mute.set_active(self.channel.out_mute)
        self.mute.connect("toggled", self.on_mute_toggled)
        self.mute.connect("button-press-event", self.on_mute_button_pressed)
        self.hbox_mutesolo.pack_start(self.mute, True, True, 0)

        self.pack_start(self.hbox_mutesolo, False, False, 0)

        self.monitor_button = Gtk.ToggleButton(_("MON"))
        self.monitor_button.get_style_context().add_class("monitor")
        self.monitor_button.connect("toggled", self.on_monitor_button_toggled)
        self.pack_start(self.monitor_button, False, False, 0)

    def create_fader(self):
        # HBox for fader and meter
        self.vbox_fader = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox_fader.get_style_context().add_class("vbox_fader")

        self.prefader_button = pre = Gtk.ToggleButton(_("PRE"))
        pre.get_style_context().add_class("prefader_meter")
        pre.set_tooltip_text(_("Pre-fader (on) / Post-fader (off) metering"))
        pre.connect("toggled", self.on_prefader_metering_toggled)
        pre.set_active(self.meter_prefader)

        self.hbox_readouts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.hbox_readouts.set_homogeneous(True)
        self.hbox_readouts.pack_start(self.volume_digits, False, True, 0)
        self.hbox_readouts.pack_start(self.abspeak, False, True, 0)
        self.vbox_fader.pack_start(self.hbox_readouts, False, False, 0)

        self.hbox_fader = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.hbox_fader.pack_start(self.slider, True, False, 0)
        self.vbox_meter = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox_meter.pack_start(self.meter, True, True, 0)
        self.vbox_meter.pack_start(self.prefader_button, False, True, 0)
        self.hbox_fader.pack_start(self.vbox_meter, True, True, 0)
        self.event_box_fader = Gtk.EventBox()
        self.event_box_fader.set_events(Gdk.EventMask.SCROLL_MASK)
        self.event_box_fader.connect("scroll-event", self.on_scroll)
        self.event_box_fader.add(self.hbox_fader)
        self.vbox_fader.pack_start(self.event_box_fader, True, True, 0)
        self.vbox_fader.pack_end(self.balance, False, True, 0)

        self.pack_start(self.vbox_fader, True, True, 0)

    def create_slider_widget(self):
        parent = None
        if self.slider:
            parent = self.slider.get_parent()
            self.slider.destroy()

        if self.gui_factory.use_custom_widgets:
            self.slider = slider.CustomSliderWidget(self.slider_adjustment)
        else:
            self.slider = slider.VolumeSlider(self.slider_adjustment)

        if parent:
            parent.pack_start(self.slider, True, False, 0)
            parent.reorder_child(self.slider, 0)

        self.slider.widen(self.wide)
        self.slider.show()

    def realize(self):
        log.debug('Realizing channel "%s".', self.channel_name)
        if self.future_out_mute is not None:
            self.channel.out_mute = self.future_out_mute

        # Widgets
        # Channel strip label
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pack_start(self.vbox, False, True, 0)
        self.label_name = Gtk.Label()
        self.label_name.get_style_context().add_class("top_label")
        self.label_name.set_text(self.channel_name)
        self.label_name.set_max_width_chars(
            self.label_chars_wide if self.wide else self.label_chars_narrow
        )
        self.label_name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.label_name_event_box = Gtk.EventBox()
        self.label_name_event_box.connect("button-press-event", self.on_label_mouse)
        self.label_name_event_box.add(self.label_name)

        # Volume slider
        self.slider = None
        self.create_slider_widget()
        # Balance slider
        self.balance = None
        self.create_balance_widget()

        # Volume entry
        self.volume_digits = Gtk.Entry()
        self.volume_digits.set_has_frame(False)
        self.volume_digits.set_width_chars(5)
        self.volume_digits.set_property("xalign", 0.5)
        self.volume_digits.connect("key-press-event", self.on_volume_digits_key_pressed)
        self.volume_digits.connect("focus-out-event", self.on_volume_digits_focus_out)
        self.volume_digits.get_style_context().add_class("readout")

        # Peak level label
        self.abspeak = abspeak.AbspeakWidget(self.app)
        self.abspeak.connect("reset", self.on_abspeak_reset)
        self.abspeak.connect("volume-adjust", self.on_abspeak_adjust)
        self.abspeak.get_style_context().add_class("readout")

        # Level meter
        if self.stereo:
            self.meter = meter.StereoMeterWidget(self.meter_scale)
        else:
            self.meter = meter.MonoMeterWidget(self.meter_scale)

        self.on_vumeter_color_changed(self.gui_factory)

        # If channel is created via UI, the initial volume is passed to the
        # init method and saved in the `initial_vol` attribute.
        # If channel is created from a project XML file, no initial volume is
        # passsed to init, `initial_vol` will be `None` and the volume slider
        # adjustment is set via the `unserialize_property` method.
        # In both cases the engine volume (and balance) will be synchronized
        # with the slider adjustment by the overwritten `realize` method in
        # Channel sub-classes.
        if self.initial_vol is not None:
            if self.initial_vol == -1:
                self.slider_adjustment.set_value(0)
            else:
                self.slider_adjustment.set_value_db(self.initial_vol)

        self.slider_adjustment.connect("volume-changed", self.on_volume_changed)
        self.slider_adjustment.connect(
            "volume-changed-from-midi", self.on_volume_changed_from_midi
        )
        self.balance_adjustment.connect("balance-changed", self.on_balance_changed)

        self.gui_factory.connect(
            "default-meter-scale-changed", self.on_default_meter_scale_changed
        )
        self.gui_factory.connect(
            "default-slider-scale-changed", self.on_default_slider_scale_changed
        )
        self.gui_factory.connect("vumeter-color-changed", self.on_vumeter_color_changed)
        self.gui_factory.connect("vumeter-color-scheme-changed", self.on_vumeter_color_changed)
        self.gui_factory.connect("use-custom-widgets-changed", self.on_custom_widgets_changed)

        self.connect("key-press-event", self.on_key_pressed)
        self.connect("scroll-event", self.on_scroll)

        entries = [Gtk.TargetEntry.new(self.__class__.__name__, Gtk.TargetFlags.SAME_APP, 0)]
        self.label_name_event_box.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK, entries, Gdk.DragAction.MOVE
        )
        self.label_name_event_box.connect("drag-data-get", self.on_drag_data_get)
        self.drag_dest_set(Gtk.DestDefaults.ALL, entries, Gdk.DragAction.MOVE)
        self.connect_after("drag-data-received", self.on_drag_data_received)

        self.vbox.pack_start(self.label_name_event_box, True, True, 0)

    def unrealize(self):
        log.debug('Unrealizing channel "%s".', self.channel_name)

    # ---------------------------------------------------------------------------------------------
    # Signal/event handlers

    def on_label_mouse(self, widget, event):
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            if event.button == 1:
                self.on_channel_properties()
            return True
        elif (
            event.state & Gdk.ModifierType.CONTROL_MASK
            and event.type == Gdk.EventType.BUTTON_PRESS
            and event.button == 1
        ):
            if self.wide:
                self.narrow()
            else:
                self.widen()
            return True

    def on_channel_properties(self):
        if not self.channel_properties_dialog:
            self.channel_properties_dialog = self.properties_dialog_class(self.app, self)
        self.channel_properties_dialog.fill_and_show()

    def on_default_meter_scale_changed(self, gui_factory, scale):
        log.debug("Default meter scale change detected.")
        self.meter.set_scale(scale)
        self.meter_scale = scale

    def on_default_slider_scale_changed(self, gui_factory, scale):
        log.debug("Default slider scale change detected.")
        self.slider_scale = scale
        self.slider_adjustment.set_scale(scale)
        if self.channel:
            self.channel.midi_scale = self.slider_scale.scale

    def on_vumeter_color_changed(self, gui_factory, *args):
        color = gui_factory.get_vumeter_color()
        color_scheme = gui_factory.get_vumeter_color_scheme()
        if color_scheme != "solid":
            self.meter.set_color(None)
        else:
            self.meter.set_color(Gdk.color_parse(color))

    def on_custom_widgets_changed(self, gui_factory, value):
        self.create_slider_widget()
        # balance slider has no custom variant, no need to re-create it.

    def on_prefader_metering_toggled(self, button):
        self.use_prefader_metering(button.get_active())

    def on_abspeak_adjust(self, abspeak, adjust):
        log.debug("abspeak adjust %f", adjust)
        self.slider_adjustment.set_value_db(self.slider_adjustment.get_value_db() + adjust)
        if self.meter_prefader:
            self.channel.abspeak_prefader = None
        else:
            self.channel.abspeak_postfader = None
        # We want to update gui even if actual decibels have not changed (scale wrap for example)
        # self.update_volume(False)

    def on_abspeak_reset(self, abspeak):
        log.debug("abspeak reset")
        if self.meter_prefader:
            self.channel.abspeak_prefader = None
        else:
            self.channel.abspeak_postfader = None

    def on_volume_digits_key_pressed(self, widget, event):
        if event.keyval == Gdk.KEY_Return or event.keyval == Gdk.KEY_KP_Enter:
            db_text = self.volume_digits.get_text()
            try:
                db = float(db_text)
                log.debug("Volume digits confirmation '%f dBFS'.", db)
            except ValueError:
                log.debug("Volume digits confirmation ignore, reset to current.")
                self.update_volume(False)
                return
            self.slider_adjustment.set_value_db(db)
            # self.grab_focus()
            # We want to update gui even if actual decibels have not changed
            # (scale wrap for example)
            # self.update_volume(False)

    def on_volume_digits_focus_out(self, widget, event):
        log.debug("Volume digits focus out detected.")
        self.update_volume(False)

    def on_scroll(self, widget, event):
        if event.direction == Gdk.ScrollDirection.DOWN:
            self.slider_adjustment.step_down()
        elif event.direction == Gdk.ScrollDirection.UP:
            self.slider_adjustment.step_up()
        return True

    def on_volume_changed(self, adjustment):
        self.update_volume(True)

    def on_volume_changed_from_midi(self, adjustment):
        self.update_volume(True, from_midi=True)

    def on_balance_changed(self, adjustment):
        self.update_balance(True)

    def on_key_pressed(self, widget, event):
        if event.keyval == Gdk.KEY_Up:
            log.debug(self.channel_name + " Up")
            self.slider_adjustment.step_up()
            return True
        elif event.keyval == Gdk.KEY_Down:
            log.debug(self.channel_name + " Down")
            self.slider_adjustment.step_down()
            return True

        return False

    def on_drag_data_get(self, widget, drag_context, data, info, time):
        data.set(data.get_target(), 8, self.channel_name.encode("utf-8"))

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        pass

    def on_midi_event_received(self, *args):
        self.slider_adjustment.set_value_db(self.channel.volume, from_midi=True)
        self.balance_adjustment.set_balance(self.channel.balance, from_midi=True)

    def on_mute_toggled(self, button):
        self.channel.out_mute = self.mute.get_active()

    def on_mute_button_pressed(self, button, event, *args):
        # should be overwritten by sub-class
        pass

    def on_monitor_button_toggled(self, button):
        if button.get_active():
            for channel in self.app.channels + self.app.output_channels:
                if channel is not self and channel.monitor_button.get_active():
                    channel.monitor_button.handler_block_by_func(channel.on_monitor_button_toggled)
                    channel.monitor_button.set_active(False)
                    channel.monitor_button.handler_unblock_by_func(
                        channel.on_monitor_button_toggled
                    )
            self.app.monitored_channel = self
        else:
            if self.app.monitored_channel is self:
                self.app.monitored_channel = None

    def assign_midi_ccs(self, volume_cc, balance_cc, mute_cc, solo_cc=None):
        try:
            if volume_cc != -1:
                self.channel.volume_midi_cc = volume_cc
            else:
                volume_cc = self.channel.autoset_volume_midi_cc()

            log.debug("Channel '%s' volume assigned to CC #%s.", self.channel.name, volume_cc)
        except Exception as exc:
            log.error("Channel '%s' volume CC assignment failed: %s", self.channel.name, exc)

        try:
            if balance_cc != -1:
                self.channel.balance_midi_cc = balance_cc
            else:
                balance_cc = self.channel.autoset_balance_midi_cc()

            log.debug("Channel '%s' balance assigned to CC #%s.", self.channel.name, balance_cc)
        except Exception as exc:
            log.error("Channel '%s' balance CC assignment failed: %s", self.channel.name, exc)

        try:
            if mute_cc != -1:
                self.channel.mute_midi_cc = mute_cc
            else:
                mute_cc = self.channel.autoset_mute_midi_cc()

            log.debug("Channel '%s' mute assigned to CC #%s.", self.channel.name, mute_cc)
        except Exception as exc:
            log.error("Channel '%s' mute CC assignment failed: %s", self.channel.name, exc)

        if solo_cc is not None:
            try:
                if solo_cc != -1:
                    self.channel.solo_midi_cc = solo_cc
                else:
                    solo_cc = self.channel.autoset_solo_midi_cc()

                log.debug("Channel '%s' solo assigned to CC #%s.", self.channel.name, solo_cc)
            except Exception as exc:
                log.error("Channel '%s' solo CC assignment failed: %s", self.channel.name, exc)

    # ---------------------------------------------------------------------------------------------
    # Channel operations

    def set_monitored(self):
        if self.channel:
            self.app.set_monitored_channel(self)
        self.monitor_button.set_active(True)

    def set_color(self, color):
        self.color = color
        set_background_color(self.label_name_event_box, self.css_name, self.color)

    def widen(self, flag=True):
        self.wide = flag
        ctx = self.label_name.get_style_context()

        if flag:
            ctx.remove_class("narrow")
            ctx.add_class("wide")
        else:
            ctx.remove_class("wide")
            ctx.add_class("narrow")

        label = self.label_name.get_label()
        label_width = self.label_chars_wide if flag else self.label_chars_narrow
        self.label_name.set_max_width_chars(label_width)

        if len(label) > label_width:
            self.label_name.set_tooltip_text(label)

        self.slider.widen(flag)
        self.meter.widen(flag)
        self.hbox_readouts.set_orientation(
            Gtk.Orientation.HORIZONTAL if flag else Gtk.Orientation.VERTICAL
        )

    def narrow(self):
        self.widen(False)

    def use_prefader_metering(self, flag=True):
        self.meter_prefader = flag
        self.prefader_button.set_active(flag)

        if (self.meter.kmetering):
            # Reset the kmeter rms
            self.channel.kmeter_reset()

    def read_meter(self):
        if not self.channel:
            return

        if self.stereo:

            if self.meter.kmetering:
                if self.meter_prefader:
                    self.meter.set_values_kmeter(*self.channel.kmeter_prefader)
                else:
                    self.meter.set_values_kmeter(*self.channel.kmeter_postfader)
            else:
                if self.meter_prefader:
                    self.meter.set_values(*self.channel.meter_prefader)
                else:
                    self.meter.set_values(*self.channel.meter_postfader)

        else:
            if self.meter.kmetering:
                if self.meter_prefader:
                    self.meter.set_value_kmeter(*self.channel.kmeter_prefader)
                else:
                    self.meter.set_value_kmeter(*self.channel.kmeter_postfader)
            else:
                if self.meter_prefader:
                    self.meter.set_value(*self.channel.meter_prefader)
                else:
                    self.meter.set_value(*self.channel.meter_postfader)

        if self.meter_prefader:
            self.abspeak.set_peak(self.channel.abspeak_prefader)
        else:
            self.abspeak.set_peak(self.channel.abspeak_postfader)

    def update_balance(self, update_engine, from_midi=False):
        balance = self.balance_adjustment.get_value()
        log.debug("%s balance: %f", self.channel_name, balance)

        if update_engine:
            if not from_midi:
                self.channel.balance = balance
                self.channel.set_midi_cc_balance_picked_up(False)
            self.app.update_monitor(self)

    def update_volume(self, update_engine, from_midi=False):
        db = self.slider_adjustment.get_value_db()
        log.debug("%s volume: %.2f dB", self.channel_name, db)

        # TODO l10n
        db_text = "%.2f" % db
        self.volume_digits.set_text(db_text)

        if update_engine:
            if not from_midi:
                self.channel.volume = db
                self.channel.set_midi_cc_volume_picked_up(False)
            self.app.update_monitor(self)

    # ---------------------------------------------------------------------------------------------
    # Channel (de-)serialization

    def serialize(self, object_backend):
        object_backend.add_property("volume", "%f" % self.slider_adjustment.get_value_db())
        object_backend.add_property("balance", "%f" % self.balance_adjustment.get_value())
        object_backend.add_property("wide", "%s" % str(self.wide))
        object_backend.add_property("meter_prefader", "%s" % str(self.meter_prefader))

        if hasattr(self.channel, "out_mute"):
            object_backend.add_property("out_mute", str(self.channel.out_mute))
        if self.channel.volume_midi_cc != -1:
            object_backend.add_property("volume_midi_cc", str(self.channel.volume_midi_cc))
        if self.channel.balance_midi_cc != -1:
            object_backend.add_property("balance_midi_cc", str(self.channel.balance_midi_cc))
        if self.channel.mute_midi_cc != -1:
            object_backend.add_property("mute_midi_cc", str(self.channel.mute_midi_cc))
        if self.channel.solo_midi_cc != -1:
            object_backend.add_property("solo_midi_cc", str(self.channel.solo_midi_cc))

    def unserialize_property(self, name, value):
        if name == "volume":
            self.slider_adjustment.set_value_db(float(value))
            return True
        elif name == "balance":
            self.balance_adjustment.set_value(float(value))
            return True
        elif name == "out_mute":
            self.future_out_mute = value == "True"
            return True
        elif name == "meter_prefader":
            self.meter_prefader = (value == "True")
            return True
        elif name == "volume_midi_cc":

            self.future_volume_midi_cc = int(value)
            return True
        elif name == "balance_midi_cc":
            self.future_balance_midi_cc = int(value)
            return True
        elif name == "mute_midi_cc":
            self.future_mute_midi_cc = int(value)
            return True
        elif name == "solo_midi_cc":
            self.future_solo_midi_cc = int(value)
            return True
        elif name == "wide":
            self.wide = value == "True"
            return True

        return False


class InputChannel(Channel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.properties_dialog_class = ChannelPropertiesDialog

    def create_buttons(self):
        super().create_buttons()
        self.solo = Gtk.ToggleButton()
        self.solo.set_label(_("S"))
        self.solo.get_style_context().add_class("solo")
        self.solo.set_active(self.channel.solo)
        self.solo.connect("toggled", self.on_solo_toggled)
        self.solo.connect("button-press-event", self.on_solo_button_pressed)
        self.hbox_mutesolo.pack_start(self.solo, True, True, 0)

    def realize(self):
        self.channel = self.mixer.add_channel(self.channel_name, self.stereo)

        if self.channel is None:
            raise Exception(_("Cannot create a channel"))

        super().realize()

        if self.future_volume_midi_cc is not None:
            self.channel.volume_midi_cc = self.future_volume_midi_cc
        if self.future_balance_midi_cc is not None:
            self.channel.balance_midi_cc = self.future_balance_midi_cc
        if self.future_mute_midi_cc is not None:
            self.channel.mute_midi_cc = self.future_mute_midi_cc
        if self.future_solo_midi_cc is not None:
            self.channel.solo_midi_cc = self.future_solo_midi_cc
        if self.app._init_solo_channels and self.channel_name in self.app._init_solo_channels:
            self.channel.solo = True

        self.channel.midi_scale = self.slider_scale.scale

        self.update_volume(update_engine=True)
        self.update_balance(update_engine=True)

        self.create_fader()

        # Widgets
        self.create_buttons()

        if not self.wide:
            self.narrow()

    def unrealize(self):
        super().unrealize()
        if self.post_fader_output_channel:
            self.post_fader_output_channel.remove()
            self.post_fader_output_channel = None
        self.channel.remove()
        self.channel = None

    def narrow(self):
        super().narrow()
        for cg in self.get_control_groups():
            cg.narrow()

    def widen(self, flag=True):
        super().widen(flag)
        for cg in self.get_control_groups():
            cg.widen()

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        source_name = data.get_data().decode("utf-8")
        if source_name == self.channel_name:
            return
        self.emit("input-channel-order-changed", source_name, self.channel_name)

    def add_control_group(self, channel):
        control_group = ControlGroup(channel, self)
        control_group.show_all()
        self.vbox.pack_start(control_group, True, True, 0)
        return control_group

    def remove_control_group(self, channel):
        ctlgroup = self.get_control_group(channel)
        self.vbox.remove(ctlgroup)

    def update_control_group(self, channel):
        for control_group in self.vbox.get_children():
            if isinstance(control_group, ControlGroup):
                if control_group.output_channel is channel:
                    control_group.update()

    def get_control_group(self, channel):
        for control_group in self.get_control_groups():
            if control_group.output_channel is channel:
                return control_group
        return None

    def get_control_groups(self):
        ctlgroups = []
        for c in self.vbox.get_children():
            if isinstance(c, ControlGroup):
                ctlgroups.append(c)
        return ctlgroups

    def midi_events_check(self):
        if self.channel is not None and self.channel.midi_in_got_events:
            self.mute.set_active(self.channel.out_mute)
            self.solo.set_active(self.channel.solo)
            super().on_midi_event_received()

    def on_mute_button_pressed(self, button, event, *args):
        if event.button == 1 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrlr+left-click: exclusive (between input channels) mute
            for channel in self.app.channels:
                if channel is not self:
                    channel.mute.set_active(False)
            return button.get_active()
        elif event.button == 3:
            # Right-click on the mute button: act on all output channels
            if button.get_active():  # was muted
                button.set_active(False)
                if hasattr(button, "touched_channels"):
                    touched_channels = button.touched_channels
                    for chan in touched_channels:
                        ctlgroup = self.get_control_group(chan)
                        ctlgroup.mute.set_active(False)
                    del button.touched_channels
            else:  # was not muted
                button.set_active(True)
                touched_channels = []
                for chan in self.app.output_channels:
                    ctlgroup = self.get_control_group(chan)
                    if not ctlgroup.mute.get_active():
                        ctlgroup.mute.set_active(True)
                        touched_channels.append(chan)
                button.touched_channels = touched_channels
            return True
        return False

    def on_solo_toggled(self, button):
        self.channel.solo = self.solo.get_active()

    def on_solo_button_pressed(self, button, event, *args):
        if event.button == 1 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrlr+left-click: exclusive solo
            for channel in self.app.channels:
                if channel is not self:
                    channel.solo.set_active(False)
            return button.get_active()
        elif event.button == 3:
            # Right click on the solo button: act on all output channels
            if button.get_active():  # was soloed
                button.set_active(False)
                if hasattr(button, "touched_channels"):
                    touched_channels = button.touched_channels
                    for chan in touched_channels:
                        ctlgroup = self.get_control_group(chan)
                        ctlgroup.solo.set_active(False)
                    del button.touched_channels
            else:  # was not soloed
                button.set_active(True)
                touched_channels = []
                for chan in self.app.output_channels:
                    ctlgroup = self.get_control_group(chan)
                    if not ctlgroup.solo.get_active():
                        ctlgroup.solo.set_active(True)
                        touched_channels.append(chan)
                button.touched_channels = touched_channels
            return True
        return False

    @classmethod
    def serialization_name(cls):
        return "input_channel"

    def serialize(self, object_backend):
        object_backend.add_property("name", self.channel_name)
        if self.stereo:
            object_backend.add_property("type", "stereo")
        else:
            object_backend.add_property("type", "mono")
        object_backend.add_property("direct_output", "%s" % str(self.wants_direct_output))
        super().serialize(object_backend)

    def unserialize_property(self, name, value):
        if name == "name":
            self.channel_name = str(value)
            return True
        elif name == "type":
            if value == "stereo":
                self.stereo = True
                return True
            elif value == "mono":
                self.stereo = False
                return True
        elif name == "direct_output":
            self.wants_direct_output = value == "True"
            return True

        return super().unserialize_property(name, value)


class OutputChannel(Channel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.properties_dialog_class = OutputChannelPropertiesDialog
        self._display_solo_buttons = False
        self._init_muted_channels = None
        self._init_solo_channels = None
        self._init_prefader_channels = None
        self._color = Gdk.RGBA()

    @property
    def display_solo_buttons(self):
        return self._display_solo_buttons

    @display_solo_buttons.setter
    def display_solo_buttons(self, value):
        self._display_solo_buttons = value
        # notifying control groups
        for inputchannel in self.app.channels:
            inputchannel.update_control_group(self)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        if isinstance(value, Gdk.RGBA):
            self._color = value
        else:
            c = Gdk.RGBA()
            c.parse(value)
            self._color = c

    def realize(self):
        self.channel = self.mixer.add_output_channel(self.channel_name, self.stereo)

        if self.channel is None:
            raise Exception(_("Cannot create an output channel"))

        super().realize()

        if self.future_volume_midi_cc is not None:
            self.channel.volume_midi_cc = self.future_volume_midi_cc
        if self.future_balance_midi_cc is not None:
            self.channel.balance_midi_cc = self.future_balance_midi_cc
        if self.future_mute_midi_cc is not None:
            self.channel.mute_midi_cc = self.future_mute_midi_cc

        self.channel.midi_scale = self.slider_scale.scale

        self.update_volume(update_engine=True)
        self.update_balance(update_engine=True)

        set_background_color(self.label_name_event_box, self.css_name, self.color)

        self.create_fader()

        # Widgets

        self.create_buttons()

        # add control groups to the input channels, and initialize them
        # appropriately
        for input_channel in self.app.channels:
            ctlgroup = input_channel.add_control_group(self)
            name = input_channel.channel.name
            if self._init_muted_channels and name in self._init_muted_channels:
                ctlgroup.mute.set_active(True)
            if self._init_solo_channels and name in self._init_solo_channels:
                ctlgroup.solo.set_active(True)
            if self._init_prefader_channels and name in self._init_prefader_channels:
                ctlgroup.prefader.set_active(True)
            if not input_channel.wide:
                ctlgroup.narrow()

        self._init_muted_channels = None
        self._init_solo_channels = None
        self._init_prefader_channels = None

        if not self.wide:
            self.narrow()

    def unrealize(self):
        # remove control groups from input channels
        for input_channel in self.app.channels:
            input_channel.remove_control_group(self)
        # then remove itself
        super().unrealize()
        self.channel.remove()
        self.channel = None

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        source_name = data.get_data().decode("utf-8")
        if source_name == self.channel_name:
            return
        self.emit("output-channel-order-changed", source_name, self.channel_name)

    def on_mute_button_pressed(self, button, event, *args):
        if event.button == 1 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrlr+left-click: exclusive (between output channels) mute
            for channel in self.app.output_channels:
                if channel is not self:
                    channel.mute.set_active(False)
            return button.get_active()

    def midi_events_check(self):
        if self.channel is not None and self.channel.midi_in_got_events:
            self.mute.set_active(self.channel.out_mute)
            super().on_midi_event_received()

    @classmethod
    def serialization_name(cls):
        return "output_channel"

    def serialize(self, object_backend):
        object_backend.add_property("name", self.channel_name)
        if self.stereo:
            object_backend.add_property("type", "stereo")
        else:
            object_backend.add_property("type", "mono")
        if self.display_solo_buttons:
            object_backend.add_property("solo_buttons", "true")
        muted_channels = []
        solo_channels = []
        prefader_in_channels = []
        for input_channel in self.app.channels:
            if self.channel.is_muted(input_channel.channel):
                muted_channels.append(input_channel)
            if self.channel.is_solo(input_channel.channel):
                solo_channels.append(input_channel)
            if self.channel.is_in_prefader(input_channel.channel):
                prefader_in_channels.append(input_channel)
        if muted_channels:
            object_backend.add_property(
                "muted_channels", "|".join([x.channel.name for x in muted_channels])
            )
        if solo_channels:
            object_backend.add_property(
                "solo_channels", "|".join([x.channel.name for x in solo_channels])
            )
        if prefader_in_channels:
            object_backend.add_property(
                "prefader_channels", "|".join([x.channel.name for x in prefader_in_channels])
            )
        object_backend.add_property("color", self.color.to_string())
        super().serialize(object_backend)

    def unserialize_property(self, name, value):
        if name == "name":
            self.channel_name = str(value)
            return True
        elif name == "type":
            if value == "stereo":
                self.stereo = True
                return True
            elif value == "mono":
                self.stereo = False
                return True
        elif name == "solo_buttons":
            if value == "true":
                self.display_solo_buttons = True
                return True
        elif name == "muted_channels":
            self._init_muted_channels = value.split("|")
            return True
        elif name == "solo_channels":
            self._init_solo_channels = value.split("|")
            return True
        elif name == "prefader_channels":
            self._init_prefader_channels = value.split("|")
            return True
        elif name == "color":
            c = Gdk.RGBA()
            c.parse(value)
            self.color = c
            return True

        return super().unserialize_property(name, value)


class ChannelPropertiesDialog(Gtk.Dialog):
    def __init__(self, app, channel=None, title=None):
        if not title:
            if not channel:
                raise ValueError("Either 'title' or 'channel' must be passed.")
            title = _("Channel '{name}' Properties").format(name=channel.channel_name)

        super().__init__(title, app.window)
        self.channel = channel
        self.app = app
        self.mixer = app.mixer
        self.set_default_size(365, -1)

        self.create_ui()

    def fill_and_show(self):
        self.fill_ui()
        self.present()

    def add_buttons(self):
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_button(Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY)
        self.set_default_response(Gtk.ResponseType.APPLY)

        self.connect("response", self.on_response_cb)
        self.connect("delete-event", self.on_response_cb)

    def create_frame(self, label, child, padding=8):
        # need to pass an empty label, otherwise no label widget is created
        frame = Gtk.Frame(label="")
        frame.get_label_widget().set_markup("<b>%s</b>" % label)
        frame.set_border_width(3)
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        alignment = Gtk.Alignment.new(0.5, 0, 1, 1)
        alignment.set_padding(padding, padding, padding, padding)
        frame.add(alignment)
        alignment.add(child)

        return frame

    def create_ui(self):
        self.add_buttons()
        vbox = self.get_content_area()

        self.properties_grid = grid = Gtk.Grid()
        vbox.pack_start(self.create_frame(_("Properties"), grid), True, True, 0)
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_column_homogeneous(True)

        name_label = Gtk.Label.new_with_mnemonic(_("_Name"))
        name_label.set_halign(Gtk.Align.START)
        grid.attach(name_label, 0, 0, 1, 1)
        self.entry_name = Gtk.Entry()
        self.entry_name.set_activates_default(True)
        self.entry_name.connect("changed", self.on_entry_name_changed)
        name_label.set_mnemonic_widget(self.entry_name)
        grid.attach(self.entry_name, 1, 0, 2, 1)

        grid.attach(Gtk.Label(label=_("Mode"), halign=Gtk.Align.START), 0, 1, 1, 1)
        self.mono = Gtk.RadioButton.new_with_mnemonic(None, _("_Mono"))
        self.stereo = Gtk.RadioButton.new_with_mnemonic_from_widget(self.mono, _("_Stereo"))
        grid.attach(self.mono, 1, 1, 1, 1)
        grid.attach(self.stereo, 2, 1, 1, 1)

        grid = Gtk.Grid()
        vbox.pack_start(self.create_frame(_("MIDI Control Changes"), grid), True, True, 0)
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_column_homogeneous(True)

        cc_tooltip = _(
            "{param} MIDI Control Change number " "(0-127, set to -1 to assign next free CC #)"
        )
        volume_label = Gtk.Label.new_with_mnemonic(_("_Volume"))
        volume_label.set_halign(Gtk.Align.START)
        grid.attach(volume_label, 0, 0, 1, 1)
        self.entry_volume_cc = Gtk.SpinButton.new_with_range(-1, 127, 1)
        self.entry_volume_cc.set_tooltip_text(cc_tooltip.format(param=_("Volume")))
        volume_label.set_mnemonic_widget(self.entry_volume_cc)
        grid.attach(self.entry_volume_cc, 1, 0, 1, 1)
        self.button_sense_midi_volume = Gtk.Button(_("Learn"))
        self.button_sense_midi_volume.connect("clicked", self.on_sense_midi_volume_clicked)
        grid.attach(self.button_sense_midi_volume, 2, 0, 1, 1)

        balance_label = Gtk.Label.new_with_mnemonic(_("_Balance"))
        balance_label.set_halign(Gtk.Align.START)
        grid.attach(balance_label, 0, 1, 1, 1)
        self.entry_balance_cc = Gtk.SpinButton.new_with_range(-1, 127, 1)
        self.entry_balance_cc.set_tooltip_text(cc_tooltip.format(param=_("Balance")))
        balance_label.set_mnemonic_widget(self.entry_balance_cc)
        grid.attach(self.entry_balance_cc, 1, 1, 1, 1)
        self.button_sense_midi_balance = Gtk.Button(_("Learn"))
        self.button_sense_midi_balance.connect("clicked", self.on_sense_midi_balance_clicked)
        grid.attach(self.button_sense_midi_balance, 2, 1, 1, 1)

        mute_label = Gtk.Label.new_with_mnemonic(_("M_ute"))
        mute_label.set_halign(Gtk.Align.START)
        grid.attach(mute_label, 0, 2, 1, 1)
        self.entry_mute_cc = Gtk.SpinButton.new_with_range(-1, 127, 1)
        self.entry_mute_cc.set_tooltip_text(cc_tooltip.format(param=_("Mute")))
        mute_label.set_mnemonic_widget(self.entry_mute_cc)
        grid.attach(self.entry_mute_cc, 1, 2, 1, 1)
        self.button_sense_midi_mute = Gtk.Button(_("Learn"))
        self.button_sense_midi_mute.connect("clicked", self.on_sense_midi_mute_clicked)
        grid.attach(self.button_sense_midi_mute, 2, 2, 1, 1)

        if isinstance(self, NewInputChannelDialog) or (
            self.channel and isinstance(self.channel, InputChannel)
        ):
            direct_output_label = Gtk.Label.new_with_mnemonic(_("_Direct Out(s)"))
            direct_output_label.set_halign(Gtk.Align.START)
            self.properties_grid.attach(direct_output_label, 0, 3, 1, 1)
            self.direct_output = Gtk.CheckButton()
            direct_output_label.set_mnemonic_widget(self.direct_output)
            self.direct_output.set_tooltip_text(_("Add direct post-fader output(s) for channel."))
            self.properties_grid.attach(self.direct_output, 1, 3, 1, 1)

        if isinstance(self, NewChannelDialog) or (
            self.channel and isinstance(self.channel, InputChannel)
        ):
            solo_label = Gtk.Label.new_with_mnemonic(_("S_olo"))
            solo_label.set_halign(Gtk.Align.START)
            grid.attach(solo_label, 0, 3, 1, 1)
            self.entry_solo_cc = Gtk.SpinButton.new_with_range(-1, 127, 1)
            self.entry_solo_cc.set_tooltip_text(cc_tooltip.format(param=_("Solo")))
            solo_label.set_mnemonic_widget(self.entry_solo_cc)
            grid.attach(self.entry_solo_cc, 1, 3, 1, 1)
            self.button_sense_midi_solo = Gtk.Button(_("Learn"))
            self.button_sense_midi_solo.connect("clicked", self.on_sense_midi_solo_clicked)
            grid.attach(self.button_sense_midi_solo, 2, 3, 1, 1)

        self.vbox.show_all()

    def fill_ui(self):
        self.entry_name.set_text(self.channel.channel_name)
        if self.channel.channel.is_stereo:
            self.stereo.set_active(True)
        else:
            self.mono.set_active(True)
        self.mono.set_sensitive(False)
        self.stereo.set_sensitive(False)
        self.entry_volume_cc.set_value(self.channel.channel.volume_midi_cc)
        self.entry_balance_cc.set_value(self.channel.channel.balance_midi_cc)
        self.entry_mute_cc.set_value(self.channel.channel.mute_midi_cc)
        if self.channel and isinstance(self.channel, InputChannel):
            self.direct_output.set_active(self.channel.wants_direct_output)
            self.entry_solo_cc.set_value(self.channel.channel.solo_midi_cc)

    def sense_popup_dialog(self, entry):
        window = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
        window.set_destroy_with_parent(True)
        window.set_transient_for(self)
        window.set_decorated(False)
        window.set_modal(True)
        window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        window.set_border_width(10)

        vbox = Gtk.Box(10, orientation=Gtk.Orientation.VERTICAL)
        window.add(vbox)
        window.timeout = 5
        label = Gtk.Label(
            label=_("Please move the MIDI control you want to use for this function.")
        )
        vbox.pack_start(label, True, True, 0)
        timeout_label = Gtk.Label(label=_("This window will close in 5 seconds."))
        vbox.pack_start(timeout_label, True, True, 0)

        def close_sense_timeout(window, entry):
            window.timeout -= 1
            timeout_label.set_text(
                _("This window will close in {seconds} seconds.").format(seconds=window.timeout)
            )
            if window.timeout == 0:
                window.destroy()
                entry.set_value(self.mixer.last_midi_cc)
                return False
            return True

        window.show_all()
        GObject.timeout_add_seconds(1, close_sense_timeout, window, entry)

    def on_sense_midi_volume_clicked(self, *args):
        self.mixer.last_midi_cc = int(self.entry_volume_cc.get_value())
        self.sense_popup_dialog(self.entry_volume_cc)

    def on_sense_midi_balance_clicked(self, *args):
        self.mixer.last_midi_cc = int(self.entry_balance_cc.get_value())
        self.sense_popup_dialog(self.entry_balance_cc)

    def on_sense_midi_mute_clicked(self, *args):
        self.mixer.last_midi_cc = int(self.entry_mute_cc.get_value())
        self.sense_popup_dialog(self.entry_mute_cc)

    def on_sense_midi_solo_clicked(self, *args):
        self.mixer.last_midi_cc = int(self.entry_solo_cc.get_value())
        self.sense_popup_dialog(self.entry_solo_cc)

    def on_response_cb(self, dlg, response_id, *args):
        if response_id == Gtk.ResponseType.APPLY:
            name = self.entry_name.get_text()

            if name != self.channel.channel_name:
                self.channel.channel_name = name

            if self.channel and isinstance(self.channel, InputChannel):
                if self.direct_output.get_active() and not self.channel.post_fader_output_channel:
                    self.channel.wants_direct_output = True
                    self.app.add_direct_output(self.channel)
                elif (
                    not self.direct_output.get_active() and self.channel.post_fader_output_channel
                ):
                    self.channel.wants_direct_output = False
                    self.channel.post_fader_output_channel.remove()
                    self.channel.post_fader_output_channel = None

            for control in ("volume", "balance", "mute", "solo"):
                widget = getattr(self, "entry_{}_cc".format(control), None)
                if widget is not None:
                    value = int(widget.get_value())
                    if value != -1:
                        setattr(self.channel.channel, "{}_midi_cc".format(control), value)

        self.hide()
        return True

    def on_entry_name_changed(self, entry):
        sensitive = False
        if len(entry.get_text()):
            if self.channel and self.channel.channel.name == entry.get_text():
                sensitive = True
            elif entry.get_text() not in [x.channel.name for x in self.app.channels] + [
                x.channel.name for x in self.app.output_channels
            ]:
                sensitive = True
        self.ok_button.set_sensitive(sensitive)


class NewChannelDialog(ChannelPropertiesDialog):
    def create_ui(self):
        super().create_ui()
        self.add_initial_vol_radio()
        self.vbox.show_all()

    def add_buttons(self):
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.ok_button = self.add_button(Gtk.STOCK_ADD, Gtk.ResponseType.OK)
        self.ok_button.set_sensitive(False)
        self.set_default_response(Gtk.ResponseType.OK)

    def add_initial_vol_radio(self):
        grid = self.properties_grid
        grid.attach(Gtk.Label(label=_("Value"), halign=Gtk.Align.START), 0, 2, 1, 1)
        self.minus_inf = Gtk.RadioButton.new_with_mnemonic(None, _("-_Inf"))
        self.zero_dB = Gtk.RadioButton.new_with_mnemonic_from_widget(self.minus_inf, _("_0dB"))
        grid.attach(self.minus_inf, 1, 2, 1, 1)
        grid.attach(self.zero_dB, 2, 2, 1, 1)


class NewInputChannelDialog(NewChannelDialog):
    def __init__(self, app, title=None):
        super().__init__(app, title=title or _("New Input Channel"))

    def fill_ui(self, **values):
        self.entry_name.set_text(values.get("name", ""))
        self.direct_output.set_active(values.get("direct_output", True))
        # don't set MIDI CCs to previously used values, because they
        # would overwrite existing mappings, if accepted.
        self.entry_volume_cc.set_value(-1)
        self.entry_balance_cc.set_value(-1)
        self.entry_mute_cc.set_value(-1)
        self.entry_solo_cc.set_value(-1)
        self.stereo.set_active(values.get("stereo", True))
        self.minus_inf.set_active(values.get("initial_vol", -1) == -1)
        self.entry_name.grab_focus()

    def get_result(self):
        return {
            "name": self.entry_name.get_text(),
            "stereo": self.stereo.get_active(),
            "direct_output": self.direct_output.get_active(),
            "volume_cc": int(self.entry_volume_cc.get_value()),
            "balance_cc": int(self.entry_balance_cc.get_value()),
            "mute_cc": int(self.entry_mute_cc.get_value()),
            "solo_cc": int(self.entry_solo_cc.get_value()),
            "initial_vol": 0 if self.zero_dB.get_active() else -1,
        }


class OutputChannelPropertiesDialog(ChannelPropertiesDialog):
    def create_ui(self):
        super().create_ui()

        grid = self.properties_grid
        color_label = Gtk.Label.new_with_mnemonic(_("_Color"))
        color_label.set_halign(Gtk.Align.START)
        grid.attach(color_label, 0, 3, 1, 1)
        self.color_chooser_button = Gtk.ColorButton()
        self.color_chooser_button.set_use_alpha(True)
        color_label.set_mnemonic_widget(self.color_chooser_button)
        grid.attach(self.color_chooser_button, 1, 3, 2, 1)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox.pack_start(self.create_frame(_("Input Channels"), vbox), True, True, 0)

        self.display_solo_buttons = Gtk.CheckButton.new_with_mnemonic(_("_Display solo buttons"))
        vbox.pack_start(self.display_solo_buttons, True, True, 0)

        self.vbox.show_all()

    def fill_ui(self):
        super().fill_ui()
        self.display_solo_buttons.set_active(self.channel.display_solo_buttons)
        self.color_chooser_button.set_rgba(self.channel.color)

    def on_response_cb(self, dlg, response_id, *args):
        if response_id == Gtk.ResponseType.APPLY:
            self.channel.display_solo_buttons = self.display_solo_buttons.get_active()
            self.channel.set_color(self.color_chooser_button.get_rgba())

        super().on_response_cb(dlg, response_id, *args)

        if response_id == Gtk.ResponseType.APPLY:
            for inputchannel in self.app.channels:
                inputchannel.update_control_group(self.channel)

        return True


class NewOutputChannelDialog(NewChannelDialog, OutputChannelPropertiesDialog):
    def __init__(self, app, title=None):
        super().__init__(app, title=title or _("New Output Channel"))

    def fill_ui(self, **values):
        self.entry_name.set_text(values.get("name", ""))

        # TODO: disable mode for output channels as mono output channels may
        # not be correctly handled yet.
        self.mono.set_sensitive(False)
        self.stereo.set_sensitive(False)

        # don't set MIDI CCs to previously used values, because they
        # would overwrite existing mappings, if accepted.
        self.entry_volume_cc.set_value(-1)
        self.entry_balance_cc.set_value(-1)
        self.entry_mute_cc.set_value(-1)
        self.stereo.set_active(values.get("stereo", True))
        self.minus_inf.set_active(values.get("initial_vol", -1) == -1)
        # choose a new random color for each new output channel
        self.color_chooser_button.set_rgba(random_color())
        self.display_solo_buttons.set_active(values.get("display_solo_buttons", False))
        self.entry_name.grab_focus()

    def get_result(self):
        return {
            "name": self.entry_name.get_text(),
            "stereo": self.stereo.get_active(),
            "volume_cc": int(self.entry_volume_cc.get_value()),
            "balance_cc": int(self.entry_balance_cc.get_value()),
            "mute_cc": int(self.entry_mute_cc.get_value()),
            "display_solo_buttons": self.display_solo_buttons.get_active(),
            "color": self.color_chooser_button.get_rgba(),
            "initial_vol": 0 if self.zero_dB.get_active() else -1,
        }


class ControlGroup(Gtk.Alignment):
    def __init__(self, output_channel, input_channel):
        super().__init__()
        self.set(0.5, 0.5, 1, 1)
        self.output_channel = output_channel
        self.input_channel = input_channel
        self.app = input_channel.app

        self.hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.vbox)
        self.buttons_box = Gtk.Box(False, BUTTON_PADDING, orientation=Gtk.Orientation.HORIZONTAL)

        set_background_color(self.vbox, output_channel.css_name, output_channel.color)

        self.vbox.pack_start(self.hbox, True, True, BUTTON_PADDING)
        hbox_context = self.hbox.get_style_context()
        hbox_context.add_class("control_group")

        name = output_channel.channel.name
        self.label = Gtk.Label(name)
        self.label.get_style_context().add_class("label")
        self.label.set_max_width_chars(self.input_channel.label_chars_narrow)
        self.label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        if len(name) > self.input_channel.label_chars_narrow:
            self.label.set_tooltip_text(name)

        self.hbox.pack_start(self.label, False, False, BUTTON_PADDING)
        self.hbox.pack_end(self.buttons_box, False, False, BUTTON_PADDING)

        self.mute = mute = Gtk.ToggleButton(_("M"))
        mute.get_style_context().add_class("mute")
        mute.set_tooltip_text(_("Mute output channel send"))
        mute.connect("button-press-event", self.on_mute_button_pressed)
        mute.connect("toggled", self.on_mute_toggled)

        self.solo = solo = Gtk.ToggleButton("S")
        solo.get_style_context().add_class("solo")
        solo.set_tooltip_text(_("Solo output send"))
        solo.connect("button-press-event", self.on_solo_button_pressed)
        solo.connect("toggled", self.on_solo_toggled)

        self.prefader = pre = Gtk.ToggleButton(_("P"))
        pre.get_style_context().add_class("prefader")
        pre.set_tooltip_text(_("Pre (on) / Post (off) fader send"))
        pre.connect("toggled", self.on_prefader_toggled)

        self.buttons_box.pack_start(pre, True, True, BUTTON_PADDING)
        self.buttons_box.pack_start(mute, True, True, BUTTON_PADDING)

        if self.output_channel.display_solo_buttons:
            self.buttons_box.pack_start(solo, True, True, BUTTON_PADDING)

    def update(self):
        if self.output_channel.display_solo_buttons:
            if self.solo not in self.buttons_box.get_children():
                self.buttons_box.pack_start(self.solo, True, True, BUTTON_PADDING)
                self.solo.show()
        else:
            if self.solo in self.buttons_box.get_children():
                self.buttons_box.remove(self.solo)

        name = self.output_channel.channel.name
        self.label.set_text(name)
        if len(name) > self.input_channel.label_chars_narrow:
            self.label.set_tooltip_text(name)

        set_background_color(self.vbox, self.output_channel.css_name, self.output_channel.color)

    def on_mute_toggled(self, button):
        self.output_channel.channel.set_muted(self.input_channel.channel, button.get_active())
        self.app.update_monitor(self.output_channel)

    def on_mute_button_pressed(self, button, event, *args):
        if event.button == 1 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrlr+left-click => exclusive mute for output
            for channel in self.app.channels:
                if channel is not self.input_channel:
                    ctlgroup = channel.get_control_group(self.output_channel)
                    ctlgroup.mute.set_active(False)
            return button.get_active()

    def on_solo_toggled(self, button):
        self.output_channel.channel.set_solo(self.input_channel.channel, button.get_active())
        self.app.update_monitor(self.output_channel)

    def on_solo_button_pressed(self, button, event, *args):
        if event.button == 1 and event.state & Gdk.ModifierType.CONTROL_MASK:
            # Ctrlr+left-click => exclusive solo for output
            for channel in self.app.channels:
                if channel is not self.input_channel:
                    ctlgroup = channel.get_control_group(self.output_channel)
                    ctlgroup.solo.set_active(False)
            return button.get_active()

    def on_prefader_toggled(self, button):
        self.output_channel.channel.set_in_prefader(
            self.input_channel.channel, button.get_active()
        )

    def narrow(self):
        self.hbox.remove(self.label)
        self.hbox.set_child_packing(self.buttons_box, True, True, BUTTON_PADDING, Gtk.PackType.END)

    def widen(self):
        self.hbox.pack_start(self.label, False, False, BUTTON_PADDING)
        self.hbox.set_child_packing(
            self.buttons_box, False, False, BUTTON_PADDING, Gtk.PackType.END
        )


GObject.signal_new(
    "input-channel-order-changed",
    InputChannel,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [GObject.TYPE_STRING, GObject.TYPE_STRING],
)

GObject.signal_new(
    "output-channel-order-changed",
    OutputChannel,
    GObject.SignalFlags.RUN_FIRST | GObject.SignalFlags.ACTION,
    None,
    [GObject.TYPE_STRING, GObject.TYPE_STRING],
)
