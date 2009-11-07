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

from optparse import OptionParser

import gtk
import gobject
import jack_mixer_c
import sys
import os

try:
    import lash
except:
    lash = None

old_path = sys.path
sys.path.insert(0, os.path.dirname(sys.argv[0]) + os.sep + ".." + os.sep + "share"+ os.sep + "jack_mixer")
from channel import *
import gui
from preferences import PreferencesDialog

sys.path = old_path

try:
    from serialization_xml import xml_serialization
    from serialization import serialized_object, serializator
except ImportError:
    xml_serialization = None

if lash is None or xml_serialization is None:
    print >> sys.stderr, "Cannot load LASH python bindings or python-xml, you want them unless you enjoy manual jack plumbing each time you use this app"

class jack_mixer(serialized_object):

    # scales suitable as meter scales
    meter_scales = [scale.iec_268(), scale.linear_70dB(), scale.iec_268_minimalistic()]

    # scales suitable as volume slider scales
    slider_scales = [scale.linear_30dB(), scale.linear_70dB()]

    # name of settngs file that is currently open
    current_filename = None

    def __init__(self, name, lash_client):
        self.mixer = jack_mixer_c.Mixer(name)
        if not self.mixer:
            return

        if lash_client:
            # Send our client name to server
            lash_event = lash.lash_event_new_with_type(lash.LASH_Client_Name)
            lash.lash_event_set_string(lash_event, name)
            lash.lash_send_event(lash_client, lash_event)

            lash.lash_jack_client_name(lash_client, name)

        gtk.window_set_default_icon_name('jack_mixer')

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title(name)

        self.gui_factory = gui.factory(self.window, self.meter_scales, self.slider_scales)

        self.vbox_top = gtk.VBox()
        self.window.add(self.vbox_top)

        self.menubar = gtk.MenuBar()
        self.vbox_top.pack_start(self.menubar, False)

        mixer_menu_item = gtk.MenuItem("_Mixer")
        self.menubar.append(mixer_menu_item)
        edit_menu_item = gtk.MenuItem('_Edit')
        self.menubar.append(edit_menu_item)

        self.window.set_default_size(120,300)

        mixer_menu = gtk.Menu()
        mixer_menu_item.set_submenu(mixer_menu)

        add_input_channel = gtk.ImageMenuItem('New _Input Channel')
        mixer_menu.append(add_input_channel)
        add_input_channel.connect("activate", self.on_add_input_channel)

        add_output_channel = gtk.ImageMenuItem('New _Output Channel')
        mixer_menu.append(add_output_channel)
        add_output_channel.connect("activate", self.on_add_output_channel)

        if lash_client is None and xml_serialization is not None:
            mixer_menu.append(gtk.SeparatorMenuItem())
            open = gtk.ImageMenuItem(gtk.STOCK_OPEN)
            mixer_menu.append(open)
            open.connect('activate', self.on_open_cb)
            save = gtk.ImageMenuItem(gtk.STOCK_SAVE)
            mixer_menu.append(save)
            save.connect('activate', self.on_save_cb)
            save_as = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
            mixer_menu.append(save_as)
            save_as.connect('activate', self.on_save_as_cb)

        mixer_menu.append(gtk.SeparatorMenuItem())

        quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        mixer_menu.append(quit)
        quit.connect('activate', self.on_quit_cb)

        edit_menu = gtk.Menu()
        edit_menu_item.set_submenu(edit_menu)

        self.channel_remove_menu_item = gtk.ImageMenuItem(gtk.STOCK_REMOVE)
        edit_menu.append(self.channel_remove_menu_item)
        self.channel_remove_menu = gtk.Menu()
        self.channel_remove_menu_item.set_submenu(self.channel_remove_menu)

        channel_remove_all_menu_item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
        edit_menu.append(channel_remove_all_menu_item)
        channel_remove_all_menu_item.connect("activate", self.on_channels_clear)

        edit_menu.append(gtk.SeparatorMenuItem())

        preferences = gtk.ImageMenuItem(gtk.STOCK_PREFERENCES)
        preferences.connect('activate', self.on_preferences_cb)
        edit_menu.append(preferences)

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
        self.output_channels = []

        self.scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scrolled_window.add_with_viewport(self.hbox_inputs)

        self.main_mix = main_mix(self)
        self.main_mix.realize()
        self.hbox_outputs = gtk.HBox()
        self.hbox_outputs.set_spacing(0)
        self.hbox_outputs.set_border_width(0)
        frame = gtk.Frame()
        frame.add(self.main_mix)
        self.hbox_outputs.pack_start(frame, False)
        self.hbox_top.pack_start(self.hbox_outputs, False)

        self.window.connect("destroy", gtk.main_quit)

        gobject.timeout_add(80, self.read_meters)
        self.lash_client = lash_client

        if lash_client:
            gobject.timeout_add(1000, self.lash_check_events)

    def cleanup(self):
        print "Cleaning jack_mixer"
        if not self.mixer:
            return

        for channel in self.channels:
            channel.unrealize()

    def on_open_cb(self, *args):
        dlg = gtk.FileChooserDialog(title='Open', parent=self.window,
                        action=gtk.FILE_CHOOSER_ACTION_OPEN,
                        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        if dlg.run() == gtk.RESPONSE_OK:
            filename = dlg.get_filename()
            try:
                f = file(filename, 'r')
                self.load_from_xml(f)
            except:
                # TODO: display error in a dialog box
                print >> sys.stderr, 'Failed to read', filename
            else:
                self.current_filename = filename
            finally:
                f.close()
        dlg.destroy()

    def on_save_cb(self, *args):
        if not self.current_filename:
            return self.on_save_as_cb()
        f = file(self.current_filename, 'w')
        self.save_to_xml(f)
        f.close()

    def on_save_as_cb(self, *args):
        dlg = gtk.FileChooserDialog(title='Save', parent=self.window,
                        action=gtk.FILE_CHOOSER_ACTION_SAVE,
                        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        dlg.set_default_response(gtk.RESPONSE_OK)
        if dlg.run() == gtk.RESPONSE_OK:
            self.current_filename = dlg.get_filename()
            self.on_save_cb()
        dlg.destroy()

    def on_quit_cb(self, *args):
        gtk.main_quit()

    preferences_dialog = None
    def on_preferences_cb(self, widget):
        if not self.preferences_dialog:
            self.preferences_dialog = PreferencesDialog(self)
        self.preferences_dialog.show()
        self.preferences_dialog.present()

    def on_add_input_channel(self, widget):
        dialog = NewChannelDialog(parent=self.window, mixer=self.mixer)
        dialog.set_transient_for(self.window)
        dialog.show()
        ret = dialog.run()
        dialog.hide()

        if ret == gtk.RESPONSE_OK:
            result = dialog.get_result()
            channel = self.add_channel(**result)
            self.window.show_all()

    def on_add_output_channel(self, widget):
        dialog = NewOutputChannelDialog(parent=self.window, mixer=self.mixer)
        dialog.set_transient_for(self.window)
        dialog.show()
        ret = dialog.run()
        dialog.hide()

        if ret == gtk.RESPONSE_OK:
            result = dialog.get_result()
            channel = self.add_output_channel(**result)
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

    def add_channel(self, name, stereo, volume_cc, balance_cc):
        try:
            channel = input_channel(self, name, stereo)
            self.add_channel_precreated(channel)
        except Exception:
            err = gtk.MessageDialog(self.window,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_ERROR,
                            gtk.BUTTONS_OK,
                            "Channel creation failed")
            err.run()
            err.destroy()
            return
        if volume_cc:
            channel.channel.volume_midi_cc = int(volume_cc)
        if balance_cc:
            channel.channel.balance_midi_cc = int(balance_cc)
        if not (volume_cc or balance_cc):
            channel.channel.autoset_midi_cc()
        channel.output_channel = self.mixer.add_output_channel(name + ' Out', stereo, True)
        channel.output_channel.volume = 0
        channel.output_channel.set_solo(channel.channel, True)
        return channel

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

        for outputchannel in self.output_channels:
            channel.add_control_group(outputchannel)

    def read_meters(self):
        for channel in self.channels:
            channel.read_meter()
        self.main_mix.read_meter()
        return True

    def add_output_channel(self, name, stereo, volume_cc, balance_cc):
        try:
            channel = output_channel(self, name, stereo)
            self.add_output_channel_precreated(channel)
        except Exception:
            raise
            err = gtk.MessageDialog(self.window,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_ERROR,
                            gtk.BUTTONS_OK,
                            "Channel creation failed")
            err.run()
            err.destroy()
            return
        if volume_cc:
            channel.channel.volume_midi_cc = int(volume_cc)
        if balance_cc:
            channel.channel.balance_midi_cc = int(balance_cc)
        return channel

    def add_output_channel_precreated(self, channel):
        frame = gtk.Frame()
        frame.add(channel)
        self.hbox_outputs.pack_start(frame, False)
        channel.realize()
        # XXX: handle deletion of output channels
        #channel_remove_menu_item = gtk.MenuItem(channel.channel_name)
        #self.channel_remove_menu.append(channel_remove_menu_item)
        #channel_remove_menu_item.connect("activate", self.on_remove_channel, channel, channel_remove_menu_item)
        #self.channel_remove_menu_item.set_sensitive(True)
        self.output_channels.append(channel)

        # add group controls to the input channels
        for inputchannel in self.channels:
            inputchannel.add_control_group(channel)

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
            if isinstance(channel, input_channel):
                self.add_channel_precreated(channel)
            else:
                self.add_output_channel_precreated(channel)
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
            channel = input_channel(self, "", True)
            self.unserialized_channels.append(channel)
            return channel

        if name == output_channel_serialization_name():
            channel = output_channel(self, "", True)
            self.unserialized_channels.append(channel)
            return channel

    def serialization_get_childs(self):
        '''Get child objects tha required and support serialization'''
        childs = self.channels[:] + self.output_channels[:]
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

    parser = OptionParser()
    parser.add_option('-c', '--config', dest='config')
    options, args = parser.parse_args()

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

    gtk.gdk.threads_init()
    mixer = jack_mixer(name, lash_client)
    if options.config:
        f = file(options.config)
        mixer.current_filename = options.config
        mixer.load_from_xml(f)
        mixer.window.set_default_size(60*(1+len(mixer.channels)+len(mixer.output_channels)),300)
        f.close()

    mixer.main()

    mixer.cleanup()

if __name__ == "__main__":
    main()
