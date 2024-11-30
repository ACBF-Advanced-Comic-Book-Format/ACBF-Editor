#!/usr/bin/env python3

"""ACBF Editor - Editor for ACBF documents

Copyright (C) 2011-2024 Robert Kubik
https://github.com/ACBF-Advanced-Comic-Book-Format
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
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk as gtk
    from gi.repository import GObject
    gtk_version = (gtk.get_major_version(), gtk.get_minor_version(), gtk.get_micro_version())
    assert GObject.pygobject_version >= (3, 20, 0)
    assert gtk_version >= (3, 20, 0)
except AssertionError:
    print("You don't have the required versions of GTK+ and/or pyGOBject installed.")
    print('Installed GTK+ version is: %s' % (
        '.'.join([str(n) for n in gtk_version])))
    print('Required GTK+ version is: 3.20.0 or higher\n')
    print('Installed pyGOBject version is: %s' % ('.'.join([str(n) for n in GObject.pygobject_version])))
    print('Required pyGOBject version is: 3.20.0 or higher')
    sys.exit(1)
except ImportError:
    print('pyGOBject version 3.20.0 or higher is required to run ACBF Editor.')
    print('No version of pyGOBject was found on your system.')
    sys.exit(1)

try:
    from PIL import Image
    try:
      im_ver = Image.__version__
    except AttributeError:
      im_ver = Image.VERSION
    assert im_ver >= '1.1.5'
except AssertionError:
    print ("You don't have the required version of the Python Imaging Library (PIL) installed.")
    print(('Installed PIL version is: %s' % im_ver))
    print ('Required PIL version is: 1.1.5 or higher')
    sys.exit(1)
except ImportError:
    print ('Python Imaging Library (PIL) 1.1.5 or higher is required.')
    print ('No version of the Python Imaging Library was found on your system.')
    sys.exit(1)

try:
  from . import constants
  from . import main
except Exception:
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
    print('  -x [lang] -- text_export  Export text layer text to output file')
    print('')
    print('Example:')
    print("  acbfe -i comic_book.cbr -o comic_book.cbz -f WEBP -q 91 -r 64x64\\> -f NEAREST -t sk")
    print('  acbfe -i comic_book.cbr -o text_layer_sk.txt -x sk')
    print('')
    sys.exit(1)

def run():
    """Run the program."""
    # Use gettext translations as found in the source dir, otherwise based on
    # the install path.

    """print(exec_path)
    print(constants.DATA_DIR)
    print(constants.CONFIG_DIR)
    print(constants.HOME_DIR)"""

    if os.path.isdir(os.path.join(constants.BASE_DIR, 'messages')):
        gettext.install('acbfe', os.path.join(constants.BASE_DIR, 'messages'))
    else:
        gettext.install('acbfe', os.path.join(constants.BASE_DIR, 'share/locale'))

    open_path = None
    output_file = None

    print('ACBF Editor version ' + constants.VERSION + ' Copyright 2013-2024 Robert Kubik.')
    print('Licensed under the GNU General Public License. https://github.com/ACBF-Advanced-Comic-Book-Format')

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], 'hi:o:f:q:r:l:t:x:',
            ['help','input', 'output', 'format', 'resize', 'filter', 'text-layer', 'text-export'])
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

    # draw main window
    window = main.MainWindow(open_path=open_path, output_file=output_file, cmd_options=opts)

    # set main window icon
    window.set_icon_from_file(os.path.join(constants.ICON_PATH, 'acbfe.png'))

    try:
        gtk.main()
    except KeyboardInterrupt:
        window.terminate_program()

if __name__ in ('__main__', 'share.acbfe.src.acbfe'):
    run()
