Installation
============

**jack_mixer** uses [meson] and Python [setuptools] for building, installation
and packaging.

## Requirements

Build requirements:

 * GCC (version 9.x or 10.x recommended, package `build-essential` on Debian/Ubuntu)
 * meson
 * [ninja]
 * Python headers (`python3-dev`)
 * [JACK] headers (`libjack-jackd2-dev` (recommended) or `libjack-dev`)
 * glib2 headers (`libglib-2.0-dev`)
 * [Cython] (optional, required if building from a Git checkout)

Runtime requirements:

 * Python (at least 3.5)
 * [Pygobject]
 * [pycairo]
 * JACK server (`jackd2` (recommended) or `jackd`)

Optional run-time dependencies:

* [pyxdg] - For saving your preferences (strongly recommended)
* [NSM] - For NSM session management support


## Building

Compile `jack_mix_box`:

```console
meson --prefix=/usr builddir
meson compile -C buildir
```

Compile Python C extension:
```console
python setup.py build
```

## Installation

```console
[sudo] python setup.py install --prefix=/usr --optimize=1 --skip-build
[sudo] meson install -C builddir
```

For packagers: to install all files under a destination directory other than
the filesystem root, use the `--root` option for `python setup.py install`
and set the `DESTDIR` environment variable for `meson install`. For example:

```console
export DESTDIR="/tmp/jack_mixer-install-root"
python setup.py install --prefix=/usr --root="$DESTDIR" --optimize=1 --skip-build
meson install -C builddir
```


[Cython]: https://cython.org/
[JACK]: https://jackaudio.org/
[meson]: https://mesonbuild.com/
[ninja]: https://ninja-build.org/
[NSM]: https://github.com/linuxaudio/new-session-manager
[pycairo]: https://pypi.org/project/pycairo/
[PyGObject]: https://pypi.org/project/PyGObject/
[pyxdg]: https://freedesktop.org/wiki/Software/pyxdg/
[setuptools]: https://docs.python.org/3/distributing/index.html
