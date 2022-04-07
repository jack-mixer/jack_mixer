#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of jack_mixer
#
# Copyright (C) 2006-2009 Nedko Arnaudov <nedko@arnaudov.name>
# Copyright (C) 2009-2021 Frederic Peters <fpeters@0d.be> et al.
#

import getpass
import gettext
import logging
import datetime
import os
import re
import signal
import sys
from os.path import abspath, dirname, isdir, isfile, join
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GLib

from . import gui
from . import scale
from ._jack_mixer import Mixer
from .channel import InputChannel, NewInputChannelDialog, NewOutputChannelDialog, OutputChannel
from .nsmclient import NSMClient
from .preferences import PreferencesDialog
from .serialization_xml import XmlSerialization
from .serialization import SerializedObject, Serializator
from .styling import load_css_styles
from .version import __version__


__program__ = "jack_mixer"
# A "locale" directory present within the package take precedence
_pkglocdir = join(abspath(dirname(__file__)), "locale")
# unless overwritten by the "LOCALEDIR environment variable.
# Fall back to the system default locale directory.
_localedir = os.environ.get("LOCALEDIR", _pkglocdir if isdir(_pkglocdir) else None)
translation = gettext.translation(__program__, _localedir, fallback=True)
translation.install()
log = logging.getLogger(__program__)
__doc__ = _("A multi-channel audio mixer application for the JACK Audio Connection Kit.")
__license__ = _("""\
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
Franklin Street, Fifth Floor, Boston, MA 02110-130159 USA
""")

# Hack argparse and delay its import to get it to use our translations
gettext.gettext, gettext.ngettext = translation.gettext, translation.ngettext
import argparse


def add_number_suffix(s):
    def inc(match):
        return str(int(match.group(0)) + 1)

    new_s = re.sub(r"(\d+)\s*$", inc, s)
    if new_s == s:
        new_s = s + " 1"

    return new_s


