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
import glib
import slider
import meter
import abspeak
from serialization import SerializedObject

try:
    import phat
except:
    phat = None


class Channel(gtk.VBox, SerializedObject):
    '''Widget with slider and meter used as base class for more specific
       channel widgets'''
    monitor_button = None

    def __init__(self, app, name, stereo):
        gtk.VBox.__init__(self)
        self.app = app
        self.mixer = app.mixer
        self.gui_factory = app.gui_factory
        self._channel_name = name
        self.stereo = stereo
        self.meter_scale = self.gui_factory.get_default_meter_scale()
        self.slider_scale = self.gui_factory.get_default_slider_scale()
        self.slider_adjustment = slider.AdjustmentdBFS(self.slider_scale, 0.0)
        self.balance_adjustment = gtk.Adjustment(0.0, -1.0, 1.0, 0.02)
        self.future_volume_midi_cc = None
        self.future_balance_midi_cc = None

    def get_channel_name(self):
        return self._channel_name

    label_name = None
    channel = None
    def set_channel_name(self, name):
        self.app.on_channel_rename(self._channel_name, name);
        self._channel_name = name
        if self.label_name:
            self.label_name.set_text(name)
        if self.channel:
            self.channel.name = name
        if self.post_fader_output_channel:
            self.post_fader_output_channel.name = "%s Out" % name;
    channel_name = property(get_channel_name, set_channel_name)

    def realize(self):
        #print "Realizing channel \"%s\"" % self.channel_name

        self.slider_adjustment.connect("volume-changed", self.on_volume_changed)
        self.balance_adjustment.connect("value-changed", self.on_balance_changed)
        self.connect('midi-event-received', self.on_midi_event_received)

        self.slider = None
        self.create_slider_widget()

        if self.stereo:
            self.meter = meter.StereoMeterWidget(self.meter_scale)
        else:
            self.meter = meter.MonoMeterWidget(self.meter_scale)
        self.on_vumeter_color_changed(self.gui_factory)

        self.meter.set_events(gtk.gdk.SCROLL_MASK)

        self.gui_factory.connect("default-meter-scale-changed", self.on_default_meter_scale_changed)
        self.gui_factory.connect("default-slider-scale-changed", self.on_default_slider_scale_changed)
        self.gui_factory.connect('vumeter-color-changed', self.on_vumeter_color_changed)
        self.gui_factory.connect('vumeter-color-scheme-changed', self.on_vumeter_color_changed)
        self.gui_factory.connect('use-custom-widgets-changed', self.on_custom_widgets_changed)

        self.abspeak = abspeak.AbspeakWidget()
        self.abspeak.connect("reset", self.on_abspeak_reset)
        self.abspeak.connect("volume-adjust", self.on_abspeak_adjust)

        self.volume_digits = gtk.Entry()
        self.volume_digits.connect("key-press-event", self.on_volume_digits_key_pressed)
        self.volume_digits.connect("focus-out-event", self.on_volume_digits_focus_out)

        self.connect("key-press-event", self.on_key_pressed)
        self.connect("scroll-event", self.on_scroll)

    def unrealize(self):
        #print "Unrealizing channel \"%s\"" % self.channel_name
        pass

    def create_balance_widget(self):
        if self.gui_factory.use_custom_widgets and phat:
            self.balance = phat.HFanSlider()
            self.balance.set_default_value(0)
            self.balance.set_adjustment(self.balance_adjustment)
        else:
            self.balance = gtk.HScale(self.balance_adjustment)
            self.balance.set_draw_value(False)
        self.pack_start(self.balance, False)
        if self.monitor_button:
            self.reorder_child(self.monitor_button, -1)
        self.balance.show()

    def create_slider_widget(self):
        parent = None
        if self.slider:
            parent = self.slider.get_parent()
            self.slider.destroy()
        if self.gui_factory.use_custom_widgets:
            self.slider = slider.CustomSliderWidget(self.slider_adjustment)
        else:
            self.slider = slider.GtkSlider(self.slider_adjustment)
        if parent:
            parent.pack_start(self.slider)
            parent.reorder_child(self.slider, 0)
        self.slider.show()

    def on_default_meter_scale_changed(self, gui_factory, scale):
        #print "Default meter scale change detected."
        self.meter.set_scale(scale)

    def on_default_slider_scale_changed(self, gui_factory, scale):
        #print "Default slider scale change detected."
        self.slider_scale = scale
        self.slider_adjustment.set_scale(scale)
        self.channel.midi_scale = self.slider_scale.scale

    def on_vumeter_color_changed(self, gui_factory, *args):
        color = gui_factory.get_vumeter_color()
        color_scheme = gui_factory.get_vumeter_color_scheme()
        if color_scheme != 'solid':
            self.meter.set_color(None)
        else:
            self.meter.set_color(gtk.gdk.color_parse(color))

    def on_custom_widgets_changed(self, gui_factory, value):
        self.balance.destroy()
        self.create_balance_widget()
        self.create_slider_widget()

    def on_abspeak_adjust(self, abspeak, adjust):
        #print "abspeak adjust %f" % adjust
        self.slider_adjustment.set_value_db(self.slider_adjustment.get_value_db() + adjust)
        self.channel.abspeak = None
        #self.update_volume(False)   # We want to update gui even if actual decibels have not changed (scale wrap for example)

    def on_abspeak_reset(self, abspeak):
        #print "abspeak reset"
        self.channel.abspeak = None

    def on_volume_digits_key_pressed(self, widget, event):
        if (event.keyval == gtk.keysyms.Return or event.keyval == gtk.keysyms.KP_Enter):
            db_text = self.volume_digits.get_text()
            try:
                db = float(db_text)
                #print "Volume digits confirmation \"%f dBFS\"" % db
            except (ValueError), e:
                #print "Volume digits confirmation ignore, reset to current"
                self.update_volume(False)
                return
            self.slider_adjustment.set_value_db(db)
            #self.grab_focus()
            #self.update_volume(False)   # We want to update gui even if actual decibels have not changed (scale wrap for example)

    def on_volume_digits_focus_out(self, widget, event):
        #print "volume digits focus out detected"
        self.update_volume(False)

    def read_meter(self):
        if not self.channel:
            return
        if self.stereo:
            meter_left, meter_right = self.channel.meter
            self.meter.set_values(meter_left, meter_right)
        else:
            self.meter.set_value(self.channel.meter[0])

        self.abspeak.set_peak(self.channel.abspeak)

    def on_scroll(self, widget, event):
        if event.direction == gtk.gdk.SCROLL_DOWN:
            self.slider_adjustment.step_down()
        elif event.direction == gtk.gdk.SCROLL_UP:
            self.slider_adjustment.step_up()
        return True

    def update_volume(self, update_engine):
        db = self.slider_adjustment.get_value_db()

        db_text = "%.2f" % db
        self.volume_digits.set_text(db_text)

        if update_engine:
            #print "Setting engine volume to " + db_text
            self.channel.volume = db
            self.app.update_monitor(self)

    def on_volume_changed(self, adjustment):
        self.update_volume(True)

    def on_balance_changed(self, adjustment):
        balance = self.balance_adjustment.get_value()
        #print "%s balance: %f" % (self.channel_name, balance)
        self.channel.balance = balance
        self.app.update_monitor(self)

    def on_key_pressed(self, widget, event):
        if (event.keyval == gtk.keysyms.Up):
            #print self.channel_name + " Up"
            self.slider_adjustment.step_up()
            return True
        elif (event.keyval == gtk.keysyms.Down):
            #print self.channel_name + " Down"
            self.slider_adjustment.step_down()
            return True

        return False

    def serialize(self, object_backend):
        object_backend.add_property("volume", "%f" % self.slider_adjustment.get_value_db())
        object_backend.add_property("balance", "%f" % self.balance_adjustment.get_value())

        if self.channel.volume_midi_cc:
            object_backend.add_property('volume_midi_cc', str(self.channel.volume_midi_cc))
        if self.channel.balance_midi_cc:
            object_backend.add_property('balance_midi_cc', str(self.channel.balance_midi_cc))

    def unserialize_property(self, name, value):
        if name == "volume":
            self.slider_adjustment.set_value_db(float(value))
            return True
        if name == "balance":
            self.balance_adjustment.set_value(float(value))
            return True
        if name == 'volume_midi_cc':
            self.future_volume_midi_cc = int(value)
            return True
        if name == 'balance_midi_cc':
            self.future_balance_midi_cc = int(value)
            return True
        return False

    def on_midi_event_received(self, *args):
        self.slider_adjustment.set_value_db(self.channel.volume)
        self.balance_adjustment.set_value(self.channel.balance)

    def midi_change_callback(self, *args):
        # the changes are not applied directly to the widgets as they
        # absolutely have to be done from the gtk thread.
        self.emit('midi-event-received')

    def on_monitor_button_toggled(self, button):
        if not button.get_active():
            self.app.main_mix.monitor_button.set_active(True)
        else:
            for channel in self.app.channels + self.app.output_channels + [self.app.main_mix]:
                if channel.monitor_button.get_active() and channel.monitor_button is not button:
                    channel.monitor_button.handler_block_by_func(
                                channel.on_monitor_button_toggled)
                    channel.monitor_button.set_active(False)
                    channel.monitor_button.handler_unblock_by_func(
                                channel.on_monitor_button_toggled)
            self.app.set_monitored_channel(self)

    def set_monitored(self):
        if self.channel:
            self.app.set_monitored_channel(self)
        self.monitor_button.set_active(True)

