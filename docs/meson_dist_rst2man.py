#!/usr/bin/env python
"""Create/Update man page(s) from ReST source file(s) to be included in source distribution."""

import argparse
import shutil
import sys
from os import chdir, environ, getcwd
from os.path import join

from subprocess import run

build_root = environ.get("MESON_BUILD_ROOT")
dist_root = environ.get("MESON_DIST_ROOT")
source_root = environ.get("MESON_SOURCE_ROOT")

ap = argparse.ArgumentParser()
ap.add_argument("-v", "--verbose", action="store_true", help="Be more verbose.")
ap.add_argument("man_page", nargs="*", help="Man page(s) to create.")
args = ap.parse_args()

if args.verbose:
    print("cwd:", getcwd())
    print("build root:", build_root)
    print("dist root:", dist_root)
    print("source root:", source_root)
    print("sys.argv:", sys.argv)

for man in args.man_page:
    target = join("docs", man)
    dst = join(dist_root, "docs", man)

    print("Creating man page '%s'" % target)
    cmd = ["ninja"]

    if args.verbose:
        cmd += ["-v"]

    cmd += [target]

    chdir(build_root)
    proc = run(cmd)

    if proc.returncode != 0:
        sys.exit("'ninja' returned non-zero (%i) for target '%s'." % (proc.returncode, target))

    shutil.copy(target, dst)