class JackMixer(SerializedObject):

    # scales suitable as meter scales
    meter_scales = [
        scale.K20(),
        scale.K14(),
        scale.IEC268(),
        scale.Linear70dB(),
        scale.IEC268Minimalistic(),
    ]

    # scales suitable as volume slider scales
    slider_scales = [scale.Linear30dB(), scale.Linear70dB()]

    def __init__(self, client_name=__program__):
        self.visible = False
        self.nsm_client = None
        # name of project file that is currently open
        self.current_filename = None
        self.last_project_path = None
        self._monitored_channel = None
        self._init_solo_channels = None
        self.last_xml_serialization = None
        self.cached_xml_serialization = None

        if os.environ.get("NSM_URL"):
            self.nsm_client = NSMClient(
                prettyName=__program__,
                saveCallback=self.nsm_save_cb,
                openOrNewCallback=self.nsm_open_cb,
                supportsSaveStatus=True,
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
        self.mixer = Mixer(client_name)
        self.create_ui(with_nsm)
        self.window.set_title(client_name)
        # Port names, which are not user-settable are not marked as translatable,
        # so they are the same regardless of the language setting of the environment
        # in which a project is loaded.
        self.monitor_channel = self.mixer.add_output_channel("Monitor", True, True)

        self.meter_refresh_period = \
            self.gui_factory.get_meter_refresh_period_milliseconds()
        self.meter_refresh_timer_id = GLib.timeout_add(self.meter_refresh_period, self.read_meters)
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
            self.menu_item_add_accelerator(menuitem, accel)
        return menuitem

    def menu_item_add_accelerator(self, menuitem, accel):
        key, mod = Gtk.accelerator_parse(accel)
        menuitem.add_accelerator(
            "activate", self.menu_accelgroup, key, mod, Gtk.AccelFlags.VISIBLE
        )

    def create_recent_file_menu(self):
        def filter_func(item):
            return (
                item.mime_type in ("text/xml", "application/xml")
                and __program__ in item.applications
            )

        filter_flags = Gtk.RecentFilterFlags.MIME_TYPE | Gtk.RecentFilterFlags.APPLICATION
        recentfilter = Gtk.RecentFilter()
        recentfilter.set_name(_("jack_mixer XML files"))
        recentfilter.add_custom(filter_flags, filter_func)

        recentchooser = Gtk.RecentChooserMenu.new_for_manager(self.recentmanager)
        recentchooser.set_sort_type(Gtk.RecentSortType.MRU)
        recentchooser.set_local_only(True)
        recentchooser.set_limit(10)
        recentchooser.set_show_icons(True)
        recentchooser.set_show_numbers(True)
        recentchooser.set_show_tips(True)
        recentchooser.add_filter(recentfilter)
        recentchooser.connect("item-activated", self.on_recent_file_chosen)

        recentmenu = Gtk.MenuItem.new_with_mnemonic(_("_Recent Projects"))
        recentmenu.set_submenu(recentchooser)
        return recentmenu

    def create_ui(self, with_nsm):
        self.channels = []
        self.output_channels = []
        load_css_styles()

        # Main window
        self.width = 420
        self.height = 420
        self.paned_position = 210
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_icon_name(__program__)
        self.window.set_default_size(self.width, self.height)

        self.gui_factory = gui.Factory(self.window, self.meter_scales, self.slider_scales)
        self.gui_factory.connect("language-changed", self.on_language_changed)
        self.gui_factory.emit("language-changed", self.gui_factory.get_language())
        self.gui_factory.connect("midi-behavior-mode-changed", self.on_midi_behavior_mode_changed)
        self.gui_factory.connect(
            "default-meter-scale-changed", self.on_default_meter_scale_changed
        )
        self.gui_factory.connect(
            "meter-refresh-period-milliseconds-changed",
            self.on_meter_refresh_period_milliseconds_changed
        )
        self.gui_factory.emit_midi_behavior_mode()

        # Recent files manager
        self.recentmanager = Gtk.RecentManager.get_default()

        self.vbox_top = Gtk.VBox()
        self.window.add(self.vbox_top)

        self.menu_accelgroup = Gtk.AccelGroup()
        self.window.add_accel_group(self.menu_accelgroup)

        # Main Menu
        self.menubar = Gtk.MenuBar()
        self.vbox_top.pack_start(self.menubar, False, True, 0)

        mixer_menu_item = Gtk.MenuItem.new_with_mnemonic(_("_Mixer"))
        self.menubar.append(mixer_menu_item)
        edit_menu_item = Gtk.MenuItem.new_with_mnemonic(_("_Edit"))
        self.menubar.append(edit_menu_item)
        help_menu_item = Gtk.MenuItem.new_with_mnemonic(_("_Help"))
        self.menubar.append(help_menu_item)

        # Mixer (and File) menu
        self.mixer_menu = Gtk.Menu()
        mixer_menu_item.set_submenu(self.mixer_menu)

        self.mixer_menu.append(
            self.new_menu_item(_("New _Input Channel"), self.on_add_input_channel, "<Control>N")
        )
        self.mixer_menu.append(
            self.new_menu_item(
                _("New Output _Channel"), self.on_add_output_channel, "<Shift><Control>N"
            )
        )

        self.mixer_menu.append(Gtk.SeparatorMenuItem())
        if not with_nsm:
            self.mixer_menu.append(
                self.new_menu_item(_("_Open..."), self.on_open_cb, "<Control>O")
            )

            # Recent files sub-menu
            self.mixer_menu.append(self.create_recent_file_menu())

        self.mixer_menu.append(self.new_menu_item(_("_Save"), self.on_save_cb, "<Control>S"))

        if not with_nsm:
            self.mixer_menu.append(
                self.new_menu_item(_("Save _As..."), self.on_save_as_cb, "<Shift><Control>S")
            )

        self.mixer_menu.append(Gtk.SeparatorMenuItem())
        if with_nsm:
            self.mixer_menu.append(self.new_menu_item(_("_Hide"), self.nsm_hide_cb, "<Control>W"))
        else:
            self.mixer_menu.append(self.new_menu_item(_("_Quit"), self.on_quit_cb, "<Control>Q"))

        # Edit menu
        edit_menu = Gtk.Menu()
        edit_menu_item.set_submenu(edit_menu)

        self.channel_edit_input_menu_item = self.new_menu_item(
            _("_Edit Input Channel"), enabled=False
        )
        edit_menu.append(self.channel_edit_input_menu_item)
        self.channel_edit_input_menu = Gtk.Menu()
        self.channel_edit_input_menu_item.set_submenu(self.channel_edit_input_menu)

        self.channel_edit_output_menu_item = self.new_menu_item(
            _("E_dit Output Channel"), enabled=False
        )
        edit_menu.append(self.channel_edit_output_menu_item)
        self.channel_edit_output_menu = Gtk.Menu()
        self.channel_edit_output_menu_item.set_submenu(self.channel_edit_output_menu)

        self.channel_remove_input_menu_item = self.new_menu_item(
            _("_Remove Input Channel"), enabled=False
        )
        edit_menu.append(self.channel_remove_input_menu_item)
        self.channel_remove_input_menu = Gtk.Menu()
        self.channel_remove_input_menu_item.set_submenu(self.channel_remove_input_menu)

        self.channel_remove_output_menu_item = self.new_menu_item(
            _("Re_move Output Channel"), enabled=False
        )
        edit_menu.append(self.channel_remove_output_menu_item)
        self.channel_remove_output_menu = Gtk.Menu()
        self.channel_remove_output_menu_item.set_submenu(self.channel_remove_output_menu)

        edit_menu.append(Gtk.SeparatorMenuItem())
        menuitem = self.new_menu_item(_("Shrink Channels"), self.on_shrink_channels_cb,
                                      "<Control>minus")
        self.menu_item_add_accelerator(menuitem, "<Control>KP_Subtract")
        edit_menu.append(menuitem)
        menuitem = self.new_menu_item(_("Expand Channels"), self.on_expand_channels_cb,
                                      "<Control>plus")
        self.menu_item_add_accelerator(menuitem, "<Control>KP_Add")
        edit_menu.append(menuitem)
        edit_menu.append(Gtk.SeparatorMenuItem())

        edit_menu.append(self.new_menu_item('Prefader Metering', self.on_prefader_meters_cb,
                                            "<Control>M"))
        edit_menu.append(self.new_menu_item('Postfader Metering', self.on_postfader_meters_cb,
                                            "<Shift><Control>M"))

        edit_menu.append(Gtk.SeparatorMenuItem())

        edit_menu.append(self.new_menu_item(_("_Clear"), self.on_channels_clear, "<Control>X"))
        edit_menu.append(Gtk.SeparatorMenuItem())

        self.preferences_dialog = None
        edit_menu.append(
            self.new_menu_item(_("_Preferences"), self.on_preferences_cb, "<Control>P")
        )

        # Help menu
        help_menu = Gtk.Menu()
        help_menu_item.set_submenu(help_menu)

        help_menu.append(self.new_menu_item(_("_About"), self.on_about, "F1"))

        # Main panel
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
        self.window.connect("delete-event", self.on_delete_event)

    # ---------------------------------------------------------------------------------------------
    # Channel creation

    def add_channel(
        self,
        name,
        stereo=True,
        direct_output=True,
        volume_cc=-1,
        balance_cc=-1,
        mute_cc=-1,
        solo_cc=-1,
        initial_vol=-1,
    ):
        try:
            channel = InputChannel(
                self, name, stereo=stereo, direct_output=direct_output, initial_vol=initial_vol
            )
            self.add_channel_precreated(channel)
        except Exception:
            error_dialog(self.window, _("Input channel creation failed."))
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

        if channel.wants_direct_output:
            self.add_direct_output(channel)

        channel.connect("input-channel-order-changed", self.on_input_channel_order_changed)

    def add_direct_output(self, channel, name=None):
        # Port names, which are not user-settable are not marked as translatable,
        # so they are the same regardless of the language setting of the environment
        # in which a project is loaded.
        if not name:
            name = "{channel_name} Out".format(channel_name=channel.channel_name)
        # create post fader output channel matching the input channel
        channel.post_fader_output_channel = self.mixer.add_output_channel(
            name, channel.channel.is_stereo, True
        )
        channel.post_fader_output_channel.volume = 0
        channel.post_fader_output_channel.set_solo(channel.channel, True)

    def add_output_channel(
        self,
        name,
        stereo=True,
        volume_cc=-1,
        balance_cc=-1,
        mute_cc=-1,
        display_solo_buttons=False,
        color="#fff",
        initial_vol=-1,
    ):
        try:
            channel = OutputChannel(self, name, stereo=stereo, initial_vol=initial_vol)
            channel.display_solo_buttons = display_solo_buttons
            channel.color = color
            self.add_output_channel_precreated(channel)
        except Exception:
            error_dialog(self.window, _("Output channel creation failed."))
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
        channel.connect("output-channel-order-changed", self.on_output_channel_order_changed)

    # ---------------------------------------------------------------------------------------------
    # Signal/event handlers

    # ---------------------------------------------------------------------------------------------
    # NSM

    def nsm_react(self):
        self.nsm_client.reactToMessage()
        current_xml_serialization = self.get_xml_serialization().doc.toxml()
        if self.last_xml_serialization is None:
            self.last_xml_serialization = current_xml_serialization
        if self.cached_xml_serialization is None:
            self.cached_xml_serialization = current_xml_serialization
        if self.cached_xml_serialization == current_xml_serialization:
            return True
        if self.last_xml_serialization != current_xml_serialization:
            self.nsm_client.announceSaveStatus(False)
        else:
            self.nsm_client.announceSaveStatus(True)
        self.cached_xml_serialization = current_xml_serialization

        return True

    def nsm_hide_cb(self, *args):
        self.window.hide()
        self.visible = False
        self.nsm_client.announceGuiVisibility(False)

    def nsm_show_cb(self):
        width, height = self.window.get_size()
        self.window.show_all()
        self.paned.set_position(self.paned_position / self.width * width)

        self.visible = True
        self.nsm_client.announceGuiVisibility(True)

    def nsm_open_cb(self, path, session_name, client_name):
        self.create_mixer(client_name, with_nsm=True)
        self.current_filename = path + ".xml"
        if isfile(self.current_filename):
            try:
                with open(self.current_filename, "r") as fp:
                    self.load_from_xml(fp, from_nsm=True)
            except Exception as exc:
                # Re-raise with more meaningful error message
                raise IOError(
                    _("Error loading project file '{filename}': {msg}").format(
                        filename=self.current_filename, msg=exc
                    )
                )

    def nsm_save_cb(self, path, session_name, client_name):
        self.current_filename = path + ".xml"
        with open(self.current_filename, "w") as fp:
            self.save_to_xml(fp)
            self.last_xml_serialization = self.get_xml_serialization().doc.toxml()

    def nsm_exit_cb(self, path, session_name, client_name):
        Gtk.main_quit()

    # ---------------------------------------------------------------------------------------------
    # POSIX signals

    def sighandler(self, signum, frame):
        log.debug("Signal %d received.", signum)
        if signum == signal.SIGUSR1:
            GLib.timeout_add(0, self.on_save_cb)
        elif signum == signal.SIGINT or signum == signal.SIGTERM:
            GLib.timeout_add(0, self.on_quit_cb)
        else:
            log.warning("Unknown signal %d received.", signum)

    # ---------------------------------------------------------------------------------------------
    # GTK signals

    def on_language_changed(self, gui_factory, lang):
        global translation
        translation = gettext.translation(
            __program__, _localedir, languages=[lang] if lang else None, fallback=True
        )
        translation.install()

    def on_about(self, *args):
        about = Gtk.AboutDialog()
        about.set_name(__program__)
        about.set_program_name(__program__)
        about.set_copyright(
            "Copyright © 2006-2021\n"
            "Nedko Arnaudov,\n"
            "Frédéric Péters, Arnout Engelen,\n"
            "Daniel Sheeler, Christopher Arndt"
        )
        about.set_license(__license__)
        about.set_authors(
            [
                "Nedko Arnaudov <nedko@arnaudov.name>",
                "Christopher Arndt <chris@chrisarndt.de>",
                "Arnout Engelen <arnouten@bzzt.net>",
                "John Hedges <john@drystone.co.uk>",
                "Olivier Humbert <trebmuh@tuxfamily.org>",
                "Sarah Mischke <sarah@spooky-online.de>",
                "Frédéric Péters <fpeters@0d.be>",
                "Daniel Sheeler <dsheeler@pobox.com>",
                "Athanasios Silis <athanasios.silis@gmail.com>",
            ]
        )
        about.set_logo_icon_name(__program__)
        about.set_version(__version__)
        about.set_website("https://rdio.space/jackmixer/")
        about.run()
        about.destroy()

    def on_delete_event(self, widget, event):
        if self.nsm_client:
            self.nsm_hide_cb()
            return True

        return self.on_quit_cb(on_delete=True)

    def add_file_filters(self, dialog):
        filter_xml = Gtk.FileFilter()
        filter_xml.set_name(_("XML files"))
        filter_xml.add_mime_type("text/xml")
        dialog.add_filter(filter_xml)
        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("All files"))
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

    def _open_project(self, filename):
        try:
            with open(filename, "r") as fp:
                self.load_from_xml(fp)
        except Exception as exc:
            error_dialog(
                self.window,
                _("Error loading project file '{filename}': {msg}").format(
                    filename=filename, msg=exc
                ),
            )
        else:
            self.current_filename = filename
            return True

    def on_open_cb(self, *args):
        dlg = Gtk.FileChooserDialog(
            title=_("Open project"), parent=self.window, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        dlg.set_default_response(Gtk.ResponseType.OK)

        default_project_path = self.gui_factory.get_default_project_path()

        if self.current_filename:
            dlg.set_current_folder(dirname(self.current_filename))
        else:
            dlg.set_current_folder(self.last_project_path or default_project_path or os.getcwd())

        if default_project_path:
            dlg.add_shortcut_folder(default_project_path)

        self.add_file_filters(dlg)

        if dlg.run() == Gtk.ResponseType.OK:
            filename = dlg.get_filename()
            if self._open_project(filename):
                self.recentmanager.add_item("file://" + abspath(filename))

        dlg.destroy()

    def on_recent_file_chosen(self, recentchooser):
        item = recentchooser.get_current_item()

        if item and item.exists():
            log.debug("Recent file menu entry selected: %s", item.get_display_name())
            uri = item.get_uri()
            if not self._open_project(urlparse(uri).path):
                self.recentmanager.remove_item(uri)

    def _save_project(self, filename):
        with open(filename, "w") as fp:
            self.save_to_xml(fp)

    def on_save_cb(self, *args):
        if not self.current_filename:
            return self.on_save_as_cb()

        try:
            self._save_project(self.current_filename)
        except Exception as exc:
            error_dialog(
                self.window,
                _("Error saving project file '{filename}': {msg}").format(
                    filename=self.current_filename, msg=exc
                ),
            )

    def on_save_as_cb(self, *args):
        dlg = Gtk.FileChooserDialog(
            title=_("Save project"), parent=self.window, action=Gtk.FileChooserAction.SAVE
        )
        dlg.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)

        default_project_path = self.gui_factory.get_default_project_path()

        if self.current_filename:
            dlg.set_filename(self.current_filename)
        else:
            dlg.set_current_folder(self.last_project_path or default_project_path or os.getcwd())
            filename = "{}-{}.xml".format(
                getpass.getuser(), datetime.datetime.now().strftime("%Y%m%d-%H%M")
            )
            dlg.set_current_name(filename)

        if default_project_path:
            dlg.add_shortcut_folder(default_project_path)

        self.add_file_filters(dlg)

        if dlg.run() == Gtk.ResponseType.OK:
            save_path = dlg.get_filename()
            save_dir = dirname(save_path)
            if isdir(save_dir):
                self.last_project_path = save_dir

            filename = dlg.get_filename()
            try:
                self._save_project(filename)
            except Exception as exc:
                error_dialog(
                    self.window,
                    _("Error saving project file '{filename}': {msg}").format(
                        filename=filename, msg=exc
                    ),
                )
            else:
                self.current_filename = filename
                self.recentmanager.add_item("file://" + abspath(filename))

        dlg.destroy()

    def on_quit_cb(self, *args, on_delete=False):
        if not self.nsm_client and self.gui_factory.get_confirm_quit():
            dlg = Gtk.MessageDialog(
                parent=self.window,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
            )
            dlg.set_markup(_("<b>Quit application?</b>"))
            dlg.format_secondary_markup(
                _(
                    "All jack_mixer ports will be closed and connections lost,"
                    "\nstopping all sound going through jack_mixer.\n\n"
                    "Are you sure?"
                )
            )
            dlg.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_QUIT, Gtk.ResponseType.OK
            )
            response = dlg.run()
            dlg.destroy()
            if response != Gtk.ResponseType.OK:
                return on_delete

        Gtk.main_quit()

    def on_shrink_channels_cb(self, widget):
        for channel in self.channels + self.output_channels:
            channel.narrow()

    def on_expand_channels_cb(self, widget):
        for channel in self.channels + self.output_channels:
            channel.widen()

    def on_prefader_meters_cb(self, widget):
        for channel in self.channels + self.output_channels:
            channel.use_prefader_metering()

    def on_postfader_meters_cb(self, widget):
        for channel in self.channels + self.output_channels:
            channel.use_prefader_metering(False)

    def on_midi_behavior_mode_changed(self, gui_factory, value):
        self.mixer.midi_behavior_mode = value

    def on_preferences_cb(self, widget):
        if not self.preferences_dialog:
            self.preferences_dialog = PreferencesDialog(self)
        self.preferences_dialog.show()
        self.preferences_dialog.present()

    def on_add_channel(self, inout="input", default_name="Input"):
        dialog = getattr(self, "_add_{}_dialog".format(inout), None)
        values = getattr(self, "_add_{}_values".format(inout), {})

        if dialog is None:
            cls = NewInputChannelDialog if inout == "input" else NewOutputChannelDialog
            dialog = cls(app=self)
            setattr(self, "_add_{}_dialog".format(inout), dialog)

        names = {
            ch.channel_name for ch in (self.channels if inout == "input" else self.output_channels)
        }
        values.setdefault("name", default_name)
        while True:
            if values["name"] in names:
                values["name"] = add_number_suffix(values["name"])
            else:
                break

        dialog.fill_ui(**values)
        dialog.set_transient_for(self.window)
        dialog.show()
        ret = dialog.run()
        dialog.hide()

        if ret == Gtk.ResponseType.OK:
            result = dialog.get_result()
            setattr(self, "_add_{}_values".format(inout), result)
            (self.add_channel if inout == "input" else self.add_output_channel)(**result)
            if self.visible or self.nsm_client is None:
                self.window.show_all()

    def on_add_input_channel(self, widget):
        return self.on_add_channel("input", _("Input"))

    def on_add_output_channel(self, widget):
        return self.on_add_channel("output", _("Output"))

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
            remove_channel_edit_input_menuitem_by_label, channel.channel_name
        )

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
            remove_channel_edit_output_menuitem_by_label, channel.channel_name
        )

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
            if container.get_label() == parameters["oldname"]:
                container.set_label(parameters["newname"])

        rename_parameters = {"oldname": oldname, "newname": newname}
        self.channel_edit_input_menu.foreach(rename_channels, rename_parameters)
        self.channel_edit_output_menu.foreach(rename_channels, rename_parameters)
        self.channel_remove_input_menu.foreach(rename_channels, rename_parameters)
        self.channel_remove_output_menu.foreach(rename_channels, rename_parameters)
        log.debug('Renaming channel from "%s" to "%s".', oldname, newname)

    def reorder_menu_item(self, menu, source_label, dest_label):
        pos = -1
        source_item = None
        for i, menuitem in enumerate(menu.get_children()):
            label = menuitem.get_label()
            if label == source_label:
                source_item = menuitem
            elif label == dest_label:
                pos = i

        if pos != -1 and source_item is not None:
            menu.reorder_child(source_item, pos)

    def reorder_channels(self, container, source_name, dest_name, reverse=False):
        frames = container.get_children()

        for frame in frames:
            if source_name == frame.get_child().channel_name:
                source_frame = frame
                break

        if reverse:
            frames.reverse()

        for pos, frame in enumerate(frames):
            if dest_name == frame.get_child().channel_name:
                container.reorder_child(source_frame, pos)
                break

    def on_input_channel_order_changed(self, widget, source_name, dest_name):
        self.channels.clear()
        self.reorder_channels(self.hbox_inputs, source_name, dest_name)

        for frame in self.hbox_inputs.get_children():
            self.channels.append(frame.get_child())

        for menu in (self.channel_edit_input_menu, self.channel_remove_input_menu):
            self.reorder_menu_item(menu, source_name, dest_name)

    def on_output_channel_order_changed(self, widget, source_name, dest_name):
        self.output_channels.clear()
        self.reorder_channels(self.hbox_outputs, source_name, dest_name, reverse=True)

        for frame in self.hbox_outputs.get_children():
            self.output_channels.append(frame.get_child())

        for menu in (self.channel_edit_output_menu, self.channel_remove_output_menu):
            self.reorder_menu_item(menu, source_name, dest_name)

    def on_channels_clear(self, widget):
        dlg = Gtk.MessageDialog(
            parent=self.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            text=_("Are you sure you want to clear all channels?"),
            buttons=Gtk.ButtonsType.OK_CANCEL,
        )

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

            # Force save-as dialog on next save
            self.current_filename = None

        dlg.destroy()

    def on_default_meter_scale_changed(self, sender, newscale):
        if isinstance(newscale, (scale.K14, scale.K20)):
            self.mixer.kmetering = True
        else:
            self.mixer.kmetering = False

    def on_meter_refresh_period_milliseconds_changed(self, sender, value):
        if self.meter_refresh_timer_id is not None:
            GLib.source_remove(self.meter_refresh_timer_id)
        self.meter_refresh_period = value
        self.meter_refresh_timer_id = GLib.timeout_add(self.meter_refresh_period, self.read_meters)

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
        if channel == self._monitored_channel:
            return
        self._monitored_channel = channel
        if channel is None:
            self.monitor_channel.out_mute = True
        elif isinstance(channel, InputChannel):
            # reset all solo/mute settings
            for in_channel in self.channels:
                self.monitor_channel.set_solo(in_channel.channel, False)
                self.monitor_channel.set_muted(in_channel.channel, False)
            self.monitor_channel.set_solo(channel.channel, True)
            self.monitor_channel.prefader = True
            self.monitor_channel.out_mute = False
        else:
            self.monitor_channel.prefader = False
            self.monitor_channel.out_mute = False

        if channel:
            self.update_monitor(channel)

    monitored_channel = property(get_monitored_channel, set_monitored_channel)

    def update_monitor(self, channel):
        if self._monitored_channel is not channel:
            return
        self.monitor_channel.volume = channel.channel.volume
        self.monitor_channel.balance = channel.channel.balance
        if isinstance(self.monitored_channel, OutputChannel):
            # sync solo/muted channels
            for input_channel in self.channels:
                self.monitor_channel.set_solo(
                    input_channel.channel, channel.channel.is_solo(input_channel.channel)
                )
                self.monitor_channel.set_muted(
                    input_channel.channel, channel.channel.is_muted(input_channel.channel)
                )

    def get_input_channel_by_name(self, name):
        for input_channel in self.channels:
            if input_channel.channel.name == name:
                return input_channel
        return None

    # ---------------------------------------------------------------------------------------------
    # Mixer project (de-)serialization and file handling

    def get_xml_serialization(self):
        b = XmlSerialization()
        s = Serializator()
        s.serialize(self, b)
        return b

    def save_to_xml(self, file):
        log.debug("Saving to XML...")
        b = self.get_xml_serialization()
        b.save(file)

    def load_from_xml(self, file, silence_errors=False, from_nsm=False):
        log.debug("Loading from XML...")
        self.unserialized_channels = []
        b = XmlSerialization()
        try:
            b.load(file, self.serialization_name())
        except:  # noqa: E722
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
            self.output_channels[-1].volume_digits.select_region(0, 0)
            self.output_channels[-1].slider.grab_focus()
        elif self.channels:
            self.channels[-1].volume_digits.select_region(0, 0)
            self.channels[-1].volume_digits.grab_focus()

        self.paned.set_position(self.paned_position / self.width * width)
        self.window.resize(self.width, self.height)

    def serialize(self, object_backend):
        width, height = self.window.get_size()
        object_backend.add_property("geometry", "%sx%s" % (width, height))
        pos = self.paned.get_position()
        object_backend.add_property("paned_position", "%s" % pos)
        solo_channels = []
        for input_channel in self.channels:
            if input_channel.channel.solo:
                solo_channels.append(input_channel)
        if solo_channels:
            object_backend.add_property(
                "solo_channels", "|".join([x.channel.name for x in solo_channels])
            )
        object_backend.add_property("visible", "%s" % str(self.visible))

    def unserialize_property(self, name, value):
        if name == "geometry":
            width, height = value.split("x")
            self.width = int(width)
            self.height = int(height)
            return True
        elif name == "solo_channels":
            self._init_solo_channels = value.split("|")
            return True
        elif name == "visible":
            self.visible = value == "True"
            return True
        elif name == "paned_position":
            self.paned_position = int(value)
            return True

        return False

    def unserialize_child(self, name):
        if name == InputChannel.serialization_name():
            channel = InputChannel(self, "", True)
            self.unserialized_channels.append(channel)
            return channel
        elif name == OutputChannel.serialization_name():
            channel = OutputChannel(self, "", True)
            self.unserialized_channels.append(channel)
            return channel
        elif name == gui.Factory.serialization_name():
            return self.gui_factory

    def serialization_get_childs(self):
        """Get child objects that require and support serialization."""
        childs = self.channels[:] + self.output_channels[:] + [self.gui_factory]
        return childs

    def serialization_name(self):
        return __program__

    # ---------------------------------------------------------------------------------------------
    # Main program loop

    def main(self):
        if not self.mixer:
            return

        if self.visible or self.nsm_client is None:
            width, height = self.window.get_size()
            self.window.show_all()
            if hasattr(self, "paned_position"):
                self.paned.set_position(self.paned_position / self.width * width)

        signal.signal(signal.SIGUSR1, self.sighandler)
        signal.signal(signal.SIGTERM, self.sighandler)
        signal.signal(signal.SIGINT, self.sighandler)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

        Gtk.main()


