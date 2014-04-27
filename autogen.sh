#!/bin/sh
#
# autotools bootstrap script for jack_mixer
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

test -n "$srcdir" || srcdir=`dirname "$0"`
test -n "$srcdir" || srcdir=.

olddir=`pwd`
cd "$srcdir"

if test x$1 = xclean
then
  GENERATED="aclocal.m4 autom4te.cache config.h.in configure config Makefile.in"
  set -x
  if test -f Makefile; then make distclean; fi
  rm -rf ${GENERATED}
else
  set -x
  mkdir -p config
  aclocal -I config -I m4 $ACLOCAL_FLAGS
  libtoolize --copy --force
  autoheader
  automake --foreign --add-missing --copy
  autoconf
fi

cd "$olddir"
test -n "$NOCONFIGURE" || "$srcdir/configure" "$@"
