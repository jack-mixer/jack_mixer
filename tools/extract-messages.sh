#!/bin/bash

LOCALEDIR="$(pwd)/data/locale"
POT="$LOCALEDIR/jack_mixer.pot"
VERSION="$(grep -A 5 project meson.build | grep version | cut -d "'" -f 2)"
ARGPARSE_PY="$(python -c 'import argparse; print(argparse.__file__)')"

echo "Extracting translatable messages from argparse and jack_mixer/*.py to $POT."
exec xgettext \
    --package-name=jack_mixer \
    "--package-version=$VERSION" \
    "--msgid-bugs-address=https://github.com/jack-mixer/jack_mixer/issues" \
    --from-code=utf-8 \
    --join-existing \
    -o "$POT" \
    jack_mixer/*.py \
    "$ARGPARSE_PY"