gobject.signal_new('midi-event-received', Channel,
                gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION,
                gobject.TYPE_NONE, ())

class InputChannel(Channel):
    post_fader_output_channel = None

    def __init__(self, app, name, stereo):
        Channel.__init__(self, app, name, stereo)

    def realize(self):
        self.channel = self.mixer.add_channel(self.channel_name, self.stereo)
        if self.channel == None:
            raise Exception,"Cannot create a channel"
        Channel.realize(self)
        if self.future_volume_midi_cc:
            self.channel.volume_midi_cc = self.future_volume_midi_cc
        if self.future_balance_midi_cc:
            self.channel.balance_midi_cc = self.future_balance_midi_cc
        self.channel.midi_scale = self.slider_scale.scale
        self.channel.midi_change_callback = self.midi_change_callback

        self.on_volume_changed(self.slider_adjustment)
        self.on_balance_changed(self.balance_adjustment)

        # vbox child at upper part
        self.vbox = gtk.VBox()
        self.pack_start(self.vbox, False)
        self.label_name = gtk.Label()
        self.label_name.set_text(self.channel_name)
        self.label_name.set_size_request(0, -1)
        self.label_name_event_box = gtk.EventBox()
        self.label_name_event_box.connect("button-press-event", self.on_label_mouse)
        self.label_name_event_box.add(self.label_name)
        self.vbox.pack_start(self.label_name_event_box, True)
