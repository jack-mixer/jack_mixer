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
import jack_mixer_c
import sys
import gtk.glade
import os

try:
    import lash
except:
    print "Cannot load LASH python bindings, you want LASH unless you enjoy manual jack plumbing each time you use this app"
    lash = None

old_path = sys.path
sys.path.insert(0, os.path.dirname(sys.argv[0]) + os.sep + ".." + os.sep + "share"+ os.sep + "jack_mixer")
from channel import *
import gui
sys.path = old_path


# no need for serialization if there is no LASH available
if lash:
    from serialization_xml import xml_serialization
    from serialization import serialized_object, serializator

class jack_mixer(serialized_object):
    def __init__(self, name, lash_client):
        self.mixer = jack_mixer_c.create(name)
        if not self.mixer:
            return

        if lash_client:
            # Send our client name to server
            lash_event = lash.lash_event_new_with_type(lash.LASH_Client_Name)
            lash.lash_event_set_string(lash_event, name)
            lash.lash_send_event(lash_client, lash_event)

            lash.lash_jack_client_name(lash_client, name)

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title(name)

        self.gui_factory = gui.factory(glade_xml, self.window, meter_scales, slider_scales)

        self.vbox_top = gtk.VBox()
        self.window.add(self.vbox_top)

        self.menubar = gtk.MenuBar()
        self.vbox_top.pack_start(self.menubar, False)

        self.channels_menu_item = gtk.MenuItem("_Channel")
        self.menubar.append(self.channels_menu_item)

        self.settings_menu_item = gtk.MenuItem("_Settings")
        self.menubar.append(self.settings_menu_item)

        self.window.set_size_request(120,300)

        self.channels_menu = gtk.Menu()
        self.channels_menu_item.set_submenu(self.channels_menu)

        self.channel_add_menu_item = gtk.ImageMenuItem(gtk.STOCK_ADD)
        self.channels_menu.append(self.channel_add_menu_item)
        self.channel_add_menu_item.connect("activate", self.on_add_channel)

        self.channel_remove_menu_item = gtk.ImageMenuItem(gtk.STOCK_REMOVE)
        self.channels_menu.append(self.channel_remove_menu_item)

        self.channel_remove_menu = gtk.Menu()
        self.channel_remove_menu_item.set_submenu(self.channel_remove_menu)

        self.channel_remove_all_menu_item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
        self.channels_menu.append(self.channel_remove_all_menu_item)
        self.channel_remove_all_menu_item.connect("activate", self.on_channels_clear)

        self.settings_menu = gtk.Menu()
        self.settings_menu_item.set_submenu(self.settings_menu)

        self.settings_choose_meter_scale_menu_item = gtk.MenuItem("_Meter scale")
        self.settings_choose_meter_scale_menu_item.connect("activate", self.on_choose_meter_scale)
        self.settings_menu.append(self.settings_choose_meter_scale_menu_item)

        self.settings_choose_slider_scale_menu_item = gtk.MenuItem("_Slider scale")
        self.settings_choose_slider_scale_menu_item.connect("activate", self.on_choose_slider_scale)
        self.settings_menu.append(self.settings_choose_slider_scale_menu_item)

        self.hbox_top = gtk.HBox()
        self.vbox_top.pack_start(self.hbox_top, True)

        self.scrolled_window = gtk.ScrolledWindow()
        self.hbox_top.pack_start(self.scrolled_window, True)

        self.hbox_inputs = gtk.HBox()
        self.hbox_inputs.set_spacing(0)
        self.hbox_inputs.set_border_width(0)
        self.hbox_top.set_spacing(0)
        self.hbox_top.set_border_width(0)
        self.channels = []

        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled_window.add_with_viewport(self.hbox_inputs)

        self.main_mix = main_mix(self.mixer, self.gui_factory)
        self.main_mix.realize()
        frame = gtk.Frame()
        frame.add(self.main_mix)
        self.hbox_top.pack_start(frame, False)

        self.window.connect("destroy", gtk.main_quit)

        gobject.timeout_add(80, self.read_meters)
        self.lash_client = lash_client

        if lash_client:
            gobject.timeout_add(1000, self.lash_check_events)

        gobject.timeout_add(100, self.midi_change_check)

    def cleanup(self):
        print "Cleaning jack_mixer"
        if not self.mixer:
            return

        for channel in self.channels:
            channel.unrealize()

        jack_mixer_c.destroy(self.mixer)

    def on_choose_meter_scale(self, widget):
        self.gui_factory.run_dialog_choose_meter_scale()

    def on_choose_slider_scale(self, widget):
        self.gui_factory.run_dialog_choose_slider_scale()

    def on_add_channel(self, widget):
        result = self.gui_factory.run_dialog_add_channel()
        if result:
            self.add_channel(result['name'], result['stereo'])
            self.window.show_all()

    def on_remove_channel(self, widget, channel, channel_remove_menu_item):
        print 'Removing channel "%s"' % channel.channel_name
        self.channel_remove_menu.remove(channel_remove_menu_item)
        for i in range(len(self.channels)):
            if self.channels[i] is channel:
                channel.unrealize()
                del self.channels[i]
                self.hbox_inputs.remove(channel.parent)
                break
        if len(self.channels) == 0:
            self.channel_remove_menu_item.set_sensitive(False)

    def on_channels_clear(self, widget):
        for channel in self.channels:
            channel.unrealize()
            self.hbox_inputs.remove(channel.parent)
        self.channels = []
        self.channel_remove_menu = gtk.Menu()
        self.channel_remove_menu_item.set_submenu(self.channel_remove_menu)
        self.channel_remove_menu_item.set_sensitive(False)

    def add_channel(self, name, stereo):
        try:
            channel = input_channel(self.mixer, self.gui_factory, name, stereo)
            self.add_channel_precreated(channel)
        except Exception:
            err = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, "Channel creation failed")
            err.run()
            err.destroy()

    def add_channel_precreated(self, channel):
        frame = gtk.Frame()
        frame.add(channel)
        self.hbox_inputs.pack_start(frame, False)
        channel.realize()
        channel_remove_menu_item = gtk.MenuItem(channel.channel_name)
        self.channel_remove_menu.append(channel_remove_menu_item)
        channel_remove_menu_item.connect("activate", self.on_remove_channel, channel, channel_remove_menu_item)
        self.channel_remove_menu_item.set_sensitive(True)
        self.channels.append(channel)

    def read_meters(self):
        for channel in self.channels:
            channel.read_meter()
        self.main_mix.read_meter()
        return True

    def midi_change_check(self):
        for channel in self.channels:
            channel.midi_change_check()
        self.main_mix.midi_change_check()
        return True

    def lash_check_events(self):
        while lash.lash_get_pending_event_count(self.lash_client):
            event = lash.lash_get_event(self.lash_client)

            #print repr(event)

            event_type = lash.lash_event_get_type(event)
            if event_type == lash.LASH_Quit:
                print "jack_mixer: LASH ordered quit."
                gtk.main_quit()
                return False
            elif event_type == lash.LASH_Save_File:
                directory = lash.lash_event_get_string(event)
                print "jack_mixer: LASH ordered to save data in directory %s" % directory
                filename = directory + os.sep + "jack_mixer.xml"
                f = file(filename, "w")
                self.save_to_xml(f)
                f.close()
                lash.lash_send_event(self.lash_client, event) # we crash with double free
            elif event_type == lash.LASH_Restore_File:
                directory = lash.lash_event_get_string(event)
                print "jack_mixer: LASH ordered to restore data from directory %s" % directory
                filename = directory + os.sep + "jack_mixer.xml"
                f = file(filename, "r")
                self.load_from_xml(f)
                f.close()
                lash.lash_send_event(self.lash_client, event)
            else:
                print "jack_mixer: Got unhandled LASH event, type " + str(event_type)
                return True

            #lash.lash_event_destroy(event)

        return True

    def save_to_xml(self, file):
        #print "Saving to XML..."
        b = xml_serialization()
        s = serializator()
        s.serialize(self, b)
        b.save(file)

    def load_from_xml(self, file):
        #print "Loading from XML..."
        self.on_channels_clear(None)
        self.unserialized_channels = []
        b = xml_serialization()
        b.load(file)
        s = serializator()
        s.unserialize(self, b)
        for channel in self.unserialized_channels:
            self.add_channel_precreated(channel)
        del self.unserialized_channels
        self.window.show_all()

    def serialize(self, object_backend):
        pass

    def unserialize_property(self, name, value):
        pass

    def unserialize_child(self, name):
        if name == main_mix_serialization_name():
            return self.main_mix

        if name == input_channel_serialization_name():
            channel = input_channel(self.mixer, self.gui_factory, "", True)
            self.unserialized_channels.append(channel)
            return channel

    def serialization_get_childs(self):
        '''Get child objects tha required and support serialization'''
        childs = self.channels[:]
        childs.append(self.main_mix)
        return childs

    def serialization_name(self):
        return "jack_mixer"

    def main(self):
        if not self.mixer:
            return

        self.window.show_all()

        gtk.main()

        #f = file("/dev/stdout", "w")
        #self.save_to_xml(f)
        #f.close

