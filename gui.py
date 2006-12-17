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

try:
    import gconf
except:
    print "Cannot load Python bindings for GConf, your preferences will not be preserved across jack_mixer invocations"
    gconf = None

def lookup_scale(scales, scale_id):
    for scale in scales:
        if scale_id == scale.scale_id:
            return scale
    return None

class factory(gobject.GObject):
    def __init__(self, glade_xml, topwindow, meter_scales, slider_scales):
        gobject.GObject.__init__(self)
        self.glade_xml = glade_xml
        self.topwindow = topwindow
        self.meter_scales = meter_scales
        self.slider_scales = slider_scales

        if gconf:
            self.gconf_client = gconf.client_get_default()

            scale_id = self.gconf_client.get_string("/apps/jack_mixer/default_meter_scale")
            self.default_meter_scale = lookup_scale(meter_scales, scale_id)
            if not self.default_meter_scale:
                self.default_meter_scale = meter_scales[0]

            scale_id = self.gconf_client.get_string("/apps/jack_mixer/default_slider_scale")
            self.default_slider_scale = lookup_scale(slider_scales, scale_id)
            if not self.default_slider_scale:
                self.default_slider_scale = slider_scales[0]

            self.gconf_client.add_dir("/apps/jack_mixer", gconf.CLIENT_PRELOAD_NONE)
            self.gconf_client.notify_add("/apps/jack_mixer/default_meter_scale", self.on_gconf_default_meter_scale_changed)
            self.gconf_client.notify_add("/apps/jack_mixer/default_slider_scale", self.on_gconf_default_slider_scale_changed)
        else:
            self.default_meter_scale = meter_scales[0]
            self.default_slider_scale = slider_scales[0]

    def on_gconf_default_meter_scale_changed(self, client, connection_id, entry, args):
        #print "GConf default_meter_scale changed"
        scale_id = entry.get_value().get_string()
        scale = lookup_scale(self.meter_scales, scale_id)
        if scale:
            self.default_meter_scale = scale
            self.emit("default-meter-scale-changed", self.default_meter_scale)
        else:
            print "Ignoring GConf default_meter_scale setting, because \"%s\" scale is not known" % scale_id

    def on_gconf_default_slider_scale_changed(self, client, connection_id, entry, args):
        #print "GConf default_slider_scale changed"
        scale_id = entry.get_value().get_string()
        scale = lookup_scale(self.slider_scales, scale_id)
        if scale:
            self.default_slider_scale = scale
            self.emit("default-slider-scale-changed", self.default_slider_scale)
        else:
            print "Ignoring GConf default_slider_scale setting, because \"%s\" scale is not known" % scale_id

    def run_dialog_add_channel(self):
        dialog = self.glade_xml.get_widget("dialog_add_channel")
        name_entry = self.glade_xml.get_widget("new_channel_name")
        name_entry.set_text("")
        dialog.set_transient_for(self.topwindow)
        dialog.show()
        ret = dialog.run()
        dialog.hide()

        if ret == gtk.RESPONSE_OK:
            result = {
                'name': name_entry.get_text(),
                'stereo': self.glade_xml.get_widget("new_channel_stereo").get_active()
                }
            return result
        else:
            return None

    def run_dialog_rename_channel(self, name):
        dialog = self.glade_xml.get_widget("dialog_rename_channel")
        name_entry = self.glade_xml.get_widget("channel_name")
        name_entry.set_text(name)
        dialog.set_transient_for(self.topwindow)
        dialog.show()
        ret = dialog.run()
        dialog.hide()
        if ret == gtk.RESPONSE_OK:
            return name_entry.get_text()
        else:
            return None

    def run_dialog_choose_meter_scale(self):
        dialog = self.glade_xml.get_widget("dialog_choose_scale")
        dialog.set_title("Choose meter scale")
        dialog.set_transient_for(self.topwindow)

        available_scales = self.glade_xml.get_widget("available_scales")
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        renderer = gtk.CellRendererText()

        column_scale = gtk.TreeViewColumn("Scale", renderer, text=0)
        column_description = gtk.TreeViewColumn("Description", renderer, text=1)

        available_scales.append_column(column_scale)
        available_scales.append_column(column_description)

        selection = available_scales.get_selection()

        for scale in self.meter_scales:
            #print "%s: %s" % (scale.scale_id, scale.description)

            row = scale.scale_id, scale.description, scale
            current_iter = store.append(row)
            if scale is self.default_meter_scale:
                selected_iter = current_iter
                #print "Selected scale is %s" % scale.scale_id

        available_scales.set_model(store)
        selection.select_iter(selected_iter)

        dialog.show()
        while True:
            ret = dialog.run()

            if ret == gtk.RESPONSE_OK or ret == gtk.RESPONSE_APPLY:
                scale = store.get(selection.get_selected()[1], 2)[0]
                if gconf:
                    # we are setting gconf, and then notified for change
                    self.gconf_client.set_string("/apps/jack_mixer/default_meter_scale", scale.scale_id)
                else:
                    self.default_meter_scale = scale
                    self.emit("default-meter-scale-changed", self.default_meter_scale)

            if ret == gtk.RESPONSE_OK or ret == gtk.RESPONSE_CANCEL or ret == gtk.RESPONSE_DELETE_EVENT:
                break

        dialog.hide()

    def run_dialog_choose_slider_scale(self):
        dialog = self.glade_xml.get_widget("dialog_choose_scale")
        dialog.set_title("Choose slider scale")
        dialog.set_transient_for(self.topwindow)

        available_scales = self.glade_xml.get_widget("available_scales")
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        renderer = gtk.CellRendererText()

        column_scale = gtk.TreeViewColumn("Scale", renderer, text=0)
        column_description = gtk.TreeViewColumn("Description", renderer, text=1)

        available_scales.append_column(column_scale)
        available_scales.append_column(column_description)

        selection = available_scales.get_selection()

        for scale in self.slider_scales:
            #print "%s: %s" % (scale.scale_id, scale.description)

            row = scale.scale_id, scale.description, scale
            current_iter = store.append(row)
            if scale is self.default_slider_scale:
                selected_iter = current_iter
                #print "Selected scale is %s" % scale.scale_id

        available_scales.set_model(store)
        selection.select_iter(selected_iter)

        dialog.show()
        while True:
            ret = dialog.run()

            if ret == gtk.RESPONSE_OK or ret == gtk.RESPONSE_APPLY:
                scale = store.get(selection.get_selected()[1], 2)[0]
                if gconf:
                    # we are setting gconf, and then notified for change
                    self.gconf_client.set_string("/apps/jack_mixer/default_slider_scale", scale.scale_id)
                else:
                    self.default_slider_scale = scale
                    self.emit("default-slider-scale-changed", self.default_slider_scale)

            if ret == gtk.RESPONSE_OK or ret == gtk.RESPONSE_CANCEL or ret == gtk.RESPONSE_DELETE_EVENT:
                break

        dialog.hide()

    def get_default_meter_scale(self):
        return self.default_meter_scale

    def get_default_slider_scale(self):
        return self.default_slider_scale

gobject.signal_new("default-meter-scale-changed", factory, gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION, gobject.TYPE_NONE, [gobject.TYPE_PYOBJECT])
gobject.signal_new("default-slider-scale-changed", factory, gobject.SIGNAL_RUN_FIRST | gobject.SIGNAL_ACTION, gobject.TYPE_NONE, [gobject.TYPE_PYOBJECT])
