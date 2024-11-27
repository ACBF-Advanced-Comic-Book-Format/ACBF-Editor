"""filechooser.py - FileChooserDialog implementation.

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

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
import os
import sys

try:
  from . import constants
  from . import fileprepare
  from . import preferences
except:
  import constants
  import fileprepare
  import preferences

class FileChooserDialog(gtk.FileChooserDialog):
    
    """The normal filechooser dialog used with the "Open" toolbar item."""
    
    def __init__(self, window,
                       title=None,action=gtk.FileChooserAction.OPEN,
                       buttons=(gtk.STOCK_CANCEL,gtk.ResponseType.CANCEL,gtk.STOCK_OPEN,gtk.ResponseType.OK)):
        self._window = window
        gtk.FileChooserDialog.__init__(self, title='Open File',action=gtk.FileChooserAction.OPEN,
                                       buttons=(gtk.STOCK_CANCEL,gtk.ResponseType.CANCEL,gtk.STOCK_OPEN,gtk.ResponseType.OK))
        self.set_default_response(gtk.ResponseType.OK)
        
        self.preferences = preferences.Preferences()
        self.set_current_folder(self.preferences.get_value("comics_dir"))
 
        # filter
        filter = gtk.FileFilter()
        filter.set_name("Comic files")
        filter.add_pattern("*.acbf")
        filter.add_pattern("*.acv")
        filter.add_pattern("*.cbz")
        filter.add_pattern("*.zip")
        filter.add_pattern("*.cbr")
        self.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        self.add_filter(filter)

        #
        self.connect('response', self.return_filename)
        self.run()

    def return_filename(self, widget, response):
        if response == gtk.ResponseType.OK:
          prepared_file = fileprepare.FilePrepare(self, self.get_filename(), self._window.tempdir, True)
          self._window.filename = prepared_file.filename
          self._window.original_filename = self.get_filename()
        self.destroy()

