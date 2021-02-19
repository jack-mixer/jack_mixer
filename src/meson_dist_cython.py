#!/usr/bin/env python

import argparse
import sys
from os import environ, getcwd
from os.path import exists, join, splitext

from subprocess import run

build_root = environ.get("MESON_BUILD_ROOT")
dist_root = environ.get("MESON_DIST_ROOT")
source_root = environ.get("MESON_SOURCE_ROOT")

ap = argparse.ArgumentParser()
ap.add_argument('-v', '--verbose', action="store_true", help="Be more verbose.")
ap.add_argument('pyx', nargs="*", help="Cython source files (*.pyx).")
args = ap.parse_args()

if args.verbose:
    print("cwd:", getcwd())
    print("build root:", build_root)
    print("dist root:", dist_root)
    print("source root:", source_root)
    print("sys.argv:", sys.argv)

for pyx in args.pyx:
    src = join(source_root, 'src', pyx)
    dst = join(dist_root, "src", splitext(pyx)[0] + '.c')

    if exists(src):
        print("Cythonizing source file '%s'..." % src)
        print("Output file: '%s'" % dst)
        cmd = ["cython"]

        if args.verbose:
            cmd += ["-v"]

        cmd += ["-o", dst, src]
        try:
            proc = run(cmd)

            if proc.returncode != 0:
                sys.exit("cython returned non-zero (%i) for '%s'." %
                         (proc.returncode, pyx))
        except FileNotFoundError:
            sys.exit("The 'cython' program was not found but is required to build a "
                     "distribution.\nPlease install Cython from: "
                     "https://pypi.org/project/Cython/")
