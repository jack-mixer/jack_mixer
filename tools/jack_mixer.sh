#!/bin/bash

if ! ls -a builddir/jack_mixer/_jack_mixer.*.so >/dev/null 2>&1 ; then
    echo "'_jack_mixer' extension module not found."
    echo "This script is meant to be run from a jack_mixer source directory"
    echo "Make sure that you have built jack_mixer with meson and created"
    echo "the language translation files with ./tools/compile-messages.py."
    exit 1
fi

export PYTHONPATH=".:./builddir:$PYTHONPATH"
export LOCALEDIR="data/locale"
exec "${PYTHON:-python3}" -m jack_mixer "$@"
