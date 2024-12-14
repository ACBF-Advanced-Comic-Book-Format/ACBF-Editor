"""fontselectiondialog.py - Choose font

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

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
import io
from PIL import Image, ImageDraw, ImageFont

try:
  from . import constants
  from . import preferences
except:
  import constants
  import preferences

class FontSelectionDialog(gtk.Dialog):
    
    """Font Selection dialog."""
    
    def __init__(self, window, font_type, selected_font):
        self._window = window
        gtk.Dialog.__init__(self, 'Font Selection: ' + font_type, window, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                                  (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        self.set_resizable(True)
        self.set_border_width(8)
        
        self.preferences = preferences.Preferences()
        
        self.font_type = font_type
        self.unique_font_families = []

        hbox = gtk.HBox(False, 10)

        # list of available fonts
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.ShadowType.ETCHED_IN)
        sw.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        if self.preferences.get_value("hidpi") == 'True':
          self.ui_scale_factor = 2
        else:
          self.ui_scale_factor = 1
        sw.set_size_request(250 * self.ui_scale_factor, 200 * self.ui_scale_factor)
        
        hbox.pack_start(sw, True, True, 0)

        store = self.create_model()

        self.treeView = gtk.TreeView(store)
        self.treeView.set_rules_hint(True)
        sw.add(self.treeView)
        
        selected_font_family = constants.FONTS_LIST[selected_font][0]
        selected_font_style = constants.FONTS_LIST[selected_font][2]
        for i in range(len(store)):
          if store[i][0] == selected_font_family:
            self.treeView.set_cursor(i, start_editing=True)

        self.create_columns(self.treeView)

        # font drawing
        vbox = gtk.VBox(False, 10)

        font_style_hbox = gtk.HBox(False, 10)
        label = gtk.Label()
        label.set_markup('<b>Font Style: </b>')
        font_style_hbox.pack_start(label, False, True, 0)
        self.font_style_label = gtk.Label(selected_font_style)
        font_style_hbox.pack_start(self.font_style_label, False, True, 0)
        vbox.pack_start(font_style_hbox, True, True, 0)

        self.font_style_buttons_hbox = gtk.HBox(False, 10)
        self.set_font_style_buttons(selected_font_family, selected_font_style)
        vbox.pack_start(self.font_style_buttons_hbox, True, True, 0)

        label = gtk.Label("Font Preview:")
        vbox.pack_start(label, True, True, 0)

        self.font_image = gtk.Image()
        self.font_image.set_from_stock(gtk.STOCK_BOLD, gtk.IconSize.LARGE_TOOLBAR)
        self.get_font_preview(selected_font_family)

        vbox.pack_start(self.font_image, True, True, 0)
        hbox.pack_start(vbox, True, True, 0)
        
        self.vbox.pack_start(hbox, True, True, 0)
        self.show_all()
        self.treeView.connect("cursor-changed", self.on_cursor_changed)
        self.treeView.connect("row-activated", self.on_activated)

        # adjust scroll window
        scroll_adjustment = self.treeView.get_cursor()[0][0]/float(len(self.unique_font_families))*(self.treeView.get_vadjustment().get_upper() - self.treeView.get_vadjustment().get_lower())
        if scroll_adjustment > self.treeView.get_vadjustment().get_upper():
          scroll_adjustment = self.treeView.get_vadjustment().get_upper()
        self.treeView.get_vadjustment().set_value(scroll_adjustment)

    def create_model(self):
        store = gtk.ListStore(str)
        for font in constants.FONTS_LIST:
          self.unique_font_families.append(font[0])
        self.unique_font_families = list(set(self.unique_font_families))
        self.unique_font_families.sort()
        for font in self.unique_font_families:
          store.append([font])
        return store

    def create_columns(self, treeView):
        rendererText = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Font Name", rendererText, text=0)
        column.set_sort_column_id(0)
        treeView.append_column(column)

    def return_font_idx(self):
        font_family = self.unique_font_families[self.treeView.get_cursor()[0][0]]
        font_style = self.font_style_label.get_label()
        for idx, font in enumerate(constants.FONTS_LIST):
          if font_family == font[0] and font_style == font[2]:
            self._window.font_idx = idx

    def on_cursor_changed(self, widget, *args):
        self.set_font_style_buttons(self.unique_font_families[widget.get_cursor()[0][0]], None)
        self.get_font_preview(self.unique_font_families[widget.get_cursor()[0][0]])
        self.return_font_idx()

    def on_activated(self, widget, *args):
        self.return_font_idx()
        self.response(gtk.ResponseType.OK)
        gtk.Widget.destroy(self)

    def get_font_preview(self, font_family):
        for font in constants.FONTS_LIST:
          if font_family == font[0] and self.font_style_label.get_label() == font[2]:
              font_path = font[1]
        font_image = Image.new("RGB", (200 * self.ui_scale_factor,100 * self.ui_scale_factor), "#fff")
        draw = ImageDraw.Draw(font_image)
        font = ImageFont.truetype(font_path, 20 * self.ui_scale_factor)
        draw.text((10 * self.ui_scale_factor, 10 * self.ui_scale_factor), "AaBbCc DdEeFf", font=font, fill="#000")
        draw.text((10 * self.ui_scale_factor, 55 * self.ui_scale_factor), "ľščťžý áíéúäňô", font=font, fill="#000")
        pixbuf_image = pil_to_pixbuf(font_image, "#000")
        self.font_image.set_from_pixbuf(pixbuf_image)

    def on_font_style_button_changed(self, widget, *args):
        if widget.get_active():
          self.font_style_label.set_label(widget.label)
          self.get_font_preview(self.unique_font_families[self.treeView.get_cursor()[0][0]])
          self.return_font_idx()
        
    def set_font_style_buttons(self, font_family, font_style):
        for i in self.font_style_buttons_hbox.get_children():
          i.destroy()
        for font in constants.FONTS_LIST:
          if font_family == font[0]:
            if len(self.font_style_buttons_hbox.get_children()) == 0:
              button = gtk.RadioButton()
              self.font_style_label.set_label(font[2])
            else:
              button = gtk.RadioButton(group=button)
            if font_style == font[2]:
              button.set_active(True)
              self.font_style_label.set_label(font[2])
            button.label = font[2]
            button.connect('toggled', self.on_font_style_button_changed)
            self.font_style_buttons_hbox.pack_start(button, True, False, 0)
        self.font_style_buttons_hbox.show_all()

def pil_to_pixbuf(PILImage, BGColor):
        bcolor = Gdk.RGBA()
        Gdk.RGBA.parse(bcolor, BGColor)
        bcolor = (int(bcolor.red*255), int(bcolor.green*255), int(bcolor.blue*255))
        try:
          PILImage = PILImage.convert("RGBA")
          bg = Image.new("RGB", PILImage.size, bcolor)
          bg.paste(PILImage,PILImage)

          with io.BytesIO() as dummy_file:
            bg.save(dummy_file, "ppm")
            contents = dummy_file.getvalue()

          loader = GdkPixbuf.PixbufLoader()
          loader.write(contents)
          pixbuf = loader.get_pixbuf()
          loader.close()
          return pixbuf
        except:
          bg = Image.new("RGB", (150 * self.ui_scale_factor, 200 * self.ui_scale_factor), bcolor)
          with io.BytesIO() as dummy_file:
            bg.save(dummy_file, "ppm")
            contents = dummy_file.getvalue()

          loader = GdkPixbuf.PixbufLoader()
          loader.write(contents)
          pixbuf = loader.get_pixbuf()
          loader.close()
          return pixbuf

