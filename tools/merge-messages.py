#!/usr/bin/env python3
"""Merge new/updated messages from jack_mixer.pot into existing translations with msgmerge."""

import glob
import os
from os.path import basename, join, splitext
from subprocess import run

LOCALEDIR = join(os.getcwd(), "data", "locale")

for po in glob.glob(join(LOCALEDIR, "*.po")):
    fn = basename(po)
    domain, lang = splitext(fn)[0].rsplit("-", 1)
    pot = join(LOCALEDIR, domain + ".pot")
    print(f"Merging new/updated messages from {pot} into {po} ...")
    run(["msgmerge", "-U", po, pot])
