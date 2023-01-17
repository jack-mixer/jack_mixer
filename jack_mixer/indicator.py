import gi
try:
    gi.require_version('Gtk', '3.0')
except Exception as e:
    print(e)
    print('Repository version required not present')
    exit(1)

try:
    from gi.repository import AppIndicator3 as appindicator
except ImportError:
    appindicator = None

import os
import logging as log
from gi.repository import Gtk
from os import environ, path

prefix = environ.get('MESON_INSTALL_PREFIX', '/usr/local')
datadir = path.join(prefix, 'share')
icondir = path.join(datadir, 'icons', 'hicolor', 'scalable', 'apps')

class Indicator:
    def __init__(self, jack_mixer):
        self.app = jack_mixer
        if appindicator is None:
            log.warning('AppIndicator3 not found, indicator will not be available')
            return
        icon = os.path.join(icondir, 'jack_mixer.svg')
        self.indicator = appindicator.Indicator.new("Jack Mixer",
            icon,
            appindicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.create_menu())
 
    def available(self):
        return not self.indicator is None

    def create_menu(self):
        self.menu = Gtk.Menu()
        self.menu.set_title('Jack Mixer')
 
        self.hidewindow = Gtk.MenuItem(label = 'Hide / Show Jack Mixer')
        self.hidewindow.connect('activate', self.hideshow)
        self.menu.append(self.hidewindow)
 
        self.separator = Gtk.SeparatorMenuItem()
        self.menu.append(self.separator)
     
        self.exittray = Gtk.MenuItem(label = 'Quit')
        self.exittray.connect('activate', self.quit)
        self.menu.append(self.exittray)
 
        self.menu.show_all()
        return self.menu

    def hideshow(self, source):
        self.app.window.set_visible(not self.app.window.get_visible())
 
    def quit(self, source, on_delete=False):
        if not self.app.nsm_client and self.app.gui_factory.get_confirm_quit():
            dlg = Gtk.MessageDialog(
                parent=self.app.window,
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