def error_dialog(parent, msg, *args, **kw):
    if kw.get("debug"):
        log.exception(msg.format(*args))
    err = Gtk.MessageDialog(
        parent=parent,
        modal=True,
        destroy_with_parent=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=msg.format(*args),
    )
    err.run()
    err.destroy()


def main():
    parser = argparse.ArgumentParser(prog=__program__, description=_(__doc__.splitlines()[0]))
    parser.add_argument(
        "-c",
        "--config",
        metavar=_("FILE"),
        help=_("load mixer project configuration from FILE")
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default="JACK_MIXER_DEBUG" in os.environ,
        help=_("enable debug logging messages"),
    )
    parser.add_argument(
        "client_name",
        metavar=_("NAME"),
        nargs="?",
        default=__program__,
        help=_("set JACK client name (default: %(default)s)"),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO, format="[{}] %(levelname)s: %(message)s".format(__program__)
    )

    try:
        mixer = JackMixer(args.client_name)
    except Exception as e:
        error_dialog(None, _("Mixer creation failed:\n\n{}"), e, debug=args.debug)
        sys.exit(1)

    if not mixer.nsm_client and args.config:
        try:
            with open(args.config) as fp:
                mixer.load_from_xml(fp)
        except Exception as exc:
            error_dialog(
                mixer.window,
                _("Error loading project file '{filename}': {msg}").format(
                    filename=args.config, msg=exc
                ),
            )
        else:
            mixer.current_filename = args.config

        mixer.window.set_default_size(
            60 * (1 + len(mixer.channels) + len(mixer.output_channels)), 300
        )

    mixer.main()
    mixer.cleanup()


if __name__ == "__main__":
    main()