#         self.label_stereo = gtk.Label()
#         if self.stereo:
#             self.label_stereo.set_text("stereo")
#         else:
#             self.label_stereo.set_text("mono")
#         self.label_stereo.set_size_request(0, -1)
#         self.vbox.pack_start(self.label_stereo, True)

        # hbox for mute and solo buttons
        self.hbox_mutesolo = gtk.HBox()

        self.mute = gtk.ToggleButton()
        self.mute.set_label("M")
        self.mute.set_active(self.channel.mute)
        self.mute.connect("button-press-event", self.on_mute_button_pressed)
        self.mute.connect("toggled", self.on_mute_toggled)
        self.hbox_mutesolo.pack_start(self.mute, True)

        self.solo = gtk.ToggleButton()
        self.solo.set_label("S")
        self.solo.set_active(self.channel.solo)
        self.solo.connect("button-press-event", self.on_solo_button_pressed)
        self.solo.connect("toggled", self.on_solo_toggled)
        self.hbox_mutesolo.pack_start(self.solo, True)

        self.vbox.pack_start(self.hbox_mutesolo, False)

        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.abspeak);
        self.pack_start(frame, False)

        # hbox child at lower part
        self.hbox = gtk.HBox()
        self.hbox.pack_start(self.slider, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.meter);
        self.hbox.pack_start(frame, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.hbox);
        self.pack_start(frame, True)

        self.volume_digits.set_size_request(0, -1)
        self.pack_start(self.volume_digits, False)

        self.create_balance_widget()

        self.monitor_button = gtk.ToggleButton('MON')
        self.monitor_button.connect('toggled', self.on_monitor_button_toggled)
        self.pack_start(self.monitor_button, False, False)

    def add_control_group(self, channel):
        control_group = ControlGroup(channel, self)
        control_group.show_all()
        self.vbox.pack_start(control_group, False)
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
        for control_group in self.vbox.get_children():
            if isinstance(control_group, ControlGroup):
                if control_group.output_channel is channel:
                    return control_group
        return None

    def unrealize(self):
        Channel.unrealize(self)
        if self.post_fader_output_channel:
            self.post_fader_output_channel.remove()
            self.post_fader_output_channel = None
        self.channel.remove()
        self.channel = None

    channel_properties_dialog = None
    def on_channel_properties(self):
        if not self.channel_properties_dialog:
            self.channel_properties_dialog = ChannelPropertiesDialog(self, self.app)
        self.channel_properties_dialog.show()
        self.channel_properties_dialog.present()

    def on_label_mouse(self, widget, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            if event.button == 1:
                self.on_channel_properties()

    def on_mute_toggled(self, button):
        self.channel.mute = self.mute.get_active()
        self.app.update_monitor(self.app.main_mix)

    def on_mute_button_pressed(self, button, event, *args):
        if event.button == 3:
            # right click on the mute button, act on all output channels
            if button.get_active(): # was muted
                button.set_active(False)
                if hasattr(button, 'touched_channels'):
                    touched_channels = button.touched_channels
                    for chan in touched_channels:
                        ctlgroup = self.get_control_group(chan)
                        ctlgroup.mute.set_active(False)
                    del button.touched_channels
            else: # was not muted
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
        self.app.update_monitor(self.app.main_mix)

    def on_solo_button_pressed(self, button, event, *args):
        if event.button == 3:
            # right click on the solo button, act on all output channels
            if button.get_active(): # was soloed
                button.set_active(False)
                if hasattr(button, 'touched_channels'):
                    touched_channels = button.touched_channels
                    for chan in touched_channels:
                        ctlgroup = self.get_control_group(chan)
                        ctlgroup.solo.set_active(False)
                    del button.touched_channels
            else: # was not soloed
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
        return 'input_channel'

    def serialize(self, object_backend):
        object_backend.add_property("name", self.channel_name)
        if self.stereo:
            object_backend.add_property("type", "stereo")
        else:
            object_backend.add_property("type", "mono")
        Channel.serialize(self, object_backend)

    def unserialize_property(self, name, value):
        if name == "name":
            self.channel_name = str(value)
            return True
        if name == "type":
            if value == "stereo":
                self.stereo = True
                return True
            if value == "mono":
                self.stereo = False
                return True
        return Channel.unserialize_property(self, name, value)


available_colours = [
    ('#ef2929', '#cc0000', '#840000'),
    ('#729fcf', '#3465a4', '#204a67'),
    ('#8aa234', '#73d216', '#4e7a06'),
    ('#fce84f', '#edd400', '#c48000'),
    ('#fcaf3e', '#f57900', '#ae5c00'),
    ('#ad7fa8', '#75507b', '#4c3556'),
    ('#e9b96e', '#c17d11', '#6f4902'),
]

class OutputChannel(Channel):
    colours = available_colours[:]
    _display_solo_buttons = False

    _init_muted_channels = None
    _init_solo_channels = None

    def __init__(self, app, name, stereo):
        Channel.__init__(self, app, name, stereo)

    def get_display_solo_buttons(self):
        return self._display_solo_buttons

    def set_display_solo_buttons(self, value):
        self._display_solo_buttons = value
        # notifying control groups
        for inputchannel in self.app.channels:
            inputchannel.update_control_group(self)

    display_solo_buttons = property(get_display_solo_buttons, set_display_solo_buttons)

    def realize(self):
        Channel.realize(self)
        self.channel = self.mixer.add_output_channel(self.channel_name, self.stereo)
        if self.channel == None:
            raise Exception,"Cannot create a channel"
        Channel.realize(self)

        self.channel.midi_scale = self.slider_scale.scale
        self.channel.midi_change_callback = self.midi_change_callback

        self.on_volume_changed(self.slider_adjustment)
        self.on_balance_changed(self.balance_adjustment)

        # vbox child at upper part
        self.vbox = gtk.VBox()
        self.pack_start(self.vbox, False)
        self.label_name = gtk.Label()
        self.label_name.set_text(self.channel_name)
        self.label_name.set_size_request(0, -1)
        self.label_name_event_box = gtk.EventBox()
        self.label_name_event_box.connect('button-press-event', self.on_label_mouse)
        self.label_name_event_box.add(self.label_name)
        if not self.colours:
            OutputChannel.colours = available_colours[:]
        for color in self.colours:
            self.color_tuple = [gtk.gdk.color_parse(color[x]) for x in range(3)]
            self.colours.remove(color)
            break
        self.label_name_event_box.modify_bg(gtk.STATE_NORMAL, self.color_tuple[1])
        self.vbox.pack_start(self.label_name_event_box, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.abspeak);
        self.vbox.pack_start(frame, False)

        # hbox child at lower part
        self.hbox = gtk.HBox()
        self.hbox.pack_start(self.slider, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.meter);
        self.hbox.pack_start(frame, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.hbox);
        self.pack_start(frame, True)

        self.volume_digits.set_size_request(0, -1)
        self.pack_start(self.volume_digits, False)

        self.create_balance_widget()

        self.monitor_button = gtk.ToggleButton('MON')
        self.monitor_button.connect('toggled', self.on_monitor_button_toggled)
        self.pack_start(self.monitor_button, False, False)

        # add control groups to the input channels, and initialize them
        # appropriately
        for input_channel in self.app.channels:
            ctlgroup = input_channel.add_control_group(self)
            if self._init_muted_channels and input_channel.channel.name in self._init_muted_channels:
                ctlgroup.mute.set_active(True)
            if self._init_solo_channels and input_channel.channel.name in self._init_solo_channels:
                ctlgroup.solo.set_active(True)
        self._init_muted_channels = None
        self._init_solo_channels = None

    channel_properties_dialog = None
    def on_channel_properties(self):
        if not self.channel_properties_dialog:
            self.channel_properties_dialog = OutputChannelPropertiesDialog(self, self.app)
        self.channel_properties_dialog.show()
        self.channel_properties_dialog.present()

    def on_label_mouse(self, widget, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            if event.button == 1:
                self.on_channel_properties()

    def unrealize(self):
        # remove control groups from input channels
        for input_channel in self.app.channels:
            input_channel.remove_control_group(self)
        # then remove itself
        Channel.unrealize(self)
        self.channel.remove()
        self.channel = None

    @classmethod
    def serialization_name(cls):
        return 'output_channel'

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
        for input_channel in self.app.channels:
            if self.channel.is_muted(input_channel.channel):
                muted_channels.append(input_channel)
            if self.channel.is_solo(input_channel.channel):
                solo_channels.append(input_channel)
        if muted_channels:
            object_backend.add_property('muted_channels', '|'.join([x.channel.name for x in muted_channels]))
        if solo_channels:
            object_backend.add_property('solo_channels', '|'.join([x.channel.name for x in solo_channels]))
        Channel.serialize(self, object_backend)

    def unserialize_property(self, name, value):
        if name == "name":
            self.channel_name = str(value)
            return True
        if name == "type":
            if value == "stereo":
                self.stereo = True
                return True
            if value == "mono":
                self.stereo = False
                return True
        if name == "solo_buttons":
            if value == "true":
                self.display_solo_buttons = True
                return True
        if name == 'muted_channels':
            self._init_muted_channels = value.split('|')
            return True
        if name == 'solo_channels':
            self._init_solo_channels = value.split('|')
            return True
        return Channel.unserialize_property(self, name, value)

class MainMixChannel(Channel):
    _init_muted_channels = None
    _init_solo_channels = None

    def __init__(self, app):
        Channel.__init__(self, app, "MAIN", True)

    def realize(self):
        Channel.realize(self)
        self.channel = self.mixer.main_mix_channel
        self.channel.midi_scale = self.slider_scale.scale
        self.channel.midi_change_callback = self.midi_change_callback

        self.on_volume_changed(self.slider_adjustment)
        self.on_balance_changed(self.balance_adjustment)

        # vbox child at upper part
        self.vbox = gtk.VBox()
        self.pack_start(self.vbox, False)
        self.label_name = gtk.Label()
        self.label_name.set_text(self.channel_name)
        self.label_name.set_size_request(0, -1)
        self.vbox.pack_start(self.label_name, False)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.abspeak);
        self.vbox.pack_start(frame, False)

        # hbox child at lower part
        self.hbox = gtk.HBox()
        self.hbox.pack_start(self.slider, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.meter);
        self.hbox.pack_start(frame, True)
        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_IN)
        frame.add(self.hbox);
        self.pack_start(frame, True)

        self.volume_digits.set_size_request(0, -1)
        self.pack_start(self.volume_digits, False)

        self.create_balance_widget()

        self.monitor_button = gtk.ToggleButton('MON')
        self.monitor_button.connect('toggled', self.on_monitor_button_toggled)
        self.pack_start(self.monitor_button, False, False)

        for input_channel in self.app.channels:
            if self._init_muted_channels and input_channel.channel.name in self._init_muted_channels:
                input_channel.mute.set_active(True)
            if self._init_solo_channels and input_channel.channel.name in self._init_solo_channels:
                input_channel.solo.set_active(True)
        self._init_muted_channels = None
        self._init_solo_channels = None

    def unrealize(self):
        Channel.unrealize(self)
        self.channel = False

    @classmethod
    def serialization_name(cls):
        return 'main_mix_channel'

    def serialize(self, object_backend):
        muted_channels = []
        solo_channels = []
        for input_channel in self.app.channels:
            if input_channel.channel.mute:
                muted_channels.append(input_channel)
            if input_channel.channel.solo:
                solo_channels.append(input_channel)
        if muted_channels:
            object_backend.add_property('muted_channels', '|'.join([x.channel.name for x in muted_channels]))
        if solo_channels:
            object_backend.add_property('solo_channels', '|'.join([x.channel.name for x in solo_channels]))
        Channel.serialize(self, object_backend)

    def unserialize_property(self, name, value):
        if name == 'muted_channels':
            self._init_muted_channels = value.split('|')
            return True
        if name == 'solo_channels':
            self._init_solo_channels = value.split('|')
            return True
        return Channel.unserialize_property(self, name, value)


