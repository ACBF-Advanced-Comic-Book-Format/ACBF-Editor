#!/usr/bin/env python3

"""
This script installs or uninstalls ACBF Editor on your system.
-------------------------------------------------------------------------------
Usage: install.py [OPTIONS] COMMAND

Commands:
    install                  Install to /usr/

    uninstall                Uninstall from /usr/

Options:
    --dir <directory>        Install or uninstall in <directory>
                             instead of /usr/local

    --no-mime                Do not install the file manager thumbnailer
                             or register new mime type for x-acbf.
"""

import os
import sys
import getopt
import shutil

source_dir = os.path.dirname(os.path.realpath(__file__))
install_dir = '/usr/'
install_mime = True

# Files to be installed, as (source file, destination directory)
FILES = (('src/acbfdocument.py', 'share/acbfe/src'),
         ('src/acbfe.py', 'share/acbfe/src'),
         ('src/constants.py', 'share/acbfe/src'),
         ('src/editstylesdialog.py', 'share/acbfe/src'),
         ('src/filechooser.py', 'share/acbfe/src'),
         ('src/fileprepare.py', 'share/acbfe/src'),
         ('src/fontselectiondialog.py', 'share/acbfe/src'),
         ('src/frames_editor.py', 'share/acbfe/src'),
         ('src/main.py', 'share/acbfe/src'),
         ('src/portability.py', 'share/acbfe/src'),
         ('src/preferences.py', 'share/acbfe/src'),
         ('src/prefsdialog.py', 'share/acbfe/src'),
         ('src/text_layer.py', 'share/acbfe/src'),
         ('src/toolbar.py', 'share/acbfe/src'),
         ('images/acbfe.png', 'share/acbfe/images'),
         ('images/acbf.svg', 'share/acbfe/images'),
         ('acbfe.desktop', 'share/applications'),
         ('images/16x16/acbfe.png', 'share/icons/hicolor/16x16/apps'),
         ('images/22x22/acbfe.png', 'share/icons/hicolor/22x22/apps'),
         ('images/24x24/acbfe.png', 'share/icons/hicolor/24x24/apps'),
         ('images/32x32/acbfe.png', 'share/icons/hicolor/32x32/apps'),
         ('images/48x48/acbfe.png', 'share/icons/hicolor/48x48/apps'),
         ('images/acbfe.svg', 'share/icons/hicolor/scalable/apps'),
         ('images/acbfe.xpm', 'share/pixmaps'))

# Symlinks to be created, as (target, symlink)
LINKS = (('../share/acbfe/src/acbfe.py', 'bin/acbfe'),)

# Mime files to be installed, as (source file, destination directory)
MIME_FILES = (('acbf.xml', 'share/mime/packages'),
              ('images/16x16/application-x-acbf.png',
                'share/icons/hicolor/16x16/mimetypes'),
              ('images/22x22/application-x-acbf.png',
                'share/icons/hicolor/22x22/mimetypes'),
              ('images/24x24/application-x-acbf.png',
                'share/icons/hicolor/24x24/mimetypes'),
              ('images/32x32/application-x-acbf.png',
                'share/icons/hicolor/32x32/mimetypes'),
              ('images/48x48/application-x-acbf.png',
                'share/icons/hicolor/48x48/mimetypes'))

def info():
    """Print usage info and exit."""
    print(__doc__)
    sys.exit(1)

