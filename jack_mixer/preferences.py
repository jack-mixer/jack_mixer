# This file is part of jack_mixer
#
# Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
# Copyright (C) 2009 Frederic Peters <fpeters@0d.be>
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

from os.path import expanduser, isdir

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject


class PreferencesDialog(Gtk.Dialog):
    def __init__(self, parent):
        self.app = parent
        GObject.GObject.__init__(self)
        self.set_title(_("Preferences"))
        self.create_ui()
        self.connect("response", self.on_response_cb)
        self.connect("delete-event", self.on_response_cb)

    def create_frame(self, label, child):
        frame = Gtk.Frame()
        frame.set_label("")
        frame.set_border_width(3)
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.get_label_widget().set_markup("<b>%s</b>" % label)

        child.set_margin_top(10)
        child.set_margin_bottom(10)
        frame.add(child)

        return frame

    def create_ui(self):
        vbox = self.get_content_area()

        path_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        path_vbox.set_tooltip_text(
            _("Set the path where mixer project files are saved and loaded from by default")
        )
        self.path_entry = Gtk.Entry()
        self.path_entry.connect("changed", self.on_path_entry_changed)
        path_vbox.pack_start(self.path_entry, False, False, 3)
        self.project_path_chooser = Gtk.FileChooserButton(
            title=_("Default Project Path"), action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        project_path = self.app.gui_factory.default_project_path
        path_vbox.pack_start(self.project_path_chooser, False, False, 3)

        if project_path:
            self.path_entry.set_text(project_path)

            if isdir(expanduser(project_path)):
                self.project_path_chooser.set_current_folder(expanduser(project_path))

        self.project_path_chooser.connect("file-set", self.on_project_path_selected)
        vbox.pack_start(self.create_frame(_("Default Project Path"), path_vbox), True, True, 0)

        interface_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.language_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.language_box.set_tooltip_text(_("Set the interface language and localisation"))
        self.language_combo = self.create_language_combo()
        interface_vbox.pack_start(self.language_box, True, True, 3)

        self.language_box.pack_start(Gtk.Label(_("Language:")), False, True, 5)
        self.language_box.pack_start(self.language_combo, True, True, 0)

        if self.app.indicator.available():
            self.tray_minimized_checkbutton = Gtk.CheckButton(_("Minimize to tray"))
            self.tray_minimized_checkbutton.set_tooltip_text(
                _("Minimize the application to the system tray when the window is closed")
            )
            self.tray_minimized_checkbutton.set_active(self.app.gui_factory.get_tray_minimized())
            self.tray_minimized_checkbutton.connect("toggled", self.on_tray_minimized_toggled)
            interface_vbox.pack_start(self.tray_minimized_checkbutton, True, True, 3)

        self.confirm_quit_checkbutton = Gtk.CheckButton(_("Confirm quit"))
        self.confirm_quit_checkbutton.set_tooltip_text(
            _("Always ask for confirmation before quitting the application")
        )
        self.confirm_quit_checkbutton.set_active(self.app.gui_factory.get_confirm_quit())
        self.confirm_quit_checkbutton.connect("toggled", self.on_confirm_quit_toggled)
        interface_vbox.pack_start(self.confirm_quit_checkbutton, True, True, 3)

        self.custom_widgets_checkbutton = Gtk.CheckButton(_("Use custom widgets"))
        self.custom_widgets_checkbutton.set_tooltip_text(
            _("Use widgets with custom design for the channel sliders")
        )
        self.custom_widgets_checkbutton.set_active(self.app.gui_factory.get_use_custom_widgets())
        self.custom_widgets_checkbutton.connect("toggled", self.on_custom_widget_toggled)
        interface_vbox.pack_start(self.custom_widgets_checkbutton, True, True, 3)

        color_tooltip = _("Draw the volume meters with the selected solid color")
        self.vumeter_color_checkbutton = Gtk.CheckButton(_("Use custom vumeter color"))
        self.vumeter_color_checkbutton.set_tooltip_text(color_tooltip)
        self.vumeter_color_checkbutton.set_active(
            self.app.gui_factory.get_vumeter_color_scheme() == "solid"
        )
        self.vumeter_color_checkbutton.connect("toggled", self.on_vumeter_color_change)
        interface_vbox.pack_start(self.vumeter_color_checkbutton, True, True, 3)

        self.custom_color_box = hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.custom_color_box.set_tooltip_text(color_tooltip)
        interface_vbox.pack_start(hbox, True, True, 3)

        hbox.set_sensitive(self.vumeter_color_checkbutton.get_active())
        hbox.pack_start(Gtk.Label(_("Custom color:")), False, True, 5)
        self.vumeter_color_picker = Gtk.ColorButton()
        self.vumeter_color_picker.set_color(
            Gdk.color_parse(self.app.gui_factory.get_vumeter_color())
        )
        self.vumeter_color_picker.connect("color-set", self.on_vumeter_color_change)
        hbox.pack_start(self.vumeter_color_picker, True, True, 0)

        reset_peak_meter_tooltip = _("Reset the peak meters after the specified time")
        self.auto_reset_peak_meters_checkbutton = Gtk.CheckButton(_("Auto reset peak meter"))
        self.auto_reset_peak_meters_checkbutton.set_tooltip_text(reset_peak_meter_tooltip)
        self.auto_reset_peak_meters_checkbutton.set_active(
            self.app.gui_factory.get_auto_reset_peak_meters()
        )
        self.auto_reset_peak_meters_checkbutton.connect(
            "toggled", self.on_auto_reset_peak_meters_toggled
        )
        interface_vbox.pack_start(self.auto_reset_peak_meters_checkbutton, True, True, 3)

        self.auto_reset_peak_meters_time_seconds_box = hbox = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.auto_reset_peak_meters_time_seconds_box.set_tooltip_text(reset_peak_meter_tooltip)
        interface_vbox.pack_start(hbox, True, True, 3)

        hbox.set_sensitive(self.auto_reset_peak_meters_checkbutton.get_active())
        hbox.pack_start(Gtk.Label(_("Time (s):")), False, True, 5)
        self.auto_reset_peak_meters_time_seconds_spinbutton = (
            spinbutton
        ) = self.create_auto_reset_peak_meters_time_seconds_spinbutton()
        hbox.pack_start(spinbutton, True, True, 0)

        self.meter_refresh_period_milliseconds_box = hbox = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.meter_refresh_period_milliseconds_box.set_tooltip_text(
            _("Update the volume level meters with the specified interval in milliseconds")
        )
        interface_vbox.pack_start(hbox, True, True, 3)
        hbox.pack_start(Gtk.Label(_("Meter Refresh Period (ms):")), False, True, 5)
        self.meter_refresh_period_milliseconds_spinbutton = (
            spinbutton
        ) = self.create_meter_refresh_period_milliseconds_spinbutton()
        hbox.pack_start(spinbutton, True, True, 0)

        vbox.pack_start(self.create_frame(_("Interface"), interface_vbox), True, True, 0)

        table = Gtk.Table(2, 2, False)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        meter_scale_tooltip = _("Set the scale for all volume meters")
        meter_scale_label = Gtk.Label(label=_("Meter scale:"))
        meter_scale_label.set_tooltip_text(meter_scale_tooltip)
        table.attach(meter_scale_label, 0, 1, 0, 1)
        self.meter_scale_combo = self.create_meter_store_and_combo()
        self.meter_scale_combo.set_tooltip_text(meter_scale_tooltip)
        table.attach(self.meter_scale_combo, 1, 2, 0, 1)

        slider_scale_tooltip = _("Set the scale for all volume sliders")
        slider_scale_label = Gtk.Label(label=_("Slider scale:"))
        slider_scale_label.set_tooltip_text(slider_scale_tooltip)
        table.attach(slider_scale_label, 0, 1, 1, 2)
        self.slider_scale_combo = self.create_slider_store_and_combo()
        self.slider_scale_combo.set_tooltip_text(slider_scale_tooltip)
        table.attach(self.slider_scale_combo, 1, 2, 1, 2)

        vbox.pack_start(self.create_frame(_("Scales"), table), True, True, 0)

        table = Gtk.Table(1, 2, False)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        midi_behavior_tooltip = _(
            "Set how channel volume and balance are controlled via MIDI:\n\n"
            "- Jump To Value: channel volume or balance is set immediately to received controller value\n"
            "- Pick Up: control changes are ignored until a controller value near the current value is received\n"
        )
        midi_behavior_label = Gtk.Label(label=_("Control Behavior:"))
        midi_behavior_label.set_tooltip_text(midi_behavior_tooltip)
        table.attach(midi_behavior_label, 0, 1, 0, 1)
        self.midi_behavior_combo = self.create_midi_behavior_combo()
        self.midi_behavior_combo.set_tooltip_text(midi_behavior_tooltip)
        table.attach(self.midi_behavior_combo, 1, 2, 0, 1)

        vbox.pack_start(self.create_frame(_("MIDI"), table), True, True, 0)
        self.vbox.show_all()

        self.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)

    def create_language_combo(self):
        combo = Gtk.ComboBoxText()
        for code, name in self.app.gui_factory.languages:
            combo.append(code or "", name)
        combo.set_active_id(self.app.gui_factory.get_language() or "")
        combo.connect("changed", self.on_language_combo_changed)
        return combo

    def create_meter_store_and_combo(self):
        store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)
        for scale in self.app.meter_scales:
            row = scale.scale_id, scale
            current_iter = store.append(row)
            if scale is self.app.gui_factory.get_default_meter_scale():
                active_iter = current_iter
        self.meter_store = store

        meter_scale_combo = Gtk.ComboBox.new_with_model(store)
        cell = Gtk.CellRendererText()
        meter_scale_combo.pack_start(cell, True)
        meter_scale_combo.add_attribute(cell, "text", 0)
        meter_scale_combo.set_active_iter(active_iter)
        meter_scale_combo.connect("changed", self.on_meter_scale_combo_changed)

        return meter_scale_combo

    def create_slider_store_and_combo(self):
        store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)
        for scale in self.app.slider_scales:
            row = scale.scale_id, scale
            current_iter = store.append(row)
            if scale is self.app.gui_factory.get_default_slider_scale():
                active_iter = current_iter
        self.slider_store = store

        slider_scale_combo = Gtk.ComboBox.new_with_model(store)
        cell = Gtk.CellRendererText()
        slider_scale_combo.pack_start(cell, True)
        slider_scale_combo.add_attribute(cell, "text", 0)
        slider_scale_combo.set_active_iter(active_iter)
        slider_scale_combo.connect("changed", self.on_slider_scale_combo_changed)

        return slider_scale_combo

    def create_midi_behavior_combo(self):
        combo = Gtk.ComboBoxText()
        for i, mode in enumerate(self.app.gui_factory.midi_behavior_modes):
            combo.append(str(i), mode)
        combo.set_active(self.app.gui_factory.get_midi_behavior_mode())
        combo.connect("changed", self.on_midi_behavior_combo_changed)
        return combo

    def create_auto_reset_peak_meters_time_seconds_spinbutton(self):
        adjustment = Gtk.Adjustment(
            value=float(self.app.gui_factory.get_auto_reset_peak_meters_time_seconds()),
            lower=0.1,
            upper=10.0,
            step_increment=0.1,
            page_increment=0.5,
            page_size=0.0,
        )
        spinbutton = Gtk.SpinButton(adjustment=adjustment, climb_rate=1.0, digits=1)
        spinbutton.connect("value-changed", self.on_peak_reset_spinbutton_changed)
        return spinbutton

    def create_meter_refresh_period_milliseconds_spinbutton(self):
        adjustment = Gtk.Adjustment(
            value=int(self.app.gui_factory.get_meter_refresh_period_milliseconds()),
            lower=1,
            upper=1000,
            step_increment=1,
            page_increment=10,
        )
        spinbutton = Gtk.SpinButton(adjustment=adjustment)
        spinbutton.connect("value-changed", self.on_meter_refresh_spinbutton_changed)
        return spinbutton

    def on_response_cb(self, dlg, response_id, *args):
        self.app.preferences_dialog = None
        self.destroy()

    def on_path_entry_changed(self, *args):
        path = self.path_entry.get_text().strip()

        if path:
            fullpath = expanduser(path)

            if isdir(fullpath):
                self.project_path_chooser.set_current_folder(fullpath)
                self.app.gui_factory.set_default_project_path(path)

    def on_project_path_selected(self, path_chooser):
        path = path_chooser.get_filename()
        self.path_entry.set_text(path)
        self.app.gui_factory.set_default_project_path(path)

    def on_language_combo_changed(self, *args):
        code = self.language_combo.get_active_id()
        if code != self.app.gui_factory.get_language():
            self.app.gui_factory.set_language(code)
            dlg = Gtk.MessageDialog(
                parent=self,
                modal=True,
                destroy_with_parent=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=_("You need to restart the application for this setting to take effect."),
            )
            dlg.run()
            dlg.destroy()

    def on_meter_scale_combo_changed(self, *args):
        active_iter = self.meter_scale_combo.get_active_iter()
        scale = self.meter_store.get(active_iter, 1)[0]
        self.app.gui_factory.set_default_meter_scale(scale)

    def on_slider_scale_combo_changed(self, *args):
        active_iter = self.slider_scale_combo.get_active_iter()
        scale = self.slider_store.get(active_iter, 1)[0]
        self.app.gui_factory.set_default_slider_scale(scale)

    def on_midi_behavior_combo_changed(self, *args):
        active = self.midi_behavior_combo.get_active()
        self.app.gui_factory.set_midi_behavior_mode(active)

    def on_vumeter_color_change(self, *args):
        color_scheme = "default"
        if self.vumeter_color_checkbutton.get_active():
            color_scheme = "solid"
        self.app.gui_factory.set_vumeter_color_scheme(color_scheme)

        color = self.vumeter_color_picker.get_color().to_string()
        self.app.gui_factory.set_vumeter_color(color)

        self.custom_color_box.set_sensitive(self.vumeter_color_checkbutton.get_active())

    def on_tray_minimized_toggled(self, *args):
        self.app.gui_factory.set_tray_minimized(self.tray_minimized_checkbutton.get_active())

    def on_confirm_quit_toggled(self, *args):
        self.app.gui_factory.set_confirm_quit(self.confirm_quit_checkbutton.get_active())

    def on_custom_widget_toggled(self, *args):
        self.app.gui_factory.set_use_custom_widgets(self.custom_widgets_checkbutton.get_active())

    def on_auto_reset_peak_meters_toggled(self, *args):
        self.app.gui_factory.set_auto_reset_peak_meters(
            self.auto_reset_peak_meters_checkbutton.get_active()
        )

        self.auto_reset_peak_meters_time_seconds_box.set_sensitive(
            self.auto_reset_peak_meters_checkbutton.get_active()
        )

    def on_peak_reset_spinbutton_changed(self, *args):
        self.app.gui_factory.set_auto_reset_peak_meters_time_seconds(
            self.auto_reset_peak_meters_time_seconds_spinbutton.get_value()
        )

    def on_meter_refresh_spinbutton_changed(self, *args):
        self.app.gui_factory.set_meter_refresh_period_milliseconds(
            self.meter_refresh_period_milliseconds_spinbutton.get_value_as_int()
        )