class ChannelPropertiesDialog(gtk.Dialog):
    channel = None

    def __init__(self, parent, app):
        self.channel = parent
        self.app = app
        self.mixer = self.channel.mixer
        gtk.Dialog.__init__(self,
                        'Channel "%s" Properties' % self.channel.channel_name,
                        self.channel.gui_factory.topwindow)

        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.ok_button = self.add_button(gtk.STOCK_APPLY, gtk.RESPONSE_APPLY)
        self.set_default_response(gtk.RESPONSE_APPLY);

        self.create_ui()
        self.fill_ui()

        self.connect('response', self.on_response_cb)
        self.connect('delete-event', self.on_response_cb)

    def create_frame(self, label, child):
        frame = gtk.Frame('')
        frame.set_border_width(3)
        #frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.get_label_widget().set_markup('<b>%s</b>' % label)

        alignment = gtk.Alignment(0, 0, 1, 1)
        alignment.set_padding(0, 0, 12, 0)
        frame.add(alignment)
        alignment.add(child)

        return frame

    def create_ui(self):
        vbox = gtk.VBox()
        self.vbox.add(vbox)

        table = gtk.Table(2, 2, False)
        vbox.pack_start(self.create_frame('Properties', table))
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        table.attach(gtk.Label('Name'), 0, 1, 0, 1)
        self.entry_name = gtk.Entry()
        self.entry_name.set_activates_default(True)
        self.entry_name.connect('changed', self.on_entry_name_changed)
        table.attach(self.entry_name, 1, 2, 0, 1)

        table.attach(gtk.Label('Mode'), 0, 1, 1, 2)
        self.mode_hbox = gtk.HBox()
        table.attach(self.mode_hbox, 1, 2, 1, 2)
        self.mono = gtk.RadioButton(label='Mono')
        self.stereo = gtk.RadioButton(label='Stereo', group=self.mono)
        self.mode_hbox.pack_start(self.mono)
        self.mode_hbox.pack_start(self.stereo)

        table = gtk.Table(2, 3, False)
        vbox.pack_start(self.create_frame('MIDI Control Channels', table))
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        table.attach(gtk.Label('Volume'), 0, 1, 0, 1)
        self.entry_volume_cc = gtk.Entry()
        self.entry_volume_cc.set_activates_default(True)
        self.entry_volume_cc.set_editable(False)
        self.entry_volume_cc.set_width_chars(3)
        table.attach(self.entry_volume_cc, 1, 2, 0, 1)
        self.button_sense_midi_volume = gtk.Button('Autoset')
        self.button_sense_midi_volume.connect('clicked',
                        self.on_sense_midi_volume_clicked)
        table.attach(self.button_sense_midi_volume, 2, 3, 0, 1)

        table.attach(gtk.Label('Balance'), 0, 1, 1, 2)
        self.entry_balance_cc = gtk.Entry()
        self.entry_balance_cc.set_activates_default(True)
        self.entry_balance_cc.set_width_chars(3)
        self.entry_balance_cc.set_editable(False)
        table.attach(self.entry_balance_cc, 1, 2, 1, 2)
        self.button_sense_midi_balance = gtk.Button('Autoset')
        self.button_sense_midi_balance.connect('clicked',
                        self.on_sense_midi_balance_clicked)
        table.attach(self.button_sense_midi_balance, 2, 3, 1, 2)

        self.vbox.show_all()

    def fill_ui(self):
        self.entry_name.set_text(self.channel.channel_name)
        if self.channel.channel.is_stereo:
            self.stereo.set_active(True)
        else:
            self.mono.set_active(True)
        self.mode_hbox.set_sensitive(False)
        self.entry_volume_cc.set_text('%s' % self.channel.channel.volume_midi_cc)
        self.entry_balance_cc.set_text('%s' % self.channel.channel.balance_midi_cc)

    def sense_popup_dialog(self, entry):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_destroy_with_parent(True)
        window.set_transient_for(self)
        window.set_decorated(False)
        window.set_modal(True)
        window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        window.set_border_width(10)

        vbox = gtk.VBox(10)
        window.add(vbox)
        window.timeout = 5
        vbox.pack_start(gtk.Label('Please move the MIDI control you want to use for this function.'))
        timeout_label = gtk.Label('This window will close in 5 seconds')
        vbox.pack_start(timeout_label)
        def close_sense_timeout(window, entry):
            window.timeout -= 1
            timeout_label.set_text('This window will close in %d seconds.' % window.timeout)
            if window.timeout == 0:
                window.destroy()
                entry.set_text('%s' % self.mixer.last_midi_channel)
                return False
            return True
        window.show_all()
        glib.timeout_add_seconds(1, close_sense_timeout, window, entry)

    def on_sense_midi_volume_clicked(self, *args):
        self.sense_popup_dialog(self.entry_volume_cc)

    def on_sense_midi_balance_clicked(self, *args):
        self.sense_popup_dialog(self.entry_balance_cc)

    def on_response_cb(self, dlg, response_id, *args):
        self.channel.channel_properties_dialog = None
        self.destroy()
        if response_id == gtk.RESPONSE_APPLY:
            name = self.entry_name.get_text()
            self.channel.channel_name = name
            self.channel.channel.volume_midi_cc = int(self.entry_volume_cc.get_text())
            self.channel.channel.balance_midi_cc = int(self.entry_balance_cc.get_text())

    def on_entry_name_changed(self, entry):
        sensitive = False
        if len(entry.get_text()):
            if self.channel and self.channel.channel.name == entry.get_text():
                sensitive = True
            elif entry.get_text() not in [x.channel.name for x in self.app.channels] + \
                        [x.channel.name for x in self.app.output_channels] + ['MAIN']:
                sensitive = True
        self.ok_button.set_sensitive(sensitive)


