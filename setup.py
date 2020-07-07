#!/usr/bin/env python
"""Setup file to build jack_mixer distribution."""

import argparse
import os
import sys
from glob import glob
from os.path import dirname, exists, isdir, join
from subprocess import check_output

from setuptools import setup
from distutils.extension import Extension
from distutils.version import StrictVersion

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None


# directories need to be relative to this file
SRC_DIR = ""
DATA_DIR = "data"
IMG_DIR = join(DATA_DIR, "art")
PKG_CONFIG = os.environ.get("PKG_CONFIG", "pkg-config")
JACK1_MIN_VERSION = StrictVersion("0.125.0")
JACK2_MIN_VERSION = StrictVersion("1.9.11")

# Compile and run-time library dependencies
pkgconf_dependencies = ["glib-2.0", "jack"]

# Run-time Python distribution dependencies
py_dependencies = [
    "PyGObject",
    "pycairo",
    "pyxdg",
]

# Python C extension source files
sources = [
    "jack_mixer.c",
    "log.c",
    "scale.c",
    # "_jack_mixer.pyx/.c" is append below
]

# Pre-processor defines
define_macros = []

# Extra data files to be installed under Python sys.prefix
data_files = [("share/applications", [join(DATA_DIR, "jack_mixer.desktop")])]

# Directives for Cython .pyx to .c compilation
cython_directives = {
    "language_level": 3,
}


def read(*args):
    """Read a file and return its contents."""
    return open(join(dirname(__file__), *args)).read()


def check_mod_version(mod, *min_versions):
    """Check whether jack version is "new" enough to have jack_port_rename."""
    try:
        res = check_output([PKG_CONFIG, "--modversion", mod])
        ver = StrictVersion(res.decode())
    except Exception as exc:
        sys.exit("Error detecting %s version: %s" % (mod, exc))
    else:
        print("Detected %s version %s." % (mod, ver))
        if (ver.version[0] == 0 and ver >= min_versions[0]) or (
            ver.version[0] == 1 and ver >= min_versions[1]
        ):
            return True
    return False


def get_pkgconfig(modules, option, prefix):
    """Get include dirs or libraries from pkg-config."""
    names = []
    for mod in modules:
        try:
            res = check_output([PKG_CONFIG, option, mod]).decode()
        except:
            sys.exit("Could not find required pkgconf module '%s'. Aborting." % mod)
        else:
            names.extend([item[2:] for item in res.split() if item.startswith(prefix)])
    return names


ap = argparse.ArgumentParser()
ap.add_argument(
    "--debug",
    action="store_true",
    help="Debug build"
)
ap.add_argument(
    "--cythonize",
    action="store_true",
    help="Generate Python extension C source from Cython source if necessary",
)
ap.add_argument(
    "--disable-jackmidi",
    dest="jackmidi",
    action="store_false",
    help="Force disable JACK MIDI support",
)
args, remaining = ap.parse_known_args()
sys.argv[1:] = remaining


if not exists(join(SRC_DIR, "_jack_mixer.c")):
    args.cythonize = True

if args.cythonize and not cythonize:
    sys.exit(
        "Could not import Cython needed to generate '_jack_mixer.c'. "
        "Please install Cython."
    )

if not check_mod_version("jack", JACK1_MIN_VERSION, JACK2_MIN_VERSION):
    sys.exit("JACK version is not recent enough to have 'jack_port_rename' function.")

include_dirs = get_pkgconfig(pkgconf_dependencies, "--cflags-only-I", "-I")
libraries = get_pkgconfig(pkgconf_dependencies, "--libs-only-l", "-l")

for size_dir in os.listdir(IMG_DIR):
    if isdir(join(IMG_DIR, size_dir)):
        images = glob(join(IMG_DIR, size_dir, "*"))
        if images:
            data_files.append(
                (
                    join("share/icons/hicolor", size_dir, "apps"),
                    images,
                )
            )

if args.debug:
    define_macros.append(("LOG_LEVEL", 0))
else:
    define_macros.append(("LOG_LEVEL", 2))


if args.jackmidi:
    define_macros.append(("HAVE_JACK_MIDI", None))

if cythonize:
    sources.append("_jack_mixer.pyx")
else:
    sources.append("_jack_mixer.c")

sources = [join(SRC_DIR, source) for source in sources]

extensions = [
    Extension(
        "jack_mixer._jack_mixer",
        sources=sources,
        language="c",
        define_macros=define_macros,
        include_dirs=include_dirs,
        libraries=libraries,
    )
]

if cythonize:
    extensions = cythonize(extensions, compiler_directives=cython_directives)

setup(
    name="jack_mixer",
    version="13rc1",
    description="A GTK+ JACK audio mixer application",
    long_description=read("README"),
    keywords="mixer,audio,music,jack,gtk",
    license="GPL2+",
    author="Nedko Arnaudov",
    author_email="nedko (a.t) arnaudov (dot) name",
    maintainer="Frédéric Péters",
    maintainer_email="fpeters (a.t) 0d (dot) be",
    url="https://rdio.space/jackmixer/",
    packages=["jack_mixer"],
    package_dir={"jack_mixer": SRC_DIR},
    data_files=data_files,
    ext_modules=extensions,
    install_requires=py_dependencies,
    python_requires=">=3.5",
    entry_points={
        "console_scripts": [
            "jack_mixer=jack_mixer.jack_mixer:main",
        ],
    },
    zip_safe=True,
)
