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
import scale
import slider
import meter
import abspeak
import jack_mixer_c
import math
import random
from serialization import serialized_object

try:
    import phat
except:
    print "PHAT audio widgets not found, some features will not be available"
    phat = None

import fpconst

class channel(gtk.VBox, serialized_object):
    '''Widget with slider and meter used as base class for more specific channel widgets'''
    def __init__(self, mixer, gui_factory, name, stereo):
        gtk.VBox.__init__(self)
        self.mixer = mixer
        self.gui_factory = gui_factory
        self.channel_name = name
        self.stereo = stereo
        self.meter_scale = gui_factory.get_default_meter_scale()
        self.slider_scale = gui_factory.get_default_slider_scale()
        self.slider_adjustment = slider.adjustment_dBFS(self.slider_scale, 0.0)
        self.balance_adjustment = gtk.Adjustment(0.0, -1.0, 1.0, 0.02)

    def realize(self):
        #print "Realizing channel \"%s\"" % self.channel_name

        self.slider_adjustment.connect("volume-changed", self.on_volume_changed)
        self.balance_adjustment.connect("value-changed", self.on_balance_changed)

        self.slider = slider.widget(self.slider_adjustment)

        if self.stereo:
            self.meter = meter.stereo(self.meter_scale)
        else:
            self.meter = meter.mono(self.meter_scale)

        self.meter.set_events(gtk.gdk.SCROLL_MASK)

        self.gui_factory.connect("default-meter-scale-changed", self.on_default_meter_scale_changed)
        self.gui_factory.connect("default-slider-scale-changed", self.on_default_slider_scale_changed)

        self.abspeak = abspeak.widget()
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

    def on_default_meter_scale_changed(self, gui_factory, scale):
        #print "Default meter scale change detected."
        self.meter.set_scale(scale)

    def on_default_slider_scale_changed(self, gui_factory, scale):
        #print "Default slider scale change detected."
        self.slider_scale = scale
        self.slider_adjustment.set_scale(scale)
        jack_mixer_c.channel_set_midi_scale(self.channel, self.slider_scale.scale)

    def on_abspeak_adjust(self, abspeak, adjust):
        #print "abspeak adjust %f" % adjust
        self.slider_adjustment.set_value_db(self.slider_adjustment.get_value_db() + adjust)
        jack_mixer_c.channel_abspeak_reset(self.channel)
        #self.update_volume(False)   # We want to update gui even if actual decibels have not changed (scale wrap for example)

    def on_abspeak_reset(self, abspeak):
        #print "abspeak reset"
        jack_mixer_c.channel_abspeak_reset(self.channel)

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
        if self.stereo:
            meter_left, meter_right = jack_mixer_c.channel_stereo_meter_read(self.channel)
            self.meter.set_values(meter_left, meter_right)
        else:
            self.meter.set_value(jack_mixer_c.channel_mono_meter_read(self.channel))

        self.abspeak.set_peak(jack_mixer_c.channel_abspeak_read(self.channel))

    def midi_change_check(self):
        if jack_mixer_c.channel_is_midi_modified(self.channel):
            volume = jack_mixer_c.channel_volume_read(self.channel)
            balance = jack_mixer_c.channel_balance_read(self.channel)
            #print volume, balance
            self.slider_adjustment.set_value_db(volume)
            self.balance_adjustment.set_value(balance)

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
            jack_mixer_c.channel_volume_write(self.channel, db)

    def on_volume_changed(self, adjustment):
        self.update_volume(True)

    def on_balance_changed(self, adjustment):
        balance = self.balance_adjustment.get_value()
        #print "%s balance: %f" % (self.channel_name, balance)
        jack_mixer_c.channel_balance_write(self.channel, balance)

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

    def unserialize_property(self, name, value):
        if name == "volume":
            self.slider_adjustment.set_value_db(float(value))
            return True
        if name == "balance":
            self.balance_adjustment.set_value(float(value))
            return True
        return False

class input_channel(channel):
    def __init__(self, mixer, gui_factory, name, stereo):
        channel.__init__(self, mixer, gui_factory, name, stereo)

    def realize(self):
        self.channel = jack_mixer_c.add_channel(self.mixer, self.channel_name, self.stereo)
        if self.channel == None:
            raise Exception,"Cannot create a channel"
        channel.realize(self)
        jack_mixer_c.channel_set_midi_scale(self.channel, self.slider_scale.scale)

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
        self.mute.set_active(jack_mixer_c.channel_is_muted(self.channel))
        self.mute.connect("toggled", self.on_mute_toggled)
        self.hbox_mutesolo.pack_start(self.mute, True)

        self.solo = gtk.ToggleButton()
        self.solo.set_label("S")
        self.solo.set_active(jack_mixer_c.channel_is_soloed(self.channel))
        self.solo.connect("toggled", self.on_solo_toggled)
        self.hbox_mutesolo.pack_start(self.solo, True)

        self.vbox.pack_start(self.hbox_mutesolo, False)

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

        if phat:
            self.balance = phat.HFanSlider()
            self.balance.set_default_value(0)
            self.balance.set_adjustment(self.balance_adjustment)
            self.pack_start(self.balance, False)
        else:
            self.balance = gtk.HScale(self.balance_adjustment)
            self.balance.set_draw_value(False)
            self.pack_start(self.balance, False)

    def unrealize(self):
        channel.unrealize(self)
        jack_mixer_c.remove_channel(self.channel)
        self.channel = False

    def on_rename_channel(self):
        result = self.gui_factory.run_dialog_rename_channel(self.channel_name)
        if result != None:
            #print "renaming to \"%s\"" % result
            self.channel_name = result
            self.label_name.set_text(self.channel_name)
            jack_mixer_c.channel_rename(self.channel, self.channel_name)

    def on_label_mouse(self, widget, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            if event.button == 1:
                self.on_rename_channel()

    def on_mute_toggled(self, button):
        if self.mute.get_active():
            #print "muted"
            jack_mixer_c.channel_mute(self.channel)
        else:
            #print "unmuted"
            jack_mixer_c.channel_unmute(self.channel)

    def on_solo_toggled(self, button):
        if self.solo.get_active():
            #print "soloed"
            jack_mixer_c.channel_solo(self.channel)
        else:
            #print "unsoloed"
            jack_mixer_c.channel_unsolo(self.channel)

    def serialization_name(self):
        return input_channel_serialization_name()

    def serialize(self, object_backend):
        object_backend.add_property("name", self.channel_name)
        if self.stereo:
            object_backend.add_property("type", "stereo")
        else:
            object_backend.add_property("type", "mono")
        channel.serialize(self, object_backend)

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
        return channel.unserialize_property(self, name, value)

def input_channel_serialization_name():
    return "input_channel"

class main_mix(channel):
    def __init__(self, mixer, gui_factory):
        channel.__init__(self, mixer, gui_factory, "MAIN", True)

    def realize(self):
        channel.realize(self)
        self.channel = jack_mixer_c.get_main_mix_channel(self.mixer)
        jack_mixer_c.channel_set_midi_scale(self.channel, self.slider_scale.scale)

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

        if phat:
            self.balance = phat.HFanSlider()
            self.balance.set_default_value(0)
            self.balance.set_adjustment(self.balance_adjustment)
            self.pack_start(self.balance, False)
        else:
            self.balance = gtk.HScale(self.balance_adjustment)
            self.balance.set_draw_value(False)
            self.pack_start(self.balance, False)

    def unrealize(self):
        channel.unrealize(self)
        self.channel = False

    def serialization_name(self):
        return main_mix_serialization_name()

def main_mix_serialization_name():
    return "main_mix_channel"
