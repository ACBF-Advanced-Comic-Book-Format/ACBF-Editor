#!/usr/bin/env python
"""ACBF Editor - Editor for ACBF documents

Copyright (C) 2013-2018 Robert Kubik
https://github.com/GeoRW/ACBF-Editor
"""
# -------------------------------------------------------------------------
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# -------------------------------------------------------------------------

from __future__ import annotations

import getopt
import gettext
import os
import sys
from typing import Any


try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
except ImportError as e:
    print("GTK4 version 4.10.0 or higher is required to run ACBF Editor.")
    print(e)
    sys.exit(1)
except ValueError as e:
    print("GTK4 version 4.10.0 or higher is required to run ACBF Editor.")
    print(e)
    sys.exit(1)

# Don't want to require an exact version but a minimum one
if Gtk.get_minor_version() < 10:
    print("GTK4 version 4.10.0 or higher is required to run ACBF Editor.")
    print(f"Installed GTK4 version is: {Gtk.get_major_version()}.{Gtk.get_minor_version()}")
    sys.exit(1)

import constants
import main


def print_help() -> None:
    print("")
    print("Usage:")
    print("  acbfe [OPTION...] [PATH_TO_FILENAME]")
    print("")
    print("Options:")
    print("  -h, --help                Show this help and exit.")
    print("  -i [filename], --input    Input file to load")
    print("  -o [filename], --output   Output file to save")
    print("  -f [format], --format     Format of the output images (JPG, WEBP ...)")
    print("  -q [1-100], --quality     Output image quality")
    print("  -r [geometry], --resize   Resize images (64x64>, 526x526<)")
    print("  -l [filter], --filter     Resize filter (default is ANTIALIAS)")
    print("  -t [lang] -- text_layer   Output text layer")
    print("")
    print("Example:")
    print(r"  acbfe -i comic_book.cbr -o comic_book.cbz -f WEBP -q 91 -r 64x64\> -f NEAREST -t sk")
    print("")
    sys.exit(1)


def run() -> None:
    """Run the program."""
    # Use gettext translations as found in the source dir, otherwise based on the install path.

    # TODO gettext
    if os.path.isdir(os.path.join(constants.BASE_DIR, "messages")):
        gettext.install("acbfe", os.path.join(constants.BASE_DIR, "messages"))
    else:
        gettext.install("acbfe", os.path.join(constants.BASE_DIR, "share/locale"))

    open_path = None
    output_file = None

    print("ACBF Editor version " + constants.VERSION + " Copyright 2013-2025 Robert Kubik.")
    print("Licensed under the GNU General Public License. https://github.com/GeoRW/ACBF-Editor")

    try:
        opts, args = getopt.gnu_getopt(
            sys.argv[1:],
            "hi:o:f:q:r:l:t:",
            [
                "help",
                "input",
                "output",
                "format",
                "resize",
                "filter",
                "text-layer",
            ],
        )
    except getopt.GetoptError as err:
        print(str(err))
        print_help()
    for opt, value in opts:
        if opt in ("-h", "--help"):
            print_help()
        elif opt in ("-i", "--input"):
            open_path = value
        elif opt in ("-o", "--output"):
            output_file = value

    # Create data (.local/share/acbfe) and config (.config/acbfe) directories
    if not os.path.exists(constants.DATA_DIR):
        os.makedirs(constants.DATA_DIR, 0o700)
    if not os.path.exists(constants.CONFIG_DIR):
        os.makedirs(constants.CONFIG_DIR, 0o700)

    if len(args) >= 1:
        open_path = os.path.abspath(args[0])

    class MyApp(Gtk.Application):
        def __init__(self, **kwargs: Any):
            super().__init__(**kwargs)
            self.connect("activate", self.on_activate)

        def on_activate(self, app: Gtk.Application) -> None:
            window = main.MainWindow(
                application=app,
                open_path=open_path,
                output_file=output_file,
                cmd_options=opts,
            )
            window.present()

    app = MyApp(application_id="org.acbf.editor")
    app.run()


if __name__ == "__main__":
    run()
