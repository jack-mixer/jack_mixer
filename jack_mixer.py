#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of jack_mixer
#
# Copyright (C) 2006-2009 Nedko Arnaudov <nedko@arnaudov.name>
# Copyright (C) 2009-2020 Frederic Peters <fpeters@0d.be> et al.
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
import os
import re
import signal
import sys
from argparse import ArgumentParser

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GLib

# temporary change Python modules lookup path to look into installation
# directory ($prefix/share/jack_mixer/)
old_path = sys.path
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), '..', 'share', 'jack_mixer'))

import jack_mixer_c

import gui
import scale
from channel import InputChannel, NewInputChannelDialog, NewOutputChannelDialog, OutputChannel
from nsmclient import NSMClient
from serialization_xml import XmlSerialization
from serialization import SerializedObject, Serializator
from styling import load_css_styles
from preferences import PreferencesDialog
from version import __version__


# restore Python modules lookup path
sys.path = old_path
log = logging.getLogger("jack_mixer")


def add_number_suffix(s):
    def inc(match):
        return str(int(match.group(0)) + 1)

    new_s = re.sub('(\d+)\s*$', inc, s)
    if new_s == s:
        new_s = s + ' 1'

    return new_s


class JackMixer(SerializedObject):

    # scales suitable as meter scales
    meter_scales = [
        scale.K20(),
        scale.K14(),
        scale.IEC268(),
        scale.Linear70dB(),
        scale.IEC268Minimalistic()
    ]

    # scales suitable as volume slider scales
    slider_scales = [
        scale.Linear30dB(),
        scale.Linear70dB()
    ]

    def __init__(self, client_name='jack_mixer'):
        self.visible = False
        self.nsm_client = None
        # name of settings file that is currently open
        self.current_filename = None
        self._monitored_channel = None
        self._init_solo_channels = None

        if os.environ.get('NSM_URL'):
            self.nsm_client = NSMClient(
                prettyName="jack_mixer",
                saveCallback=self.nsm_save_cb,
                openOrNewCallback=self.nsm_open_cb,
                supportsSaveStatus=False,
                hideGUICallback=self.nsm_hide_cb,
                showGUICallback=self.nsm_show_cb,
                exitProgramCallback=self.nsm_exit_cb,
                loggingLevel="error",
            )
            self.nsm_client.announceGuiVisibility(self.visible)
        else:
            self.visible = True
            self.create_mixer(client_name, with_nsm=False)

    def create_mixer(self, client_name, with_nsm=True):
        self.mixer = jack_mixer_c.Mixer(client_name)
        if not self.mixer:
            raise RuntimeError("Failed to create Mixer instance.")

        self.create_ui(with_nsm)
        self.window.set_title(client_name)

        self.monitor_channel = self.mixer.add_output_channel("Monitor", True, True)
        self.save = False

        GLib.timeout_add(33, self.read_meters)
        GLib.timeout_add(50, self.midi_events_check)

        if with_nsm:
            GLib.timeout_add(200, self.nsm_react)

    def cleanup(self):
        log.debug("Cleaning jack_mixer.")
        if not self.mixer:
            return

        for channel in self.channels:
            channel.unrealize()

        self.mixer.destroy()

    # ---------------------------------------------------------------------------------------------
    # UI creation and (de-)initialization

    def new_menu_item(self, title, callback=None, accel=None, enabled=True):
        menuitem = Gtk.MenuItem.new_with_mnemonic(title)
        menuitem.set_sensitive(enabled)
        if callback:
            menuitem.connect("activate", callback)
        if accel:
            key, mod = Gtk.accelerator_parse(accel)
            menuitem.add_accelerator("activate", self.menu_accelgroup, key, mod,
                                     Gtk.AccelFlags.VISIBLE)
        return menuitem

    def create_ui(self, with_nsm):
        self.channels = []
        self.output_channels = []
        load_css_styles()
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_icon_name('jack_mixer')
        self.gui_factory = gui.Factory(self.window, self.meter_scales, self.slider_scales)
        self.gui_factory.connect('midi-behavior-mode-changed', self.on_midi_behavior_mode_changed)
        self.gui_factory.emit_midi_behavior_mode()

        self.vbox_top = Gtk.VBox()
        self.window.add(self.vbox_top)

        self.menu_accelgroup = Gtk.AccelGroup()
        self.window.add_accel_group(self.menu_accelgroup)

        self.menubar = Gtk.MenuBar()
        self.vbox_top.pack_start(self.menubar, False, True, 0)

        mixer_menu_item = Gtk.MenuItem.new_with_mnemonic("_Mixer")
        self.menubar.append(mixer_menu_item)
        edit_menu_item = Gtk.MenuItem.new_with_mnemonic('_Edit')
        self.menubar.append(edit_menu_item)
        help_menu_item = Gtk.MenuItem.new_with_mnemonic('_Help')
        self.menubar.append(help_menu_item)

        self.width = 420
        self.height = 420
        self.paned_position = 210
        self.window.set_default_size(self.width, self.height)

        self.mixer_menu = Gtk.Menu()
        mixer_menu_item.set_submenu(self.mixer_menu)

        self.mixer_menu.append(self.new_menu_item('New _Input Channel',
                                                  self.on_add_input_channel, "<Control>N"))
        self.mixer_menu.append(self.new_menu_item('New Output _Channel',
                                                  self.on_add_output_channel, "<Shift><Control>N"))

        self.mixer_menu.append(Gtk.SeparatorMenuItem())
        if not with_nsm:
            self.mixer_menu.append(self.new_menu_item('_Open...', self.on_open_cb, "<Control>O"))

        self.mixer_menu.append(self.new_menu_item('_Save', self.on_save_cb, "<Control>S"))

        if not with_nsm:
            self.mixer_menu.append(self.new_menu_item('Save _As...', self.on_save_as_cb,
                                                      "<Shift><Control>S"))

        self.mixer_menu.append(Gtk.SeparatorMenuItem())
        if with_nsm:
            self.mixer_menu.append(self.new_menu_item('_Hide', self.nsm_hide_cb, "<Control>W"))
        else:
            self.mixer_menu.append(self.new_menu_item('_Quit', self.on_quit_cb, "<Control>Q"))

        edit_menu = Gtk.Menu()
        edit_menu_item.set_submenu(edit_menu)

        self.channel_edit_input_menu_item = self.new_menu_item('_Edit Input Channel',
                                                               enabled=False)
        edit_menu.append(self.channel_edit_input_menu_item)
        self.channel_edit_input_menu = Gtk.Menu()
        self.channel_edit_input_menu_item.set_submenu(self.channel_edit_input_menu)

        self.channel_edit_output_menu_item = self.new_menu_item('E_dit Output Channel',
                                                                enabled=False)
        edit_menu.append(self.channel_edit_output_menu_item)
        self.channel_edit_output_menu = Gtk.Menu()
        self.channel_edit_output_menu_item.set_submenu(self.channel_edit_output_menu)

        self.channel_remove_input_menu_item = self.new_menu_item('_Remove Input Channel',
                                                                 enabled=False)
        edit_menu.append(self.channel_remove_input_menu_item)
        self.channel_remove_input_menu = Gtk.Menu()
        self.channel_remove_input_menu_item.set_submenu(self.channel_remove_input_menu)

        self.channel_remove_output_menu_item = self.new_menu_item('Re_move Output Channel',
                                                                  enabled=False)
        edit_menu.append(self.channel_remove_output_menu_item)
        self.channel_remove_output_menu = Gtk.Menu()
        self.channel_remove_output_menu_item.set_submenu(self.channel_remove_output_menu)

        edit_menu.append(Gtk.SeparatorMenuItem())
        edit_menu.append(self.new_menu_item('Shrink Channels', self.on_shrink_channels_cb,
                                            "<Control>minus"))
        edit_menu.append(self.new_menu_item('Expand Channels', self.on_expand_channels_cb,
                                            "<Control>plus"))
        edit_menu.append(Gtk.SeparatorMenuItem())

        edit_menu.append(self.new_menu_item('_Clear', self.on_channels_clear, "<Control>X"))
        edit_menu.append(Gtk.SeparatorMenuItem())

        self.preferences_dialog = None
        edit_menu.append(self.new_menu_item('_Preferences', self.on_preferences_cb, "<Control>P"))

        help_menu = Gtk.Menu()
        help_menu_item.set_submenu(help_menu)

        help_menu.append(self.new_menu_item('_About', self.on_about, "F1"))

        self.hbox_top = Gtk.HBox()
        self.vbox_top.pack_start(self.hbox_top, True, True, 0)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.hbox_inputs = Gtk.Box()
        self.hbox_inputs.set_spacing(0)
        self.hbox_inputs.set_border_width(0)
        self.hbox_top.set_spacing(0)
        self.hbox_top.set_border_width(0)
        self.scrolled_window.add(self.hbox_inputs)
        self.hbox_outputs = Gtk.Box()
        self.hbox_outputs.set_spacing(0)
        self.hbox_outputs.set_border_width(0)
        self.scrolled_output = Gtk.ScrolledWindow()
        self.scrolled_output.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_output.add(self.hbox_outputs)
        self.paned = Gtk.HPaned()
        self.paned.set_wide_handle(True)
        self.hbox_top.pack_start(self.paned, True, True, 0)
        self.paned.pack1(self.scrolled_window, True, False)
        self.paned.pack2(self.scrolled_output, True, False)

        self.window.connect("destroy", Gtk.main_quit)
        self.window.connect('delete-event', self.on_delete_event)

    # ---------------------------------------------------------------------------------------------
    # Channel creation

    def add_channel(self, name, stereo, volume_cc, balance_cc, mute_cc, solo_cc, value):
        try:
            channel = InputChannel(self, name, stereo, value)
            self.add_channel_precreated(channel)
        except Exception:
            error_dialog(self.window, "Input channel creation failed.")
            return

        channel.assign_midi_ccs(volume_cc, balance_cc, mute_cc, solo_cc)
        return channel

    def add_channel_precreated(self, channel):
        frame = Gtk.Frame()
        frame.add(channel)
        self.hbox_inputs.pack_start(frame, False, True, 0)
        channel.realize()

        channel_edit_menu_item = Gtk.MenuItem(label=channel.channel_name)
        self.channel_edit_input_menu.append(channel_edit_menu_item)
        channel_edit_menu_item.connect("activate", self.on_edit_input_channel, channel)
        self.channel_edit_input_menu_item.set_sensitive(True)

        channel_remove_menu_item = Gtk.MenuItem(label=channel.channel_name)
        self.channel_remove_input_menu.append(channel_remove_menu_item)
        channel_remove_menu_item.connect("activate", self.on_remove_input_channel, channel)
        self.channel_remove_input_menu_item.set_sensitive(True)

        self.channels.append(channel)

        for outputchannel in self.output_channels:
            channel.add_control_group(outputchannel)

        # create post fader output channel matching the input channel
        channel.post_fader_output_channel = self.mixer.add_output_channel(
                        channel.channel.name + ' Out', channel.channel.is_stereo, True)
        channel.post_fader_output_channel.volume = 0
        channel.post_fader_output_channel.set_solo(channel.channel, True)

        channel.connect('input-channel-order-changed', self.on_input_channel_order_changed)

    def add_output_channel(self, name, stereo, volume_cc, balance_cc, mute_cc,
                           display_solo_buttons, color, value):
        try:
            channel = OutputChannel(self, name, stereo, value)
            channel.display_solo_buttons = display_solo_buttons
            channel.color = color
            self.add_output_channel_precreated(channel)
        except Exception:
            error_dialog(self.window, "Output channel creation failed")
            return

        channel.assign_midi_ccs(volume_cc, balance_cc, mute_cc)
        return channel

    def add_output_channel_precreated(self, channel):
        frame = Gtk.Frame()
        frame.add(channel)
        self.hbox_outputs.pack_end(frame, False, True, 0)
        self.hbox_outputs.reorder_child(frame, 0)
        channel.realize()

        channel_edit_menu_item = Gtk.MenuItem(label=channel.channel_name)
        self.channel_edit_output_menu.append(channel_edit_menu_item)
        channel_edit_menu_item.connect("activate", self.on_edit_output_channel, channel)
        self.channel_edit_output_menu_item.set_sensitive(True)

        channel_remove_menu_item = Gtk.MenuItem(label=channel.channel_name)
        self.channel_remove_output_menu.append(channel_remove_menu_item)
        channel_remove_menu_item.connect("activate", self.on_remove_output_channel, channel)
        self.channel_remove_output_menu_item.set_sensitive(True)

        self.output_channels.append(channel)
        channel.connect('output-channel-order-changed', self.on_output_channel_order_changed)

    # ---------------------------------------------------------------------------------------------
    # Signal/event handlers

    # ---------------------------------------------------------------------------------------------
    # NSM

    def nsm_react(self):
        self.nsm_client.reactToMessage()
        return True

    def nsm_hide_cb(self, *args):
        self.window.hide()
        self.visible = False
        self.nsm_client.announceGuiVisibility(False)

    def nsm_show_cb(self):
        width, height = self.window.get_size()
        self.window.show_all()
        self.paned.set_position(self.paned_position/self.width*width)

        self.visible = True
        self.nsm_client.announceGuiVisibility(True)

    def nsm_open_cb(self, path, session_name, client_name):
        self.create_mixer(client_name, with_nsm=True)
        self.current_filename = path + '.xml'
        if os.path.isfile(self.current_filename):
            try:
                with open(self.current_filename, 'r') as fp:
                    self.load_from_xml(fp, from_nsm=True)
            except Exception as exc:
                # Re-raise with more meaningful error message
                raise IOError("Error loading settings file '{}': {}".format(
                              self.current_filename, exc))

    def nsm_save_cb(self, path, session_name, client_name):
        self.current_filename = path + '.xml'
        f = open(self.current_filename, 'w')
        self.save_to_xml(f)
        f.close()

    def nsm_exit_cb(self, path, session_name, client_name):
        Gtk.main_quit()

    # ---------------------------------------------------------------------------------------------
    # POSIX signals

    def sighandler(self, signum, frame):
        log.debug("Signal %d received.", signum)
        if signum == signal.SIGUSR1:
            self.save = True
        elif signum == signal.SIGTERM:
            self.on_quit_cb()
        elif signum == signal.SIGINT:
            self.on_quit_cb()
        else:
            log.warning("Unknown signal %d received.", signum)

    # ---------------------------------------------------------------------------------------------
    # GTK signals

    def on_about(self, *args):
        about = Gtk.AboutDialog()
        about.set_name('jack_mixer')
        about.set_program_name('jack_mixer')
        about.set_copyright('Copyright © 2006-2020\n'
                            'Nedko Arnaudov, Frédéric Péters, Arnout Engelen, Daniel Sheeler')
        about.set_license("""\
jack_mixer is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

jack_mixer is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along
with jack_mixer; if not, write to the Free Software Foundation, Inc., 51
Franklin Street, Fifth Floor, Boston, MA 02110-130159 USA""")
        about.set_authors([
            'Nedko Arnaudov <nedko@arnaudov.name>',
            'Christopher Arndt <chris@chrisarndt.de>',
            'Arnout Engelen <arnouten@bzzt.net>',
            'John Hedges <john@drystone.co.uk>',
            'Olivier Humbert <trebmuh@tuxfamily.org>',
            'Sarah Mischke <sarah@spooky-online.de>',
            'Frédéric Péters <fpeters@0d.be>',
            'Daniel Sheeler <dsheeler@pobox.com>',
            'Athanasios Silis <athanasios.silis@gmail.com>',
        ])
        about.set_logo_icon_name('jack_mixer')
        about.set_version(__version__)
        about.set_website('https://rdio.space/jackmixer/')
        about.run()
        about.destroy()

    def on_delete_event(self, widget, event):
        if self.nsm_client:
            self.nsm_hide_cb()
            return True

        return self.on_quit_cb()

    def on_open_cb(self, *args):
        dlg = Gtk.FileChooserDialog(title='Open', parent=self.window,
                        action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            filename = dlg.get_filename()
            try:
                with open(filename, 'r') as fp:
                    self.load_from_xml(fp)
            except Exception as exc:
                error_dialog(self.window, "Error loading settings file '%s': %s", filename, exc)
            else:
                self.current_filename = filename
        dlg.destroy()

    def on_save_cb(self, *args):
        if not self.current_filename:
            return self.on_save_as_cb()
        f = open(self.current_filename, 'w')
        self.save_to_xml(f)
        f.close()

    def on_save_as_cb(self, *args):
        dlg = Gtk.FileChooserDialog(title='Save', parent=self.window,
                        action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            self.current_filename = dlg.get_filename()
            self.on_save_cb()
        dlg.destroy()

    def on_quit_cb(self, *args):
        if not self.nsm_client and self.gui_factory.get_confirm_quit():
            dlg = Gtk.MessageDialog(parent=self.window,
                                    message_type=Gtk.MessageType.QUESTION,
                                    buttons=Gtk.ButtonsType.NONE)
            dlg.set_markup("<b>Quit application?</b>")
            dlg.format_secondary_markup("All jack_mixer ports will be closed and connections lost,"
                                        "\nstopping all sound going through jack_mixer.\n\n"
                                        "Are you sure?")
            dlg.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_QUIT, Gtk.ResponseType.OK
            )
            response = dlg.run()
            dlg.destroy()
            if response != Gtk.ResponseType.OK:
                return True

        Gtk.main_quit()

    def on_shrink_channels_cb(self, widget):
        for channel in self.channels + self.output_channels:
            channel.narrow()

    def on_expand_channels_cb(self, widget):
        for channel in self.channels + self.output_channels:
            channel.widen()

    def on_midi_behavior_mode_changed(self, gui_factory, value):
        self.mixer.midi_behavior_mode = value

    def on_preferences_cb(self, widget):
        if not self.preferences_dialog:
            self.preferences_dialog = PreferencesDialog(self)
        self.preferences_dialog.show()
        self.preferences_dialog.present()

    def on_add_channel(self, inout="input", default_name="Input"):
        dialog = getattr(self, '_add_{}_dialog'.format(inout), None)
        values = getattr(self, '_add_{}_values'.format(inout), {})

        if dialog == None:
            cls = NewInputChannelDialog if inout == 'input' else NewOutputChannelDialog
            dialog = cls(app=self)
            setattr(self, '_add_{}_dialog'.format(inout), dialog)

        names = {ch.channel_name
                 for ch in (self.channels if inout == 'input' else self.output_channels)}
        values.setdefault('name', default_name)
        while True:
            if values['name'] in names:
                values['name'] = add_number_suffix(values['name'])
            else:
                break

        dialog.fill_ui(**values)
        dialog.set_transient_for(self.window)
        dialog.show()
        ret = dialog.run()
        dialog.hide()

        if ret == Gtk.ResponseType.OK:
            result = dialog.get_result()
            setattr(self, '_add_{}_values'.format(inout), result)
            method = getattr(self, 'add_channel' if inout == 'input' else 'add_output_channel')
            channel = method(**result)
            if self.visible or self.nsm_client == None:
                self.window.show_all()

    def on_add_input_channel(self, widget):
        return self.on_add_channel("input", "Input")

    def on_add_output_channel(self, widget):
        return self.on_add_channel("output", "Output")

    def on_edit_input_channel(self, widget, channel):
        log.debug('Editing input channel "%s".', channel.channel_name)
        channel.on_channel_properties()

    def on_remove_input_channel(self, widget, channel):
        log.debug('Removing input channel "%s".', channel.channel_name)

        def remove_channel_edit_input_menuitem_by_label(widget, label):
            if widget.get_label() == label:
                self.channel_edit_input_menu.remove(widget)

        self.channel_remove_input_menu.remove(widget)
        self.channel_edit_input_menu.foreach(
            remove_channel_edit_input_menuitem_by_label,
            channel.channel_name)

        if self.monitored_channel is channel:
            channel.monitor_button.set_active(False)

        for i in range(len(self.channels)):
            if self.channels[i] is channel:
                channel.unrealize()
                del self.channels[i]
                self.hbox_inputs.remove(channel.get_parent())
                break

        if not self.channels:
            self.channel_edit_input_menu_item.set_sensitive(False)
            self.channel_remove_input_menu_item.set_sensitive(False)

    def on_edit_output_channel(self, widget, channel):
        log.debug('Editing output channel "%s".', channel.channel_name)
        channel.on_channel_properties()

    def on_remove_output_channel(self, widget, channel):
        log.debug('Removing output channel "%s".', channel.channel_name)

        def remove_channel_edit_output_menuitem_by_label(widget, label):
            if widget.get_label() == label:
                self.channel_edit_output_menu.remove(widget)

        self.channel_remove_output_menu.remove(widget)
        self.channel_edit_output_menu.foreach(
            remove_channel_edit_output_menuitem_by_label,
            channel.channel_name);

        if self.monitored_channel is channel:
            channel.monitor_button.set_active(False)

        for i in range(len(self.channels)):
            if self.output_channels[i] is channel:
                channel.unrealize()
                del self.output_channels[i]
                self.hbox_outputs.remove(channel.get_parent())
                break

        if not self.output_channels:
            self.channel_edit_output_menu_item.set_sensitive(False)
            self.channel_remove_output_menu_item.set_sensitive(False)

    def on_channel_rename(self, oldname, newname):
        def rename_channels(container, parameters):
            if container.get_label() == parameters['oldname']:
                container.set_label(parameters['newname'])

        rename_parameters = {'oldname': oldname, 'newname': newname}
        self.channel_edit_input_menu.foreach(rename_channels, rename_parameters)
        self.channel_edit_output_menu.foreach(rename_channels, rename_parameters)
        self.channel_remove_input_menu.foreach(rename_channels, rename_parameters)
        self.channel_remove_output_menu.foreach(rename_channels, rename_parameters)
        log.debug('Renaming channel from "%s" to "%s".', oldname, newname)

    def on_input_channel_order_changed(self, widget, source_name, dest_name):
        self.channels.clear()

        channel_box = self.hbox_inputs
        frames = channel_box.get_children()

        for f in frames:
            c = f.get_child()
            if source_name == c._channel_name:
                source_frame = f
                break

        for f in frames:
            c = f.get_child()
            if (dest_name == c._channel_name):
                pos = frames.index(f)
                channel_box.reorder_child(source_frame, pos)
                break

        for frame in self.hbox_inputs.get_children():
            c = frame.get_child()
            self.channels.append(c)

    def on_output_channel_order_changed(self, widget, source_name, dest_name):
        self.output_channels.clear()
        channel_box = self.hbox_outputs

        frames = channel_box.get_children()

        for f in frames:
            c = f.get_child()
            if source_name == c._channel_name:
                 source_frame = f
                 break

        for f in frames:
            c = f.get_child()
            if (dest_name == c._channel_name):
                pos = len(frames) - 1 - frames.index(f)
                channel_box.reorder_child(source_frame, pos)
                break

        for frame in self.hbox_outputs.get_children():
            c = frame.get_child()
            self.output_channels.append(c)

    def on_channels_clear(self, widget):
        dlg = Gtk.MessageDialog(parent = self.window,
                modal = True,
                message_type = Gtk.MessageType.WARNING,
                text = "Are you sure you want to clear all channels?",
                buttons = Gtk.ButtonsType.OK_CANCEL)
        if not widget or dlg.run() == Gtk.ResponseType.OK:
            for channel in self.output_channels:
                channel.unrealize()
                self.hbox_outputs.remove(channel.get_parent())
            for channel in self.channels:
                channel.unrealize()
                self.hbox_inputs.remove(channel.get_parent())
            self.channels = []
            self.output_channels = []
            self.channel_edit_input_menu = Gtk.Menu()
            self.channel_edit_input_menu_item.set_submenu(self.channel_edit_input_menu)
            self.channel_edit_input_menu_item.set_sensitive(False)
            self.channel_remove_input_menu = Gtk.Menu()
            self.channel_remove_input_menu_item.set_submenu(self.channel_remove_input_menu)
            self.channel_remove_input_menu_item.set_sensitive(False)
            self.channel_edit_output_menu = Gtk.Menu()
            self.channel_edit_output_menu_item.set_submenu(self.channel_edit_output_menu)
            self.channel_edit_output_menu_item.set_sensitive(False)
            self.channel_remove_output_menu = Gtk.Menu()
            self.channel_remove_output_menu_item.set_submenu(self.channel_remove_output_menu)
            self.channel_remove_output_menu_item.set_sensitive(False)
        dlg.destroy()

    def read_meters(self):
        for channel in self.channels:
            channel.read_meter()
        for channel in self.output_channels:
            channel.read_meter()
        return True

    def midi_events_check(self):
        for channel in self.channels + self.output_channels:
            channel.midi_events_check()
        return True

    def get_monitored_channel(self):
        return self._monitored_channel

    def set_monitored_channel(self, channel):
        if self._monitored_channel:
            if channel.channel.name == self._monitored_channel.channel.name:
                return
        self._monitored_channel = channel
        if type(channel) is InputChannel:
            # reset all solo/mute settings
            for in_channel in self.channels:
                self.monitor_channel.set_solo(in_channel.channel, False)
                self.monitor_channel.set_muted(in_channel.channel, False)
            self.monitor_channel.set_solo(channel.channel, True)
            self.monitor_channel.prefader = True
        else:
            self.monitor_channel.prefader = False
        self.update_monitor(channel)
    monitored_channel = property(get_monitored_channel, set_monitored_channel)

    def update_monitor(self, channel):
        if self._monitored_channel is not channel:
            return
        self.monitor_channel.volume = channel.channel.volume
        self.monitor_channel.balance = channel.channel.balance
        if type(self.monitored_channel) is OutputChannel:
            # sync solo/muted channels
            for input_channel in self.channels:
                self.monitor_channel.set_solo(input_channel.channel,
                                channel.channel.is_solo(input_channel.channel))
                self.monitor_channel.set_muted(input_channel.channel,
                                channel.channel.is_muted(input_channel.channel))

    def get_input_channel_by_name(self, name):
        for input_channel in self.channels:
            if input_channel.channel.name == name:
                return input_channel
        return None

    # ---------------------------------------------------------------------------------------------
    # Mixer settings (de-)serialization and file handling

    def save_to_xml(self, file):
        log.debug("Saving to XML...")
        b = XmlSerialization()
        s = Serializator()
        s.serialize(self, b)
        b.save(file)

    def load_from_xml(self, file, silence_errors=False, from_nsm=False):
        log.debug("Loading from XML...")
        self.unserialized_channels = []
        b = XmlSerialization()
        try:
            b.load(file)
        except:
            if silence_errors:
                return
            raise
        self.on_channels_clear(None)
        s = Serializator()
        s.unserialize(self, b)
        for channel in self.unserialized_channels:
            if isinstance(channel, InputChannel):
                if self._init_solo_channels and channel.channel_name in self._init_solo_channels:
                    channel.solo = True
                self.add_channel_precreated(channel)
        self._init_solo_channels = None
        for channel in self.unserialized_channels:
            if isinstance(channel, OutputChannel):
                self.add_output_channel_precreated(channel)
        del self.unserialized_channels
        width, height = self.window.get_size()
        if self.visible or not from_nsm:
            self.window.show_all()

        if self.output_channels:
            self.output_channels[-1].volume_digits.select_region(0,0)
            self.output_channels[-1].slider.grab_focus()
        elif self.channels:
            self.channels[-1].volume_digits.select_region(0,0)
            self.channels[-1].volume_digits.grab_focus()

        self.paned.set_position(self.paned_position/self.width*width)
        self.window.resize(self.width, self.height)

    def serialize(self, object_backend):
        width, height = self.window.get_size()
        object_backend.add_property('geometry',
                        '%sx%s' % (width, height))
        pos = self.paned.get_position()
        object_backend.add_property('paned_position', '%s' % pos)
        solo_channels = []
        for input_channel in self.channels:
            if input_channel.channel.solo:
                solo_channels.append(input_channel)
        if solo_channels:
            object_backend.add_property('solo_channels',
                                        '|'.join([x.channel.name for x in solo_channels]))
        object_backend.add_property('visible', '%s' % str(self.visible))

    def unserialize_property(self, name, value):
        if name == 'geometry':
            width, height = value.split('x')
            self.width = int(width)
            self.height = int(height)
            return True
        if name == 'solo_channels':
            self._init_solo_channels = value.split('|')
            return True
        if name == 'visible':
            self.visible = value == 'True'
            return True
        if name == 'paned_position':
            self.paned_position = int(value)
            return True
        return False

    def unserialize_child(self, name):
        if name == InputChannel.serialization_name():
            channel = InputChannel(self, "", True)
            self.unserialized_channels.append(channel)
            return channel

        if name == OutputChannel.serialization_name():
            channel = OutputChannel(self, "", True)
            self.unserialized_channels.append(channel)
            return channel

        if name == gui.Factory.serialization_name():
            return self.gui_factory

    def serialization_get_childs(self):
        '''Get child objects that required and support serialization'''
        childs = self.channels[:] + self.output_channels[:] + [self.gui_factory]
        return childs

    def serialization_name(self):
        return "jack_mixer"

    # ---------------------------------------------------------------------------------------------
    # Main program loop

    def main(self):
        if not self.mixer:
            return

        if self.visible or self.nsm_client == None:
            width, height = self.window.get_size()
            self.window.show_all()
            if hasattr(self, 'paned_position'):
                self.paned.set_position(self.paned_position/self.width*width)

        signal.signal(signal.SIGUSR1, self.sighandler)
        signal.signal(signal.SIGTERM, self.sighandler)
        signal.signal(signal.SIGINT, self.sighandler)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

        Gtk.main()


def error_dialog(parent, msg, *args):
    log.exception(msg, *args)
    err = Gtk.MessageDialog(parent=parent, modal=True, destroy_with_parent=True,
        message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK, text=msg % args)
    err.run()
    err.destroy()


def main():
    parser = ArgumentParser()
    parser.add_argument(
        '-c',
        '--config',
        metavar="FILE",
        help='load mixer project configuration from FILE')
    parser.add_argument(
        '-d',
        '--debug',
        action="store_true",
        help='enable debug logging messages')
    parser.add_argument(
        'client_name',
        metavar='NAME',
        nargs='?',
        default='jack_mixer',
        help='set JACK client name')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(levelname)s: %(message)s")

    try:
        mixer = JackMixer(args.client_name)
    except Exception as e:
        error_dialog(None, "Mixer creation failed:\n\n%s", e)
        sys.exit(1)

    if not mixer.nsm_client and args.config:
        try:
            with open(args.config) as fp:
                mixer.load_from_xml(fp)
        except Exception as exc:
            error_dialog(mixer.window, "Error loading settings file '%s': %s", args.config, exc)
        else:
            mixer.current_filename = args.config

        mixer.window.set_default_size(60*(1+len(mixer.channels)+len(mixer.output_channels)), 300)

    mixer.main()

    mixer.cleanup()


if __name__ == "__main__":
    main()
