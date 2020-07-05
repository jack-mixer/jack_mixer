#!/usr/bin/env python
"""Distutils Setuptools file to build the _jack_mixer extension module from the Cython source."""

import os
import sys
from os.path import abspath, dirname, join
from subprocess import check_output

from setuptools import setup
from distutils.extension import Extension
from Cython.Build import cythonize


SRC_DIR = dirname(abspath(__file__))

sources = [join(SRC_DIR, source) for source in [
    "_jack_mixer.pyx",
    "jack_mixer.c",
    "log.c",
    "memory_atomic.c",
    "scale.c",
]]

pkgconf_modules = ["glib-2.0", "jack"]

include_dirs = []
for mod in pkgconf_modules:
    try:
        res = check_output(["pkg-config", "--cflags-only-I", mod]).decode()
    except:
        sys.exit("Could not find required pkgconf module '%s'. Aborting." % mod)
    else:
        include_dirs.extend([inc[2:] for inc in res.split() if inc.startswith("-I")])

libraries = []
for mod in pkgconf_modules:
    try:
        res = check_output(["pkg-config", "--libs-only-l", mod]).decode()
    except:
        sys.exit("Could not find required pkgconf module '%s'. Aborting." % mod)
    else:
        libraries.extend([lib[2:] for lib in res.split() if lib.startswith("-l")])

define_macros = [
    ("LOG_LEVEL", 2),
]

cython_directives = {
    'language_level': 3,
}

extensions = cythonize(
    [
        Extension(
            "_jack_mixer",
            sources=sources,
            language="c",
            define_macros=define_macros,
            include_dirs=include_dirs,
            libraries=libraries,
        )
    ],
    compiler_directives=cython_directives
)

setup(
    name="jack_mixer",
    version="12",
    description="A GTK+ JACK audio mixer application",
    keywords="mixer,audio,music,jack,gtk",
    license="GPL2+",
    author="Nedko Arnaudov",
    author_email="nedko (a.t) arnaudov (dot) name",
    maintainer="Frédéric Péters",
    maintainer_email="fpeters (a.t) 0d (dot) be",
    url="https://rdio.space/jackmixer/",
    ext_modules=extensions,
    zip_safe=True,
)
