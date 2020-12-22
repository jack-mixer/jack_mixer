Installation
============

**jack_mixer** uses [meson] and optionally a Python [PEP-517]-compliant build
system for building, installation and packaging.


## Requirements

Build requirements:

 * GCC (version 9.x or 10.x recommended, package `build-essential` on Debian/Ubuntu)
 * meson
 * [ninja]
 * Python headers (`python3-dev`)
 * [JACK] headers (`libjack-jackd2-dev` (recommended) or `libjack-dev`)
 * glib2 headers (`libglib-2.0-dev`)
 * [Cython] (optional, required if building from a Git checkout)
 * [docutils] (optional, `rst2man` required if building from a Git checkout)

Runtime requirements:

 * Python (at least 3.6)
 * [Pygobject]
 * [pycairo]
 * `libjack` and JACK server (`jackd2` (recommended) or `jackd`)

Optional run-time dependencies:

* [pyxdg] - For saving your preferences (strongly recommended)
* [NSM] - For NSM session management support


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


## Building a Python wheel (for maintainers)

1. Make sure you have Python 3, `git` and [pip] installed:
2. Run the following command to build a binary wheel:

```console
pip wheel .
```

This will automatically download the required build tools, e.g. Cython, meson,
ninja, the Python `wheel` package etc. (see the [pyproject.toml] file for
details), build the software with meson and then package it into a wheel, which
will be placed in the project's root directory.

The wheel can be installed with `pip install jack_mixer-*.whl`.


[docutils]: https://pypi.org/project/docutils/
[Cython]: https://cython.org/
[JACK]: https://jackaudio.org/
[meson]: https://mesonbuild.com/
[ninja]: https://ninja-build.org/
[NSM]: https://github.com/linuxaudio/new-session-manager
[options]: https://mesonbuild.com/Build-options.html
[pip]: https://pypi.org/project/pip/
[pycairo]: https://pypi.org/project/pycairo/
[PyGObject]: https://pypi.org/project/PyGObject/
[pyxdg]: https://freedesktop.org/wiki/Software/pyxdg/
[PEP-517]: https://www.python.org/dev/peps/pep-0517/
[pyproject.toml]: ./pyproject.toml
[standard meson options]: https://mesonbuild.com/Builtin-options.html