class NewChannelDialog(ChannelPropertiesDialog):
    def __init__(self, app):
        gtk.Dialog.__init__(self, 'New Channel', app.window)
        self.mixer = app.mixer
        self.app = app
        self.create_ui()

        self.stereo.set_active(True) # default to stereo

        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.ok_button = self.add_button(gtk.STOCK_ADD, gtk.RESPONSE_OK)
        self.ok_button.set_sensitive(False)
        self.set_default_response(gtk.RESPONSE_OK);

    def get_result(self):
        return {'name': self.entry_name.get_text(),
                'stereo': self.stereo.get_active(),
                'volume_cc': self.entry_volume_cc.get_text(),
                'balance_cc': self.entry_balance_cc.get_text()
               }

class OutputChannelPropertiesDialog(ChannelPropertiesDialog):
    def create_ui(self):
        ChannelPropertiesDialog.create_ui(self)

        vbox = gtk.VBox()
        self.vbox.pack_start(self.create_frame('Input Channels', vbox))

        self.display_solo_buttons = gtk.CheckButton('Display solo buttons')
        vbox.pack_start(self.display_solo_buttons)

        self.vbox.show_all()

    def fill_ui(self):
        ChannelPropertiesDialog.fill_ui(self)
        self.display_solo_buttons.set_active(self.channel.display_solo_buttons)

    def on_response_cb(self, dlg, response_id, *args):
        ChannelPropertiesDialog.on_response_cb(self, dlg, response_id, *args)
        if response_id == gtk.RESPONSE_APPLY:
            self.channel.display_solo_buttons = self.display_solo_buttons.get_active()


