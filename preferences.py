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

import gtk
import gobject

try:
    import gconf
except ImportError:
    gconf = None

def lookup_scale(scales, scale_id):
    for scale in scales:
        if scale_id == scale.scale_id:
            return scale
    return None

class PreferencesDialog(gtk.Dialog):
    def __init__(self, parent):
        self.app = parent
        gtk.Dialog.__init__(self, '', self.app.window)
        self.create_ui()
        self.connect('response', self.on_response_cb)
        self.connect('delete-event', self.on_response_cb)

    def create_frame(self, label, child):
        frame = gtk.Frame('')
        frame.set_border_width(3)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        frame.get_label_widget().set_markup('<b>%s</b>' % label)

        alignment = gtk.Alignment()
        alignment.set_padding(0, 0, 12, 0)
        frame.add(alignment)
        alignment.add(child)

        return frame

    def create_ui(self):
        vbox = gtk.VBox()
        self.vbox.add(vbox)

        interface_vbox = gtk.VBox()
        self.custom_widgets_checkbutton = gtk.CheckButton('Use custom widgets')
        self.custom_widgets_checkbutton.set_active(
                        self.app.gui_factory.get_use_custom_widgets())
        self.custom_widgets_checkbutton.connect('toggled',
                        self.on_custom_widget_toggled)
        interface_vbox.pack_start(self.custom_widgets_checkbutton)

        self.vumeter_color_checkbutton = gtk.CheckButton('Use custom vumeter color')
        self.vumeter_color_checkbutton.set_active(
                        self.app.gui_factory.get_vumeter_color_scheme() == 'solid')
        self.vumeter_color_checkbutton.connect('toggled',
                        self.on_vumeter_color_change)
        interface_vbox.pack_start(self.vumeter_color_checkbutton)
        hbox = gtk.HBox()
        interface_vbox.pack_start(hbox)
        self.custom_color_box = hbox
        self.custom_color_box.set_sensitive(
                        self.vumeter_color_checkbutton.get_active() == True)
        hbox.pack_start(gtk.Label('Custom color:'))
        self.vumeter_color_picker = gtk.ColorButton()
        self.vumeter_color_picker.set_color(gtk.gdk.color_parse(
                                self.app.gui_factory.get_vumeter_color()))
        self.vumeter_color_picker.connect('color-set',
                        self.on_vumeter_color_change)
        hbox.pack_start(self.vumeter_color_picker)

        self.minimize_to_tray_checkbutton = gtk.CheckButton('Minimize to system tray')
        self.minimize_to_tray_checkbutton.set_active(
                        self.app.gui_factory.get_minimize_to_tray() )
        self.minimize_to_tray_checkbutton.connect('toggled', self.on_minimize_to_tray_toggled)
        interface_vbox.pack_start(self.minimize_to_tray_checkbutton)

        vbox.pack_start(self.create_frame('Interface', interface_vbox))

        table = gtk.Table(2, 2, False)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        table.attach(gtk.Label('Meter scale'), 0, 1, 0, 1)
        self.meter_scale_combo = self.create_meter_store_and_combo()
        table.attach(self.meter_scale_combo, 1, 2, 0, 1)

        table.attach(gtk.Label('Slider scale'), 0, 1, 1, 2)
        self.slider_scale_combo = self.create_slider_store_and_combo()
        table.attach(self.slider_scale_combo, 1, 2, 1, 2)

        vbox.pack_start(self.create_frame('Scales', table))

        self.vbox.show_all()

        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)

    def create_meter_store_and_combo(self):
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        for scale in self.app.meter_scales:
            row = scale.scale_id, scale
            current_iter = store.append(row)
            if scale is self.app.gui_factory.get_default_meter_scale():
                active_iter = current_iter
        self.meter_store = store

        meter_scale_combo = gtk.ComboBox(store)
        cell = gtk.CellRendererText()
        meter_scale_combo.pack_start(cell, True)
        meter_scale_combo.add_attribute(cell, 'text', 0)
        meter_scale_combo.set_active_iter(active_iter)
        meter_scale_combo.connect('changed',
                        self.on_meter_scale_combo_changed)

        return meter_scale_combo

    def create_slider_store_and_combo(self):
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        for scale in self.app.slider_scales:
            row = scale.scale_id, scale
            current_iter = store.append(row)
            if scale is self.app.gui_factory.get_default_slider_scale():
                active_iter = current_iter
        self.slider_store = store

        slider_scale_combo = gtk.ComboBox(store)
        cell = gtk.CellRendererText()
        slider_scale_combo.pack_start(cell, True)
        slider_scale_combo.add_attribute(cell, 'text', 0)
        slider_scale_combo.set_active_iter(active_iter)
        slider_scale_combo.connect('changed',
                        self.on_slider_scale_combo_changed)

        return slider_scale_combo

    def on_response_cb(self, dlg, response_id, *args):
        self.app.preferences_dialog = None
        self.destroy()

    def on_meter_scale_combo_changed(self, *args):
        active_iter = self.meter_scale_combo.get_active_iter()
        scale = self.meter_store.get(active_iter, 1)[0]
        self.app.gui_factory.set_default_meter_scale(scale)

    def on_slider_scale_combo_changed(self, *args):
        active_iter = self.slider_scale_combo.get_active_iter()
        scale = self.slider_store.get(active_iter, 1)[0]
        self.app.gui_factory.set_default_slider_scale(scale)

    def on_vumeter_color_change(self, *args):
        color_scheme = 'default'
        if self.vumeter_color_checkbutton.get_active():
            color_scheme = 'solid'
        self.app.gui_factory.set_vumeter_color_scheme(color_scheme)

        color = self.vumeter_color_picker.get_color().to_string()
        self.app.gui_factory.set_vumeter_color(color)

        self.custom_color_box.set_sensitive(
                        self.vumeter_color_checkbutton.get_active() == True)

    def on_custom_widget_toggled(self, *args):
        self.app.gui_factory.set_use_custom_widgets(
                        self.custom_widgets_checkbutton.get_active())

    def on_minimize_to_tray_toggled(self, *args):
        self.app.gui_factory.set_minimize_to_tray(
                        self.minimize_to_tray_checkbutton.get_active())
