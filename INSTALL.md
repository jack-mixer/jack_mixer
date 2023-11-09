Installation
============

**jack_mixer** uses the [meson] build system for building, installation and
packaging.


## Requirements

Build requirements:

 * GCC (version >= 9.x recommended)
 * meson >= 0.64.0
 * [ninja]
 * Python headers
 * [JACK] headers
 * glib2 headers
 * gettext
 * [Cython] (optional, required if building from a Git checkout)
 * [docutils] (optional, `rst2man` required if building from a Git checkout)

Runtime requirements:

 * Python >= 3.8
 * [Pygobject]
 * [pycairo]
 * JACK library and server

Optional run-time dependencies:

* [appdirs] (for saving your preferences, strongly recommended)
* [NSM] (for NSM session management support)

The run-time Python dependencies are checked by meson when setting up the
build directory. To disable this, use the `-Dcheck-py-modules=false` option to
`meson setup.`


## Building

Building with meson always happens in a special build directory. Set up the
build in the `builddir` sub-directory and configure the build with:

```console
meson setup builddir --prefix=/usr --buildtype=release
```

Then build the software with:

```console
meson compile -C builddir
```

**Note:** *For building **jack_mixer** from source on **debian / Ubuntu**
derrived Linux distributions, please refer to this [wiki page]. If possible,
use your distribution's package manager to install **jack_mixer**.*


## Installation

```console
[sudo] meson install -C builddir
```

**Note for packagers**: to install all files under a destination directory
other than the filesystem root, set the `DESTDIR` environment variable for
`meson install`.

For example:

```console
DESTDIR="/tmp/jack_mixer-install-root" meson install -C builddir
```


## Build options

There are several project-specific [options] to configure the build and the
resulting installation. To see all supported options (including [standard
meson options]) and their possible values run:

```console
meson configure
```

If you have already set up the build directory, you can append its name
to see the current values of all options for this build configuration.

To change an option, pass the build directory and `-Doption=value` to
`meson setup` or `meson configure`. For example:

```console
meson configure builddir -Dgui=disabled
```


## Building a Python wheel (only for special needs)

**Note:** Due to limitations of Python's build ecosystem, the wheel packages
built with the instructions given here, will *not* contain any files used
for system desktop integration, e.g. icons and `.desktop' files, nor man pages
or translation files. Using this method to install jack_mixer is thus not
recommended and mainly provided for testing prurposes.

1. Make sure you have Python 3, `git`, [pip] and the Python [build] package
   installed and your internet connection is online.
2. Run the following command to build a binary wheel:

```console
python -m build -w
```

This will automatically download the required build tools, e.g. Cython, meson,
ninja, the Python `wheel` package etc. (see the [pyproject.toml] file for
details), build the software with meson and then package it into a wheel, which
will be placed in the `dist` directory below the project's root directory.

The wheel can be installed with `python -m pip install dist/jack_mixer-*.whl`.


[docutils]: https://pypi.org/project/docutils/
[build]: https://pypi.org/project/build
[Cython]: https://cython.org/
[JACK]: https://jackaudio.org/
[meson]: https://mesonbuild.com/
[ninja]: https://ninja-build.org/
[NSM]: https://new-session-manager.jackaudio.org/
[options]: https://mesonbuild.com/Build-options.html
[pip]: https://pypi.org/project/pip
[pycairo]: https://pypi.org/project/pycairo/
[PyGObject]: https://pypi.org/project/PyGObject/
[appdirs]: https://pypi.org/project/appdirs/
[PEP-517]: https://www.python.org/dev/peps/pep-0517/
[pyproject.toml]: ./pyproject.toml
[standard meson options]: https://mesonbuild.com/Builtin-options.html
[wiki page]: https://github.com/jack-mixer/jack_mixer/wiki/Installing-on-debian---Ubuntu
