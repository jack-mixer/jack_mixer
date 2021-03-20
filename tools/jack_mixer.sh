#!/bin/bash

if ! ls -a jack_mixer/_jack_mixer.*.so >/dev/null 2>&1 ; then
    echo "'_jack_mixer' extension module not found."
    echo "This script is meant to be run from a jack_mixer source directory"
    echo "Make sure that you have built jack_mixer with meson."
    exit 1
fi

export PYTHONPATH=".:$PYTHONPATH"
exec python -m jack_mixer "$@"
