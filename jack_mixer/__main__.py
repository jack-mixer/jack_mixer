#!/usr/bin/env python3

import sys

from jack_mixer.app import main

if __name__ == '__main__':
    sys.exit(main() or 0)
