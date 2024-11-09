"""toolbar.py - Toolbar for main window.

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

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk

class Toolbar(gtk.Toolbar):

    def __init__(self, window):
        gtk.Toolbar.__init__(self)
        self._window = window

        self.set_orientation(gtk.Orientation.HORIZONTAL)
        self.set_style(gtk.ToolbarStyle.ICONS)
        if self._window.preferences.get_value("hidpi") == 'True':
          self.set_icon_size(gtk.IconSize.DIALOG)
        else:
          self.set_icon_size(gtk.IconSize.SMALL_TOOLBAR)
        self.set_border_width(5)

        tool_button = gtk.ToolButton()
        tool_button.set_stock_id(gtk.STOCK_OPEN)
        tool_button.set_tooltip_text('Open File')
        tool_button.connect("clicked", self._window.open_file)
        self.insert(tool_button, 0)

        tool_button = gtk.ToolButton()
        tool_button.set_stock_id(gtk.STOCK_PREFERENCES)
        tool_button.set_tooltip_text('Preferences')
        tool_button.connect("clicked", self._window.open_preferences)
        self.insert(tool_button, 1)

        tool_button = gtk.ToolButton()
        tool_button.set_stock_id(gtk.STOCK_ABOUT)
        tool_button.set_tooltip_text('About')
        tool_button.connect("clicked", self._window.show_about_window)
        self.insert(tool_button, 2)

        self.insert(gtk.SeparatorToolItem(), 3)

        self.contents_button = gtk.ToolButton()
        self.contents_button.set_stock_id(gtk.STOCK_INDEX)
        self.contents_button.set_tooltip_text('Table of Contents')
        self.contents_button.connect("clicked", self._window.edit_contents)
        self.contents_button.set_sensitive(False)
        self.insert(self.contents_button, 4)
 
        self.frames_button = gtk.ToolButton()
        self.frames_button.set_stock_id(gtk.STOCK_PAGE_SETUP)
        self.frames_button.set_tooltip_text('Frames/Text Areas Definition')
        self.frames_button.connect("clicked", self._window.edit_frames)
        self.insert(self.frames_button, 5)

        self.font_button = gtk.ToolButton()
        self.font_button.set_stock_id(gtk.STOCK_SELECT_FONT)
        self.font_button.set_tooltip_text('Font/Style Definitions')
        self.font_button.connect("clicked", self._window.edit_styles)
        self.insert(self.font_button, 6)
        
        self.insert(gtk.SeparatorToolItem(), 7)
 
        self.save_button = gtk.ToolButton()
        self.save_button.set_stock_id(gtk.STOCK_SAVE)
        self.save_button.set_tooltip_text('Save')
        self.save_button.connect("clicked", self._window.save_file)
        self.insert(self.save_button, 8)

        self.insert(gtk.SeparatorToolItem(), 9)

        self.language = gtk.ComboBoxText()
        lang_list = []
        for lang in self._window.acbf_document.languages:
          if lang[0] not in lang_list:
            lang_list.append(lang[0])
            self.language.append_text(lang[0])
        self.language.set_active(0)
        self.language.connect('changed', self._window.change_language)
        language_toolitem = gtk.ToolItem()
        language_toolitem.add(self.language)
        self.insert(language_toolitem, 10)

    def update(self):
        self.language.destroy()
        self.language = gtk.ComboBoxText()
        lang_list = []
        for lang in self._window.acbf_document.languages:
          if lang[0] not in lang_list:
            lang_list.append(lang[0])
            self.language.append_text(lang[0])
        self.language.set_active(0)
        self.language.connect('changed', self._window.change_language)
        language_toolitem = gtk.ToolItem()
        language_toolitem.add(self.language)
        language_toolitem.set_tooltip_text('Language layer for meta-data')
        self.insert(language_toolitem, 10)

        self.show_all()