def install(src, dst):
    """Copy <src> to <dst>. The <src> path is relative to the source_dir and
    the <dst> path is a directory relative to the install_dir.
    """
    try:
        dst = os.path.join(install_dir, dst, os.path.basename(src))
        src = os.path.join(source_dir, src)
        assert os.path.isfile(src)
        assert not os.path.isdir(dst)
        if not os.path.isdir(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        shutil.copy(src, dst)
        print('Installed', dst)
    except Exception:
        print('Could not install', dst)

def uninstall(path):
    """Remove the file or directory at <path>, which is relative to the 
    install_dir.
    """
    try:
        path = os.path.join(install_dir, path)
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            return
        print('Removed', path)
    except Exception:
        print('Could not remove', path)

def make_link(src, link):
    """Create a symlink <link> pointing to <src>. The <link> path is relative
    to the install_dir, and the <src> path is relative to the full path of
    the created link.
    """
    try:
        link = os.path.join(install_dir, link)
        if os.path.isfile(link) or os.path.islink(link):
            os.remove(link)
        if not os.path.exists(os.path.dirname(link)):
            os.makedirs(os.path.dirname(link))
        os.symlink(src, link)
        print('Symlinked', link)
    except:
        print('Could not create symlink', link)

def check_dependencies():
    """Check for required and recommended dependencies."""
    required_found = True
    recommended_found = True
    print('Checking dependencies ...\n')
    print('Required dependencies:')
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk
        from gi.repository import GObject
        print('    Gtk 3.0 ..................... OK')
    except ImportError:
        print('    !!! Gtk 3.0 ................. Not found')
        required_found = False
    try:
        import lxml
        print('    python-lxml ................. OK')
    except ImportError:
        print('    !!! python-lxml ............. Not found')
        required_found = False
    try:
        import matplotlib
        assert matplotlib.__version__ >= '0.99'
        print('    python-matplotlib ........... OK')
    except ImportError:
        print('    !!! python-matplotlib ....... Not found')
        required_found = False
    except AssertionError:
        print('    !!! python-matplotlib ....... version', matplotlib.__version__, end=' ')
        print('found')
        print('Required matplotlib version is: 0.99 or higher')
        sys.exit(1)
    try:
        import cv2
        print('    open cv ..................... OK')
    except ImportError:
        print('    !!! open cv ................. Not found')
        required_found = False
    try:
        from PIL import Image
        try:
          im_ver = Image.__version__
          im_ver_major = int(Image.__version__.split('.')[0])
        except AttributeError:
          im_ver = Image.VERSION
          im_ver_major = int(Image.VERSION.split('.')[0])
        assert im_ver_major >= 9
        print('    Python Imaging Library ...... OK')
    except ImportError:
        print('    !!! Python Imaging Library .. Not found')
        required_found = False
    except AssertionError:
        print('    !!! Python Imaging Library .. version', im_ver, end=' ')
        print('found')
        print('    !!! Python Imaging Library 1.1.5 or higher is required')
        required_found = False
    try:
        import patoolib
        print('    patool ...................... OK')
    except ImportError:
        print('    !!! patool .................. Not found')
        required_found = False
    
    try:
        import cairo
        gi.require_foreign('cairo')
        gi.require_foreign('cairo', 'Surface')
    except ImportError:
        print('    !!! python3-gi-cairo ........ Not found')
        required_found = False
    
    if not required_found:
        print('\nCould not find all required dependencies!')
        print('Please install them and try again.')
        sys.exit(1)
    print()


# ---------------------------------------------------------------------------
# Parse the command line.
# ---------------------------------------------------------------------------
try:
    opts, args = getopt.gnu_getopt(sys.argv[1:], '', ['dir=', 'no-mime'])
except getopt.GetoptError:
    info()
for opt, value in opts:
    if opt == '--dir':
        install_dir = value
        if not os.path.isdir(install_dir):
            print('\n!!! Error:', install_dir, 'does not exist.') 
            info()
    elif opt == '--no-mime':
        install_mime = False

# ---------------------------------------------------------------------------
# Install ACBF Editor.
# ---------------------------------------------------------------------------
if args == ['install']:
    check_dependencies()
    print('Installing ACBF Editor to', install_dir, '...\n')
    if not os.access(install_dir, os.W_OK):
        print('You do not have write permissions to', install_dir)
        sys.exit(1)
    for src, dst in FILES:
        install(src, dst)
    for src, link in LINKS:
        make_link(src, link)
    if install_mime:
        for src, dst in MIME_FILES:
            install(src, dst)
        os.popen('update-mime-database "%s"' % 
            os.path.join(install_dir, 'share/mime'))
        print('\nUpdated mime database (added .acbf file type.)')
    os.utime(os.path.join(install_dir, 'share/icons/hicolor'), None)

# ---------------------------------------------------------------------------
# Uninstall ACBF Editor.
# ---------------------------------------------------------------------------
elif args == ['uninstall']:
    print('Uninstalling ACBF Editor from', install_dir, '...\n')
    uninstall('share/acbfe')
    uninstall('share/applications/acbfe.desktop')
    uninstall('share/icons/hicolor/16x16/apps/acbfe.png')
    uninstall('share/icons/hicolor/22x22/apps/acbfe.png')
    uninstall('share/icons/hicolor/24x24/apps/acbfe.png')
    uninstall('share/icons/hicolor/32x32/apps/acbfe.png')
    uninstall('share/icons/hicolor/48x48/apps/acbfe.png')
    uninstall('share/icons/hicolor/scalable/apps/acbfe.svg')
    uninstall('share/pixmaps/acbfe.xpm')
    for _, link in LINKS:
        uninstall(link)
    for src, path in MIME_FILES:
        uninstall(os.path.join(path, os.path.basename(src)))
else:
    info()

