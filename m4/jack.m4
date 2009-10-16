# Copyright (C) 2007 Nedko Arnaudov <nedko@arnaudov.name>
# This file is distributed under the same terms as the Autoconf macro files.

AC_DEFUN([AC_JACK_MIDI_NFRAMES_CHECK], [
AC_MSG_CHECKING([whether JACK MIDI functions need nframes parameter])
AC_LANG_PUSH(C)
AC_COMPILE_IFELSE(AC_LANG_PROGRAM([[
#include <jack/jack.h>
#include <jack/midiport.h>
]], [[
jack_midi_event_get(0, 0, 0, 0);
]]), [jackmidi_nframes='yes'], [jackmidi_nframes='no'])
AC_MSG_RESULT([$jackmidi_nframes])
AC_LANG_POP()
])