class NewOutputChannelDialog(OutputChannelPropertiesDialog):
    def __init__(self, app):
        gtk.Dialog.__init__(self, 'New Output Channel', app.window)
        self.mixer = app.mixer
        self.app = app
        self.create_ui()

        # TODO: disable mode for output channels as mono output channels may
        # not be correctly handled yet.
        self.mode_hbox.set_sensitive(False)
        self.stereo.set_active(True) # default to stereo

        self.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.ok_button = self.add_button(gtk.STOCK_ADD, gtk.RESPONSE_OK)
        self.ok_button.set_sensitive(False)
        self.set_default_response(gtk.RESPONSE_OK);

    def get_result(self):
        return {'name': self.entry_name.get_text(),
                'stereo': self.stereo.get_active(),
                'volume_cc': self.entry_volume_cc.get_text(),
                'balance_cc': self.entry_balance_cc.get_text(),
                'display_solo_buttons': self.display_solo_buttons.get_active(),
               }


class ControlGroup(gtk.Alignment):
    def __init__(self, output_channel, input_channel):
        gtk.Alignment.__init__(self, 0.5, 0.5, 0, 0)
        self.output_channel = output_channel
        self.input_channel = input_channel
        self.app = input_channel.app

        hbox = gtk.HBox()
        self.hbox = hbox
        self.add(hbox)

        mute = gtk.ToggleButton()
        self.mute = mute
        mute.set_label("M")
        mute.connect("toggled", self.on_mute_toggled)
        hbox.pack_start(mute, False)

        solo = gtk.ToggleButton()
        self.solo = solo
        solo.set_label("S")
        solo.connect("toggled", self.on_solo_toggled)
        if self.output_channel.display_solo_buttons:
            hbox.pack_start(solo, True)

        mute.modify_bg(gtk.STATE_PRELIGHT, output_channel.color_tuple[0])
        mute.modify_bg(gtk.STATE_NORMAL, output_channel.color_tuple[1])
        mute.modify_bg(gtk.STATE_ACTIVE, output_channel.color_tuple[2])
        solo.modify_bg(gtk.STATE_PRELIGHT, output_channel.color_tuple[0])
        solo.modify_bg(gtk.STATE_NORMAL, output_channel.color_tuple[1])
        solo.modify_bg(gtk.STATE_ACTIVE, output_channel.color_tuple[2])

    def update(self):
        if self.output_channel.display_solo_buttons:
            if not self.solo in self.hbox.get_children():
                self.hbox.pack_start(self.solo, True)
                self.solo.show()
        else:
            if self.solo in self.hbox.get_children():
                self.hbox.remove(self.solo)

    def on_mute_toggled(self, button):
        self.output_channel.channel.set_muted(self.input_channel.channel, button.get_active())
        self.app.update_monitor(self)

    def on_solo_toggled(self, button):
        self.output_channel.channel.set_solo(self.input_channel.channel, button.get_active())
        self.app.update_monitor(self)

