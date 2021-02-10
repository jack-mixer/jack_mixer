# This file is part of jack_mixer
#
# Copyright (C) 2006-2009 Nedko Arnaudov <nedko@arnaudov.name>
# Copyright (C) 2009-2020 Frederic Peters <fpeters@0d.be> et al.
# Copyright (C) 2020-2021 Christopher Arndt <info@chrisarndt>
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

from random import random

import gi  # noqa: F401
from gi.repository import Gtk
from gi.repository import Gdk


# CSS widget styling
DEFAULT_CSS = """\
/* Global color definitions */

@define-color monitor_bgcolor_hover #C0BFBC;
@define-color monitor_bgcolor_checked #9A9996;
@define-color mute_bgcolor_hover #FFBC80;
@define-color mute_bgcolor_checked #FF7800;
@define-color solo_bgcolor_hover #76A28E;
@define-color solo_bgcolor_checked #26A269;
@define-color prefader_bgcolor_hover #A6C2E4;
@define-color prefader_bgcolor_checked #3584E4;


/* Channel strips */

.top_label {
    padding: 0px .1em;
    min-height: 1.5rem;
}

.wide {
    font-size: medium;
}

.narrow {
    font-size: smaller;
}

.vbox_fader {
    border: 1px inset #111;
}

.readout {
    font-size: 80%;
    margin: .1em;
    padding: 0;
    border: 1px inset #111;
    color: white;
    background-color: #333;
    background-image: none;
}


/* Channel buttons */

button {
    padding: 0px .2em;
}
button.prefader_meter {
    font-size: smaller;
}
button.monitor:hover,
button.mute:hover,
button.solo:hover,
button.prefader:hover,
button.prefader_meter:hover,
button.monitor:checked,
button.mute:checked,
button.solo:checked,
button.prefader:checked,
button.prefader_meter:checked {
    color: white;
    text-shadow: unset;
    background-image: none;
}
button.monitor:hover {
    background-color: @monitor_bgcolor_hover;
}
button.monitor:checked {
    background-color: @monitor_bgcolor_checked;
}
button.mute:hover {
    background-color: @mute_bgcolor_hover;
}
button.mute:checked {
    background-color: @mute_bgcolor_checked;
}
button.solo:hover {
    background-color: @solo_bgcolor_hover;
}
button.solo:checked {
    background-color: @solo_bgcolor_checked;
}
button.prefader:hover {
    background-color: @prefader_bgcolor_hover;
}
button.prefader:checked {
    background-color: @prefader_bgcolor_checked;
}
button.prefader_meter:hover {
    background-color: @prefader_bgcolor_hover;
}
button.prefader_meter:checked {
    background-color: @prefader_bgcolor_checked;
}


/* Control groups */

.control_group {
    min-width: 0px;
    padding: 0px;
}

.control_group .label,
.control_group .mute,
.control_group .prefader,
.control_group .solo {
    font-size: smaller;
    padding: 0px .1em;
}

.control_group .mute:hover,
.control_group .solo:hover,
.control_group .prefader:hover,
.control_group .mute:checked,
.control_group .solo:checked,
.control_group .prefader:checked {
    color: white;
    text-shadow: unset;
    background-image: none;
}
.control_group .mute:hover {
    background-color: @mute_bgcolor_hover;
}
.control_group .mute:checked {
    background-color:@mute_bgcolor_checked;
}
.control_group .solo:hover {
    background-color: @solo_bgcolor_hover;
}
.control_group .solo:checked {
    background-color: @solo_bgcolor_checked;
}
.control_group .prefader:hover {
    background-color: @prefader_bgcolor_hover;
}
.control_group .prefader:checked {
    background-color: @prefader_bgcolor_checked;
}


/* Peak meters */

.over_zero {
    background-color: #cc4c00;
}

.is_nan {
    background-color: #b20000;
}
"""

COLOR_TMPL_CSS = """\
.{} {{
    background-color: {};
    color: {};
}}
"""


def add_css_provider(css, priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION):
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(css.encode("utf-8"))
    context = Gtk.StyleContext()
    screen = Gdk.Screen.get_default()
    context.add_provider_for_screen(screen, css_provider, priority)


def get_text_color(background_color):
    """Calculate the luminance of the given color (GdkRGBA)
    and return an appropriate text color."""
    # luminance coefficients taken from section C-9 from
    # http://www.faqs.org/faqs/graphics/colorspace-faq/
    brightess = (
        background_color.red * 0.212671
        + background_color.green * 0.715160
        + background_color.blue * 0.072169
    )

    if brightess > 0.5:
        return "black"
    else:
        return "white"


def load_css_styles():
    add_css_provider(DEFAULT_CSS)


def set_background_color(widget, name, color):
    color_string = color.to_string()
    add_css_provider(COLOR_TMPL_CSS.format(name, color_string, get_text_color(color)))
    widget_context = widget.get_style_context()
    widget_context.add_class(name)


def random_color():
    return Gdk.RGBA(random(), random(), random(), 1)
