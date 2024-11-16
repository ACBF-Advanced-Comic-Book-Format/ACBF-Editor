"""prefsdialog.py - Preferences Dialog.

Copyright (C) 2011-2024 Robert Kubik
https://github.com/GeoRW/ACBF
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

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Gdk

try:
  from . import constants
except:
  import constants

class PrefsDialog(gtk.Dialog):
    
    """Preferences dialog."""
    
    def __init__(self, window):
        self._window = window
        gtk.Dialog.__init__(self, 'Preferences', window, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                                  (gtk.STOCK_CLOSE, gtk.ResponseType.CLOSE))
        self.set_resizable(True)
        self.set_border_width(8)
        self.isChanged = False

        notebook = gtk.Notebook()
        notebook.set_border_width(3)

        ## General tab
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(450 * self._window.ui_scale_factor, 255 * self._window.ui_scale_factor)
        tab = gtk.VBox(False, 0)
        tab.set_border_width(5)
        scrolled.add_with_viewport(tab)

        # default language
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('Default language: ')
        label.set_tooltip_text("Default language when adding new attributes (authors, language layers).")
        hbox.pack_start(label, False, False, 0)

        self.default_language = gtk.ComboBoxText()
        self.default_language.set_active(0)
        for idx, lang in enumerate(constants.LANGUAGES):
          if lang != '??#':
            self.default_language.append_text(lang)
          if lang == self._window.preferences.get_value("default_language"):
            self.default_language.set_active(idx - 1)

        hbox.pack_start(self.default_language, False, False, 0)
        self.default_language.connect('changed', self.set_default_language)

        tab.pack_start(hbox, False, False, 0)

        # default comic books dir
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)
        
        label = gtk.Label()
        label.set_markup('Default comics folder: ')
        hbox.pack_start(label, False, False, 0)
        
        self.comics_dir = self._window.preferences.get_value("comics_dir")
        if len(self.comics_dir) > 25:
          comics_dir_label = self.comics_dir[0:25] + ' ...'
        else:
          comics_dir_label = self.comics_dir
        self.comics_dir_button = gtk.Button.new_with_label(comics_dir_label)
        self.comics_dir_button.connect('clicked', self.select_folder)
        
        hbox.pack_start(self.comics_dir_button, False, False, 0)
        tab.pack_start(hbox, False, False, 0)

        # tmpfs
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        self.tmpfs_button = gtk.CheckButton("Custom temporary directory: ")
        self.tmpfs_button.set_border_width(5)
        self.tmpfs_button.set_tooltip_text("Directory where comic archives are unpacked. Use /dev/shm for temporary file storage filesystem (tmpfs) instead of default system temp directory to store in RAM.")
        self.tmpfs_button.connect("toggled", self.set_tmpfs)

        hbox.pack_start(self.tmpfs_button, False, False, 0)

        self.tmpfs_entry = gtk.Entry()
        self.tmpfs_entry.set_text(self._window.preferences.get_value("tmpfs_dir"))
        self.tmpfs_entry.connect('insert_text', self.entry_changed)
        
        hbox.pack_start(self.tmpfs_entry, False, False, 0)

        if self._window.preferences.get_value("tmpfs") == 'True':
          self.tmpfs_button.set_active(True)
          self.tmpfs_entry.set_sensitive(True)
        else:
          self.tmpfs_button.set_active(False)
          self.tmpfs_entry.set_sensitive(False)

        tab.pack_start(hbox, False, False, 0)
        
        # HiDPI
        button = gtk.CheckButton("HiDPI display")
        button.set_border_width(5)
        button.set_tooltip_text("Scale user interface for HiDPI monitor.")
        button.connect("toggled", self.set_hidpi)

        if self._window.preferences.get_value("hidpi") == 'True':
          button.set_active(True)
        else:
          button.set_active(False)

        tab.pack_start(button, False, False, 0)

        notebook.insert_page(scrolled, gtk.Label('General'), -1)

        ## Document Info & Publish Info
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(400 * self._window.ui_scale_factor, 150 * self._window.ui_scale_factor)
        tab = gtk.VBox(False, 0)
        tab.set_border_width(5)
        scrolled.add_with_viewport(tab)

        # Author
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('Default Document Author: ')
        hbox.pack_start(label, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        # first-name
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('  First Name: ')
        hbox.pack_start(label, False, False, 0)

        self.first_name_entry = gtk.Entry()
        try:
          self.first_name_entry.set_text(self._window.preferences.get_value("first_name"))
        except:
          None
        self.first_name_entry.connect('insert_text', self.entry_changed)
        
        hbox.pack_start(self.first_name_entry, False, False, 0)
        tab.pack_start(hbox, False, False, 0)

        # middle-name
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('  Middle Name: ')
        hbox.pack_start(label, False, False, 0)

        self.middle_name_entry = gtk.Entry()
        try:
          self.middle_name_entry.set_text(self._window.preferences.get_value("middle_name"))
        except:
          None
        self.middle_name_entry.connect('insert_text', self.entry_changed)
        
        hbox.pack_start(self.middle_name_entry, False, False, 0)
        tab.pack_start(hbox, False, False, 0)

        # last-name
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('  Last Name: ')
        hbox.pack_start(label, False, False, 0)

        self.last_name_entry = gtk.Entry()
        try:
          self.last_name_entry.set_text(self._window.preferences.get_value("last_name"))
        except:
          None
        self.last_name_entry.connect('insert_text', self.entry_changed)
        
        hbox.pack_start(self.last_name_entry, False, False, 0)
        tab.pack_start(hbox, False, False, 0)

        # nickname
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('  Nickname: ')
        hbox.pack_start(label, False, False, 0)

        self.nick_name_entry = gtk.Entry()
        try:
          self.nick_name_entry.set_text(self._window.preferences.get_value("nickname"))
        except:
          None
        self.nick_name_entry.connect('insert_text', self.entry_changed)
        
        hbox.pack_start(self.nick_name_entry, False, False, 0)
        tab.pack_start(hbox, False, False, 0)

        #
        notebook.insert_page(scrolled, gtk.Label('Document Info'), -1)

        ## Frames/Text Layers Editor
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(400 * self._window.ui_scale_factor, 150 * self._window.ui_scale_factor)
        tab = gtk.VBox(False, 0)
        tab.set_border_width(5)
        scrolled.add_with_viewport(tab)

        # Frames Color
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('  Frames Color: ')
        hbox.pack_start(label, False, False, 0)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self._window.preferences.get_value("frames_color"))
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_frames_color)
        hbox.pack_start(color_button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        # Text Layers Color
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('  Text Layers Color: ')
        hbox.pack_start(label, False, False, 0)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self._window.preferences.get_value("text_layers_color"))
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_text_layers_color)
        hbox.pack_start(color_button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        # Snap to Image Border
        button = gtk.CheckButton("Snap to Image Border")
        button.set_border_width(5)
        button.set_tooltip_text("Snap polygon points to image border when close to it.")
        button.connect("toggled", self.set_snap)

        if self._window.preferences.get_value("snap") == 'True':
          button.set_active(True)
        else:
          button.set_active(False)

        tab.pack_start(button, False, False, 0)

        #
        notebook.insert_page(scrolled, gtk.Label('Frames Editor'), -1)

        # show it
        self.vbox.pack_start(notebook, False, False, 0)
        self.show_all()

        self.connect('response', self.close_preferences)
        self.run()

    def select_folder(self, *args):
      filechooser = gtk.FileChooserDialog(title='Select Folder ...', action=gtk.FileChooserAction.SELECT_FOLDER,
                                buttons=(gtk.STOCK_CANCEL,gtk.ResponseType.CANCEL,gtk.STOCK_OPEN,gtk.ResponseType.OK))

      filechooser.set_current_folder(self._window.preferences.get_value("comics_dir"))

      response = filechooser.run()
      if response != gtk.ResponseType.OK:
        filechooser.destroy()
        return

      self.comics_dir = str(filechooser.get_filename())
      if len(self.comics_dir) > 25:
        comics_dir_label = self.comics_dir[0:25] + ' ...'
      else:
        comics_dir_label = self.comics_dir
      
      self.comics_dir_button.set_label(comics_dir_label)
      self._window.preferences.set_value("comics_dir", self.comics_dir)
      filechooser.destroy()

    def set_hidpi(self, widget):
        if widget.get_active():
          self._window.preferences.set_value("hidpi", "True")
        else:
          self._window.preferences.set_value("hidpi", "False")
        self.isChanged = True
        return True

    def set_snap(self, widget):
        if widget.get_active():
          self._window.preferences.set_value("snap", "True")
        else:
          self._window.preferences.set_value("snap", "False")
        self.isChanged = True
        return True

    def set_text_layers_color(self, widget):
        self._window.preferences.set_value("text_layers_color", widget.get_color().to_string())
        self.isChanged = True
        return True

    def set_frames_color(self, widget):
        self._window.preferences.set_value("frames_color", widget.get_color().to_string())
        self.isChanged = True
        return True

    def set_default_language(self, widget):
        self._window.preferences.set_value("default_language", constants.LANGUAGES[self.default_language.get_active() + 1])
        self.isChanged = True
        return True

    def set_tmpfs(self, widget, *args):
        if self.tmpfs_button.get_active():
          self.tmpfs_entry.set_sensitive(True)
          self._window.preferences.set_value("tmpfs", "True")
          self._window.preferences.set_value("tmpfs_dir", self.tmpfs_entry.get_text())
        else:
          self._window.preferences.set_value("tmpfs", "False")
          self.tmpfs_entry.set_sensitive(False)
        self.isChanged = True
        return True

    def entry_changed(self, widget, *args):
        self.isChanged = True

    def close_preferences(self, *args):
        if self.isChanged:
          self._window.preferences.set_value("tmpfs_dir", self.tmpfs_entry.get_text())
          self._window.preferences.set_value("first_name", self.first_name_entry.get_text())
          self._window.preferences.set_value("middle_name", self.middle_name_entry.get_text())
          self._window.preferences.set_value("last_name", self.last_name_entry.get_text())
          self._window.preferences.set_value("nickname", self.nick_name_entry.get_text())
