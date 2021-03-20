#!/usr/bin/env python3
"""Compile translated message catalog *.po files to *.mo with msgfmt."""

import glob
import os
from os.path import basename, join, splitext
from subprocess import run

LOCALEDIR = join(os.getcwd(), "data", "locale")

for po in glob.glob(join(LOCALEDIR, "*.po")):
    fn = basename(po)
    domain, lang = splitext(fn)[0].rsplit("-", 1)
    langdir = join(LOCALEDIR, lang, "LC_MESSAGES")
    mo = join(langdir, domain + ".mo")
    print(f"Compiling {fn} to {mo} ...")
    os.makedirs(langdir, exist_ok=True)
    run(["msgfmt", "-o", mo, po])
