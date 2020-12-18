# -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.
#
# This file is part of jack_mixer
#
# Copyright (C) 2007 Nedko Arnaudov <nedko@arnaudov.name>
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
#

AC_PREREQ(2.61)
AC_INIT(jack_mixer, 14)
AC_CONFIG_AUX_DIR(config)
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([1.11 foreign no-define tar-ustar no-dist-gzip dist-xz])
AC_CONFIG_HEADER([config.h])

# not real check but hack (because version is not parameter to configure script) to detect development version
AM_CONDITIONAL(DEV_VERSION, test $VERSION = dev)

AC_SUBST(DATADIR)

# Checks for programs.
AC_PROG_CC
AC_DISABLE_STATIC
AC_PROG_LIBTOOL
AC_SUBST(ACLOCAL_AMFLAGS, "$ACLOCAL_FLAGS -I m4")

# Checks for libraries.

PKG_CHECK_MODULES(JACKMIXER, [glib-2.0 jack])

# JACK MIDI
have_jackmidi="unknown"
AC_ARG_ENABLE(jackmidi, [AS_HELP_STRING(--disable-jackmidi, [Force disable JACK MIDI support [default=no]])], [ have_jackmidi="no (disabled)" ])
if test "$have_jackmidi" = "unknown"
then
  have_jackmidi="no"
  PKG_CHECK_MODULES(JACK_MIDI, jack >= 0.102.0, AC_DEFINE([HAVE_JACK_MIDI], [], [Defined if we have JACK MIDI support.]) have_jackmidi="yes")
  if test "$have_jackmidi" = "yes"
  then
    PKG_CHECK_MODULES(OLD_JACK_MIDI, jack < 0.102.27, have_jackmidi="yes (old one)" AC_DEFINE(HAVE_OLD_JACK_MIDI, 1, [whether or not we building against old JACK MIDI (0.102.20)]), echo -n)
  fi
fi

AM_CONDITIONAL(HAVE_JACK_MIDI, test "$have_jackmidi" = "yes" -o "$have_jackmidi" = "yes (old one)")

if test "$have_jackmidi" = "no"
then
  AC_MSG_WARN([Your JACK is missing MIDI support.])
fi

if test "$have_jackmidi" = "yes" -o "$have_jackmidi" = "yes (old one)"
then
  AC_JACK_MIDI_NFRAMES_CHECK()
  if test "$jackmidi_nframes" = "yes"
  then
    AC_DEFINE([JACK_MIDI_NEEDS_NFRAMES], 1, [Defined if we JACK MIDI functions need nframes parameter.])
  fi
fi

# Python checking
AC_ARG_ENABLE(gui, [AS_HELP_STRING(--disable-gui, [Disable GUI [default=no]])])
AC_ARG_ENABLE(pymod-checks, [AS_HELP_STRING(--disable-pymod-checks, [Force disable checks for Python modules required at run time])], [ disable_pymod_checks="yes" ], [ disable_pymod_checks="no" ])
if test "$enable_gui" != "no"
then
  AM_PATH_PYTHON(3.6)
  AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(Could not find Python headers)])
  #AS_AC_EXPAND(PYTHONDIR, $pythondir)
  #AC_SUBST(PYTHONDIR)
  pkgpyexecdir="$pyexecdir"
  enable_gui="yes"

  if test "$disable_pymod_checks" != "yes"
  then
    AM_CHECK_PYMOD(gi,,,[AC_MSG_ERROR(Could not find Pygi)])
    AM_CHECK_PYMOD(cairo,,,[AC_MSG_ERROR(Could not find Pycairo)])
  else
    AC_MSG_WARN([Checks for python modules required runtime have been force disabled])
  fi
else
  AC_MSG_WARN([GUI has been force disabled. Only jack_mix_box cli application will be built.])
fi

AM_CONDITIONAL(ENABLE_GUI, [test x$enable_gui != xno])

AC_OUTPUT([
Makefile
data/Makefile
data/art/Makefile
])


AC_MSG_RESULT([])
AC_MSG_RESULT([**********************************************************************])
AC_MSG_RESULT([])
AC_MSG_RESULT([Prefix:            $prefix])
AC_MSG_RESULT([Python dir:        $pythondir])
AC_MSG_RESULT([])
AC_MSG_RESULT([GUI  support:      $enable_gui])
AC_MSG_RESULT([MIDI support:      $have_jackmidi])
AC_MSG_RESULT([])
AC_MSG_RESULT([**********************************************************************])
AC_MSG_RESULT([])