def help():
    print "Usage: %s [mixer_name]" % sys.argv[0]

def main():
    if lash:                        # If LASH python bindings are available
        # sys.argv is modified by this call
        lash_client = lash.init(sys.argv, "jack_mixer", lash.LASH_Config_File)
    else:
        lash_client = None

    # check arguments
    args = sys.argv[1:]
    i = len(args)
    for arg in reversed(args):
        i -= 1
        if len(arg) != 0 and arg[0] == '-':
            if arg == "--help":
                help()
                return
            else:
                print 'Unknown option "%s"' % args[i]
                help()
                return
            del args[i]
    #    else:
    #        print 'Non option argument "%s"' % args[i]

    # Yeah , this sounds stupid, we connected earlier, but we dont want to show this if we got --help option
    # This issue should be fixed in pylash, there is a reason for having two functions for initialization after all
    if lash_client:
        print "Successfully connected to LASH server at " +  lash.lash_get_server_name(lash_client)

    if len(args) == 1:
        name = args[0]
    else:
        name = None

    if not name:
        name = "jack_mixer-%u" % os.getpid()

    mixer = jack_mixer(name, lash_client)

    mixer.main()

    mixer.cleanup()

glade_dir = os.path.dirname(sys.argv[0])

# since ppl tend to run "python jack_mixer.py", lets assume that it is in current directory
# "python ./jack_mixer.py" and "./jack_mixer.py" will work anyway.
if not glade_dir:
    glade_dir = "."

glade_file = glade_dir + os.sep + "jack_mixer.glade"

if not os.path.isfile(glade_file):
    glade_file = glade_dir + os.sep + ".." + os.sep + "share"+ os.sep + "jack_mixer" + os.sep + "jack_mixer.glade"

#print 'Loading glade from "%s"' % glade_file

glade_xml = gtk.glade.XML(glade_file)

# scales suitable as meter scales
meter_scales = [scale.iec_268(), scale.linear_70dB(), scale.iec_268_minimalistic()]

# scales suitable as volume slider scales
slider_scales = [scale.linear_30dB(), scale.linear_70dB()]

if __name__ == "__main__":
    main()
