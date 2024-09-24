#!/usr/bin/env python

"""ACBF Editor - Editor for ACBF documents

Copyright (C) 2013-2018 Robert Kubik
https://launchpad.net/~just-me
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


import os
import sys
import gettext
import getopt

#Check for PyGTK and PIL dependencies.
try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, GdkPixbuf, Adw
    #assert Gtk.gtk_version >= (2, 12, 0)
    #assert Gtk.pygtk_version >= (2, 12, 0)
except AssertionError:
    print("You don't have the required versions of GTK+ and/or PyGTK", end=' ')
    print('installed.')
    print('Installed GTK+ version is: %s' % (
        '.'.join([str(n) for n in Gtk.gtk_version])))
    print('Required GTK+ version is: 4.12.0 or higher\n')
    print('Installed PyGTK version is: %s' % (
        '.'.join([str(n) for n in Gtk.pygtk_version])))
    print('Required PyGTK version is: 4.12.0 or higher')
    sys.exit(1)
except ImportError:
    print('PyGTK version 4.12.0 or higher is required to run Comix.')
    print('No version of PyGTK was found on your system.')
    sys.exit(1)

try:
    from PIL import Image
    try:
      im_ver = Image.__version__
    except AttributeError:
      im_ver = Image.__version__
    assert Image.__version__ >= '1.1.5'
except AssertionError:
    print("You don't have the required version of the Python Imaging", end=' ')
    print('Library (PIL) installed.')
    print('Installed PIL version is: %s' % Image.__version__)
    print('Required PIL version is: 1.1.5 or higher')
    sys.exit(1)
except ImportError:
    print('Python Imaging Library (PIL) 1.1.5 or higher is required.')
    print('No version of the Python Imaging Library was found on your', end=' ')
    print('system.')
    sys.exit(1)

import constants
import main

def print_help():
    print('')
    print('Usage:')
    print('  acbfe [OPTION...] [PATH_TO_FILENAME]')
    print('')
    print('Options:')
    print('  -h, --help                Show this help and exit.')
    print('  -i [filename], --input    Input file to load')
    print('  -o [filename], --output   Output file to save')
    print('  -f [format], --format     Format of the output images (JPG, WEBP ...)')
    print('  -q [1-100], --quality     Output image quality')
    print('  -r [geometry], --resize   Resize images (64x64>, 526x526<)')
    print('  -l [filter], --filter     Resize filter (default is ANTIALIAS)')
    print('  -t [lang] -- text_layer   Output text layer')
    print('')
    print('Example:')
    print('  acbfe -i comic_book.cbr -o comic_book.cbz -f WEBP -q 91 -r 64x64\> -f NEAREST -t sk')
    print('')
    sys.exit(1)

def run():
    """Run the program."""
    # Use gettext translations as found in the source dir, otherwise based on
    # the install path.

    """print exec_path
    print constants.DATA_DIR
    print constants.CONFIG_DIR
    print constants.HOME_DIR"""

    if os.path.isdir(os.path.join(constants.BASE_DIR, 'messages')):
        gettext.install('acbfe', os.path.join(constants.BASE_DIR, 'messages'))
    else:
        gettext.install('acbfe', os.path.join(constants.BASE_DIR, 'share/locale'))

    open_path = None
    output_file = None

    print('ACBF Editor version ' + constants.VERSION + ' Copyright 2013-2019 Robert Kubik.')
    print('Licensed under the GNU General Public License. https://launchpad.net/acbf')

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'hi:o:f:q:r:l:t:',
            ['help','input', 'output', 'format', 'resize', 'filter', 'text-layer'])
    except getopt.GetoptError as err:
        print(str(err))
        print_help()
    for opt, value in opts:
        if opt in ('-h', '--help'):
            print_help()
        elif opt in ('-i', '--input'):
            open_path = value
        elif opt in ('-o', '--output'):
            output_file = value

    # Create data (.local/share/acbfe) and config (.config/acbfe) directories
    if not os.path.exists(constants.DATA_DIR):
        os.makedirs(constants.DATA_DIR, 0o700)
    if not os.path.exists(constants.CONFIG_DIR):
        os.makedirs(constants.CONFIG_DIR, 0o700)

    if len(args) >= 1:
        open_path = os.path.abspath(args[0])

    class MyApp(Gtk.Application):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.connect('activate', self.on_activate)

        def on_activate(self, app):
            self.window = main.MainWindow(application=app, open_path=open_path, output_file=output_file, cmd_options=opts)
            self.window.present()

    app = MyApp(application_id="org.acbf.editor")
    app.run()


if __name__ == '__main__':
    run()

