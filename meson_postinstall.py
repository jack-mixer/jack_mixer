#!/usr/bin/env python3

import sysconfig
from compileall import compile_dir
from os import environ, path

prefix = environ.get('MESON_INSTALL_PREFIX', '/usr/local')
datadir = path.join(prefix, 'share')
destdir = environ.get('MESON_INSTALL_DESTDIR_PREFIX', '')

# Package managers set this so we don't need to run
if 'DESTDIR' not in environ:
    from subprocess import call
    print('Updating icon cache...')
    call(['gtk-update-icon-cache', '-qtf', path.join(datadir, 'icons', 'hicolor')])

print('Compiling Python module to bytecode...')
moduledir = sysconfig.get_path('purelib', vars={'base': destdir})
compile_dir(path.join(moduledir, 'jack_mixer'), optimize=1, stripdir=destdir)
