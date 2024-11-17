# -*- coding: utf-8 -*-
"""frameseditor.py - Frames/Text Layers Editor Dialog.

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
import io

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf

from PIL import Image
from PIL import ImageColor
import lxml.etree as xml
import re
from xml.sax.saxutils import escape, unescape
from copy import deepcopy
import numpy
import cv2
import cairo
import math

try:
  from . import constants
  from . import text_layer
except:
  import constants
  import text_layer

class FramesEditorDialog(gtk.Dialog):
    
    """Frames Editor dialog."""
    
    def __init__(self, window):
        self._window = window
        gtk.Dialog.__init__(self, title = 'ACBF Editor: Frames/Text Layers Editor', parent = None, flags = gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.set_resizable(True)
        self.set_border_width(8)
        self.set_size_request(1000 * self._window.ui_scale_factor, 700 * self._window.ui_scale_factor)

        self.points = []
        self.root_directory = os.path.dirname(self._window.filename)
        self.selected_page = self._window.acbf_document.bookinfo.find("coverpage/" + "image").get("href").replace("\\", "/")
        self.selected_page_bgcolor = None
        self.page_color_button = gtk.ColorButton()
        self.drawing_frames = False
        self.drawing_texts = False
        self.drawing_rounded_rectangle = True
        self.detecting_bubble = False
        self.scale_factor = 1
        self.transition_dropdown_dict = {0 : "", 1 : "None", 2 : "Fade", 3 : "Blend", 4 : "Scroll Right", 5 : "Scroll Down"}
        self.transition_dropdown_is_active = True
        self.frames_box = gtk.VBox(False, 0)
        self.texts_box = gtk.VBox(False, 0)

        # main screen
        self.main_box = gtk.HBox(False, 0)

        # pages
        self.sidebar = gtk.ScrolledWindow()
        self.sidebar.set_shadow_type(gtk.ShadowType.ETCHED_IN)
        self.sidebar.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        self.sidebar.set_size_request(250 * self._window.ui_scale_factor, 500 * self._window.ui_scale_factor)

        directories = []
        self.pages_tree = gtk.TreeView()
        tree_pages = gtk.TreeViewColumn()
        tree_pages.set_title("Comic Book Pages")
        cell = gtk.CellRendererText()
        tree_pages.pack_start(cell, True)
        tree_pages.add_attribute(cell, "text", 0)

        pages_treestore = gtk.TreeStore(str)
        directories.append('Cover Page')
        directories.append('Root')

        for page in self._window.acbf_document.pages:
          page_path = page.find("image").get("href").replace("\\", "/")
          if '/' in page_path:
            if page_path[0:page_path.find('/')] not in directories:
              directories.append(page_path[0:page_path.find('/')])

        for directory in directories:
          it = pages_treestore.append(None, [directory])
          if directory == 'Cover Page':
            if '/' in page_path:
              pages_treestore.append(it, [self.selected_page[self.selected_page.find('/') + 1:]])
            else:
              pages_treestore.append(it, [self.selected_page])
          else:
            for page in self._window.acbf_document.pages:
              page_path = page.find("image").get("href").replace("\\", "/")
              if '/' in page_path and page_path[0:page_path.find('/')] == directory:
                pages_treestore.append(it, [page_path[page_path.find('/') + 1:]])
              elif '/' not in page_path and directory == 'Root':
                pages_treestore.append(it, [page_path])

        # remove empty directories (i.e. Root)
        for row in pages_treestore:
          if len(list(row.iterchildren())) == 0:
            pages_treestore.remove(row.iter)

        self.pages_tree.append_column(tree_pages)
        self.pages_tree.set_model(pages_treestore)
        tree_selection = self.pages_tree.get_selection()
        tree_selection.set_mode(gtk.SelectionMode.SINGLE)
        tree_selection.connect("changed", self.onPageSelectionChanged)

        self.sidebar.add_with_viewport(self.pages_tree)
        self.main_box.pack_start(self.sidebar, False, True, 5)

        # page image
        self.sw_image = gtk.ScrolledWindow()
        self.sw_image.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)

        self.drawing_area = gtk.DrawingArea()
        self.drawing_area.set_size_request(300 * self._window.ui_scale_factor, 500 * self._window.ui_scale_factor)
        self.drawing_area.show()
        self.drawing_area.connect("button_press_event", self.draw_brush)
        self.drawing_area.connect("scroll-event", self.scroll_window)
        self.drawing_area.connect("draw", self.expose_event)
        self.drawing_area.set_events(Gdk.EventMask.EXPOSURE_MASK
                                | Gdk.EventMask.LEAVE_NOTIFY_MASK
                                | Gdk.EventMask.BUTTON_PRESS_MASK
                                | Gdk.EventMask.POINTER_MOTION_MASK
                                | Gdk.EventMask.POINTER_MOTION_HINT_MASK)

        self.sw_image.add_with_viewport(self.drawing_area)
        self.main_box.pack_start(self.sw_image, True, True, 5)

        self.vbox.pack_start(self.main_box, True, True, 0)

        # general & frames & text-layers
        self.notebook = gtk.Notebook()
        self.notebook.set_border_width(3)
        self.notebook.connect("switch-page", self.tab_change)

        # general
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.ShadowType.ETCHED_IN)
        sw.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)

        self.general_box = gtk.VBox(False, 0)
        self.load_general()

        sw.add_with_viewport(self.general_box)
        self.notebook.insert_page(sw, gtk.Label('General'), -1)

        # frames
        self.fsw = gtk.ScrolledWindow()
        self.fsw.set_shadow_type(gtk.ShadowType.ETCHED_IN)
        self.fsw.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        self.fsw.set_size_request(550 * self._window.ui_scale_factor, 150 * self._window.ui_scale_factor)

        self.load_frames()

        self.fsw.add_with_viewport(self.frames_box)
        self.notebook.insert_page(self.fsw, gtk.Label('Frames'), -1)

        # text-layers
        self.tsw = gtk.ScrolledWindow()
        self.tsw.set_shadow_type(gtk.ShadowType.ETCHED_IN)
        self.tsw.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)

        self.load_texts()

        self.tsw.add_with_viewport(self.texts_box)
        self.notebook.insert_page(self.tsw, gtk.Label('Text-Layers'), -1)

        self.vbox.pack_start(self.notebook, False, False, 5)

        # action area
        hbox = gtk.HBox(True, 0)
        copy_layer_button = gtk.ToolButton()
        copy_layer_button.set_stock_id(gtk.STOCK_COPY)
        copy_layer_button.set_tooltip_text('Copy Text Layer')
        self.source_layer_frames = ''
        self.source_layer_frames_no = 0
        self.source_layer_texts = ''
        self.source_layer_texts_no = 0
        copy_layer_button.connect('clicked', self.copy_layer)
        hbox.pack_start(copy_layer_button, False, False, 0)
        
        paste_layer_button = gtk.ToolButton()
        paste_layer_button.set_stock_id(gtk.STOCK_PASTE)
        paste_layer_button.set_tooltip_text('Paste Text Layer')
        paste_layer_button.connect('clicked', self.paste_layer)
        hbox.pack_start(paste_layer_button, False, False, 0)
        self.get_action_area().pack_start(hbox, False, False, 0)

        self.straight_button = gtk.CheckButton("Draw straight lines.")
        self.get_action_area().pack_start(self.straight_button, False, False, 0)

        hbox = gtk.HBox(True, 0)
        self.zoom_dropdown = gtk.ComboBoxText()
        self.zoom_dropdown.append_text("10%")
        self.zoom_dropdown.append_text("25%")
        self.zoom_dropdown.append_text("50%")
        self.zoom_dropdown.append_text("75%")
        self.zoom_dropdown.append_text("100%")
        self.zoom_dropdown.append_text("150%")
        self.zoom_dropdown.append_text("200%")
        self.zoom_dropdown.set_active(4)
        self.zoom_dropdown.connect('changed', self.change_zoom)
        label = gtk.Label("Zoom: ")
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(self.zoom_dropdown, False, False, 0)
        self.get_action_area().pack_start(hbox, False, False, 0)

        hbox = gtk.HBox(True, 0)
        self.layer_dropdown = gtk.ComboBoxText()
        for a in self._window.acbf_document.languages:
          if a[1] == 'FALSE':
            self.layer_dropdown.append_text(a[0] + '#')
        for a in self._window.acbf_document.languages:
          if a[1] == 'TRUE':
            self.layer_dropdown.append_text(a[0])
        self.layer_dropdown.set_active(0)
        self.layer_dropdown.connect('changed', self.change_layer)
        label = gtk.Label("Layer: ")
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(self.layer_dropdown, False, False, 0)
        self.get_action_area().pack_start(hbox, False, False, 0)

        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect('clicked', self.close_dialog)
        self.get_action_area().pack_start(close_button, True, False, 0)

        self.get_action_area().set_layout(gtk.ButtonBoxStyle.EDGE)
        
        # show
        self.show_all()
        self.connect('response', self.close_dialog)
        self.connect('key_press_event', self.key_pressed)
        self.draw_page_image()

        #fg_color = Gdk.RGBA()
        #Gdk.RGBA.parse(fg_color, self._window.preferences.get_value("frames_color"))
        #self.frames_gc = self.drawing_area.get_window.new_gc(line_style=2)
        #self.frames_gc.set_rgb_fg_color(frames_color)
        #bg_color = Gdk.RGBA()
        #Gdk.RGBA.parse(bg_color, "#FFFFFF")
        #self.frames_gc.set_rgb_bg_color(bg_color)
        #text_layers_color = Gdk.RGBA()
        #Gdk.RGBA.parse(text_layers_color, self._window.preferences.get_value("text_layers_color"))
        #self.text_layers_gc = self.drawing_area.window.new_gc()
        #self.text_layers_gc.set_rgb_fg_color(text_layers_color)

        self.run()

    def copy_layer(self, *args):
      number_of_frames = len(self._window.acbf_document.load_page_frames(self.get_current_page_number()))
      number_of_texts = 0
      selected_layer = self.layer_dropdown.get_active_text()
      if selected_layer[-1] != '#':
        number_of_texts = len(self._window.acbf_document.load_page_texts(self.get_current_page_number(), selected_layer)[0])

      if self.drawing_frames == False and self.drawing_texts == False:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Nothing to copy.\nSelect 'Frames' or 'Text-Layers' tab.")
      elif self.drawing_frames == True and number_of_frames == 0:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Nothing to copy.\nNo frames found on this page.")
      elif self.drawing_texts == True and number_of_texts == 0:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Nothing to copy.\nNo text-layers found on this page for layer: " + selected_layer)
      elif self.drawing_frames:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Frames layer copied: " + str(number_of_frames) + " objects.")
        self.source_layer_frames = self.selected_page
        self.source_layer_frames_no = self.get_current_page_number()
      elif self.drawing_texts:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Text-layer copied: " + str(number_of_texts) + " objects.")
        self.source_layer_texts = self.selected_page
        self.source_layer_texts_no = self.get_current_page_number()
      else:
        return
      response = message.run()
      message.destroy()
      return

    def paste_layer(self, *args):
      if self.drawing_frames:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.YES_NO, message_format="Are you sure you want to paste frames from page '" + self.source_layer_frames +"'?\nCurrent layer will be removed.")
      else:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.YES_NO, message_format="Are you sure you want to paste text-layers from page '" + self.source_layer_texts +"'?\nCurrent layer will be removed.")
      response = message.run()
      message.destroy()
      if response != gtk.ResponseType.YES:
        return False

      if self.drawing_frames == False and self.drawing_texts == False:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Select 'Frames' or 'Text-Layers' tab to paste into.")
      elif self.drawing_frames and (self.source_layer_frames_no == 0 or self.source_layer_frames_no == self.get_current_page_number()):
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Nothing to paste. Copy frames from some other page first.")
      elif self.drawing_texts and (self.source_layer_texts_no == 0 or self.source_layer_texts_no == self.get_current_page_number()):
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Nothing to paste. Copy text-layer from some other page first.")
      elif self.drawing_frames:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Frames pasted from page " + self.source_layer_frames)
        self.set_modified()

        for page in self._window.acbf_document.pages:
          if page.find("image").get("href").replace("\\", "/") == self.selected_page:
            # delete all frames
            for frame in page.findall("frame"):
              page.remove(frame)

            # copy frames from source page
            for source_page in self._window.acbf_document.pages:
              if source_page.find("image").get("href").replace("\\", "/") == self.source_layer_frames:
                for source_frame in source_page.findall("frame"):
                  page.append(deepcopy(source_frame))
        
        self.load_frames()
        self.draw_page_image()

      elif self.drawing_texts:
        selected_layer = self.layer_dropdown.get_active_text()
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Text-layer pasted from page " + self.source_layer_texts)
        self.set_modified()
        layer_found = False

        for page in self._window.acbf_document.pages:
          if page.find("image").get("href").replace("\\", "/") == self.selected_page:
            for text_layer in page.findall("text-layer"):
              if text_layer.get("lang") == selected_layer:
                # delete text-areas
                layer_found = True
                for text_area in text_layer.findall("text-area"):
                  text_layer.remove(text_area)

                # copy text-areas from source page
                for source_page in self._window.acbf_document.pages:
                  if source_page.find("image").get("href").replace("\\", "/") == self.source_layer_texts:
                    for source_text_layer in source_page.findall("text-layer"):
                      if source_text_layer.get("lang") == selected_layer:
                        for source_text_area in source_text_layer.findall("text-area"):
                          text_layer.append(deepcopy(source_text_area))

            if not layer_found and selected_layer[-1] != '#':
              text_layer = xml.SubElement(page, "text-layer", lang=selected_layer)
              for source_page in self._window.acbf_document.pages:
                if source_page.find("image").get("href").replace("\\", "/") == self.source_layer_texts:
                  for source_text_layer in source_page.findall("text-layer"):
                    if source_text_layer.get("lang") == selected_layer:
                      for source_text_area in source_text_layer.findall("text-area"):
                        text_layer.append(deepcopy(source_text_area))

        self.load_texts()
        self.draw_page_image()        

      response = message.run()
      message.destroy()
      return
      
    def key_pressed(self, widget, event):
      """print(dir(Gdk.KEY))"""
      # ALT + key
      if event.state == Gdk.ModifierType.MOD1_MASK:
        None
      # CTRL + key
      if event.state == Gdk.ModifierType.CONTROL_MASK:
        if event.keyval in (Gdk.KEY_C, Gdk.KEY_c):
          self.copy_layer()
        elif event.keyval in (Gdk.KEY_V, Gdk.KEY_v):
          self.paste_layer()
      else:
      # the rest
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
          self.enclose_rectangle()
        elif event.keyval == Gdk.KEY_Escape:
          self.cancel_rectangle()
          self.detecting_bubble = False
          self.get_window().set_cursor(None)
        elif event.keyval == Gdk.KEY_BackSpace:
          if len(self.points) == 1:
            self.cancel_rectangle()
            self.detecting_bubble = False
            self.get_window().set_cursor(None)
          elif len(self.points) > 1:
            del self.points[-1]
            self.draw_page_image()
        elif event.keyval == Gdk.KEY_F1:
          self.show_help()
        elif event.keyval == Gdk.KEY_Delete:
          self.delete_page()
        elif event.keyval in (Gdk.KEY_R, Gdk.KEY_r) and self.drawing_texts:
          self.points = []
          self.drawing_rounded_rectangle = True
          cross_cursor = Gdk.Cursor(Gdk.CursorType.CROSS)
          self.get_window().set_cursor(cross_cursor)
        elif event.keyval in (Gdk.KEY_F8, Gdk.KEY_F, Gdk.KEY_f):
          self.frames_detection()
        elif event.keyval in (Gdk.KEY_F7, Gdk.KEY_T, Gdk.KEY_t):
          self.text_bubble_detection_cursor()
        elif event.keyval == Gdk.KEY_F5:
          self.draw_page_image()
        elif event.keyval in (Gdk.KEY_h, Gdk.KEY_H, Gdk.KEY_F11):
          if self.notebook.get_property("visible"):
            self.notebook.hide()
            self.sidebar.hide()
          else:
            self.notebook.show()
            self.sidebar.show()
        elif event.keyval == Gdk.KEY_Right:
          (path, focus_column) = self.pages_tree.get_cursor()
          if len(path) == 1:
            self.pages_tree.expand_row(path, False)
        elif event.keyval == Gdk.KEY_Left:
          (path, focus_column) = self.pages_tree.get_cursor()
          if len(path) == 1:
            self.pages_tree.collapse_row(path)
        elif event.keyval == Gdk.KEY_Down:
          (path, focus_column) = self.pages_tree.get_cursor()
          if len(path) == 1 and self.pages_tree.row_expanded(path):
            self.pages_tree.set_cursor((path[0], 0), focus_column, False)
          elif len(path) == 1:
            self.pages_tree.set_cursor((path[0] + 1, ), focus_column, False)
          else:
            self.pages_tree.set_cursor((path[0], path[1] + 1), focus_column, False)

          (new_path, focus_column) = self.pages_tree.get_cursor()
          if new_path == None:
            self.pages_tree.set_cursor((path[0] + 1, ), focus_column, False)

          (final_path, focus_column) = self.pages_tree.get_cursor()
          if final_path == None:
            self.pages_tree.set_cursor(path, focus_column, False)
        elif event.keyval == Gdk.KEY_Up:
          (path, focus_column) = self.pages_tree.get_cursor()
          if len(path) == 1 and path[0] == 0:
            return True
          elif len(path) == 1:
            self.pages_tree.set_cursor((path[0] - 1, ), focus_column, False)
          elif path[1] > 0:
            self.pages_tree.set_cursor((path[0], path[1] - 1), focus_column, False)
          else:
            self.pages_tree.set_cursor((path[0], ), focus_column, False)

          (final_path, focus_column) = self.pages_tree.get_cursor()
          if final_path == None:
            self.pages_tree.set_cursor(path, focus_column, False)
            
      return True

    def set_cursor_loading(self, *args):
      loading_cursor = Gdk.Cursor(Gdk.CursorType.WATCH)
      try:
        self.get_window().set_cursor(loading_cursor)
      except:
        None
      while gtk.events_pending():
        gtk.main_iteration()

    def show_help(self, *args):
      dialog = gtk.Dialog('Help', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT, (gtk.STOCK_CLOSE, gtk.ResponseType.CLOSE))
      dialog.height = 300
      dialog.set_resizable(False)
      dialog.set_border_width(8)

      #Shortcuts
      hbox = gtk.HBox(False, 10)
      label = gtk.Label()
      label.set_markup('<b>Shortcuts</b>')
      hbox.pack_start(label, False, False, 0)
      dialog.vbox.pack_start(hbox, False, False, 10)

      # left side
      main_hbox = gtk.HBox(False, 3)
      left_vbox = gtk.VBox(False, 3)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_HELP)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('This help window (F1)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_COPY)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Copy Frames/Text-Layer (CTRL + C)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)
      
      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_OK)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Enclose Rectangle (ENTER, right click)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)
      
      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_GO_FORWARD)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Draw straight line by holding down Control key')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_REFRESH)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Refresh image (F5)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_FIND)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Detect Frames (F8 or "F" key)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)
      
      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_FULLSCREEN)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Hide bottom and side bars (F11 or "H" key)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)

      main_hbox.pack_start(left_vbox, False, False, 10)

      # right side
      right_vbox = gtk.VBox(False, 3)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_REMOVE)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Delete current page (DEL)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_PASTE)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Paste Frames/Text-Layer (CTRL + V)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_STOP)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Cancel Drawing Rectangle (ESC)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_UNDO)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Remove Last Point (BackSpace)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)
      
      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_SELECT_FONT)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Detect Text Bubble at cursor (F7 or "T" key)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_ORIENTATION_LANDSCAPE)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Draw Text Layer Rectangle with rounded corners ("R" key)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      main_hbox.pack_start(right_vbox, False, False, 10)

      dialog.vbox.pack_start(main_hbox, False, False, 0)
      dialog.get_action_area().get_children()[0].grab_focus()

      # show it
      dialog.show_all()
      dialog.run()
      if dialog != None:
        dialog.destroy()

      return

    def delete_page(self, *args):
      if self.get_current_page_number() <= 1:
        return False

      message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.YES_NO, message_format="Are you sure you want to remove this page?")
      response = message.run()
      message.destroy()

      if response != gtk.ResponseType.YES:
        return False

      for page in self._window.acbf_document.tree.findall("body/page"):
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          self._window.acbf_document.tree.find("body").remove(page)
          in_path = os.path.join(self._window.tempdir, page.find("image").get("href").replace("\\", "/"))
          if os.path.isfile(in_path):
            os.remove(in_path)

      for image in self._window.acbf_document.tree.findall("data/binary"):
        if image.get("id") == self.selected_page[1:]:
          self._window.acbf_document.tree.find("data").remove(image)

      self._window.acbf_document.pages = self._window.acbf_document.tree.findall("body/" + "page")

      self.pages_tree.get_selection().get_selected()[0].remove(self.pages_tree.get_selection().get_selected()[1])
      self.pages_tree.set_cursor((0,0))
      self.pages_tree.grab_focus()
      self.draw_page_image()

      self.set_modified()

    def set_modified(self):
      self._window.is_modified = True
      self.set_title('Frames/Text Layers Editor*')

    def change_zoom(self, *args):
      self.scale_factor = float(self.zoom_dropdown.get_active_text()[0:-1])/100
      self.draw_page_image()

    def change_layer(self, *args):
      self.draw_page_image()
      return

    def tab_change(self, notebook, page, page_num, *args):
      if page_num == 1:
        self.drawing_frames = True
        self.drawing_texts = False
        self.load_frames()
      elif page_num == 2:
        self.drawing_frames = False
        self.drawing_texts = True
        self.load_texts()
      else:
        self.drawing_frames = False
        self.drawing_texts = False

    def load_general(self, *args):
      # main bg_color
      hbox = gtk.HBox(False, 0)

      label = gtk.Label()
      label.set_markup('Main Background Color: ')
      hbox.pack_start(label, False, False, 0)

      color = Gdk.RGBA()
      Gdk.RGBA.parse(color, self._window.acbf_document.bg_color)
      color_button = gtk.ColorButton()
      color_button.set_rgba(color)
      #color_button.modify_fg(gtk.StateType.NORMAL, color)
      color_button.set_title('Select Color')
      color_button.connect("clicked", self.set_body_bgcolor)
      hbox.pack_start(color_button, False, False, 0)
      self.general_box.pack_start(hbox, False, False, 0)

      # page bg_color
      hbox = gtk.HBox(False, 0)

      label = gtk.Label()
      label.set_markup('Page Background Color: ')
      hbox.pack_start(label, False, False, 0)

      color = Gdk.RGBA()
      try:
        Gdk.RGBA.parse(color, self.selected_page_bgcolor)
      except:
        Gdk.RGBA.parse(color, self._window.acbf_document.bg_color)
      self.page_color_button = gtk.ColorButton()
      self.page_color_button.set_rgba(color)
      self.page_color_button.set_title('Select Color')
      self.page_color_button.connect("clicked", self.set_page_bgcolor)
      hbox.pack_start(self.page_color_button, False, False, 0)
      self.general_box.pack_start(hbox, False, False, 0)

      # transition
      hbox = gtk.HBox(False, 0)

      label = gtk.Label()
      label.set_markup('Page Transition: ')
      hbox.pack_start(label, False, False, 0)

      self.transition_dropdown = gtk.ComboBoxText()
      for key in self.transition_dropdown_dict:
        self.transition_dropdown.append_text(self.transition_dropdown_dict[key])
        if self.transition_dropdown_dict[key].replace(' ', '_').upper() == self._window.acbf_document.get_page_transition(self.get_current_page_number()).upper():
          self.transition_dropdown.set_active(key)

      self.transition_dropdown.connect("changed", self.update_page_transition)
      self.transition_dropdown_is_active = True
      hbox.pack_start(self.transition_dropdown, False, False, 0)

      self.general_box.pack_start(hbox, False, False, 0)

    def update_page_transition(self, widget):
      if not self.transition_dropdown_is_active or self.transition_dropdown.get_active() == 0:
        return
      for page in self._window.acbf_document.pages:
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          page.attrib["transition"] = self.transition_dropdown.get_active_text().lower().replace(' ', '_')
      self.set_modified()

    def set_body_bgcolor(self, widget):
      #override to ColorSelectionDialog (to make it non-modal in order to pick color from other window with eyedropper)
      for i in self.list_toplevels():
        if i.get_name() == 'GtkColorChooserDialog':
          i.destroy()
          my_dialog = ColorDialog(self, widget.get_color(), False, 'false')
          response = my_dialog.run()
          if response == gtk.ResponseType.OK:
            widget.set_rgba(my_dialog.get_rgba())
            self._window.acbf_document.tree.find("body").attrib["bgcolor"] = self.get_hex_color(widget)
            self._window.acbf_document.bg_color = self.get_hex_color(widget)
            color = Gdk.RGBA()
            try:
              Gdk.RGBA.parse(color, self.selected_page_bgcolor)
            except:
              Gdk.RGBA.parse(color, self._window.acbf_document.bg_color)
            color_button = gtk.ColorButton()
            color_button.set_rgba(color)
            self.set_modified()
          my_dialog.destroy()
      return True

    def get_hex_color(self, widget):
      color_string = widget.get_color().to_string()
      if len(color_string) == 13:
        color = '#' + color_string[1:3] + color_string[5:7] + color_string[9:11]
        return color
      else:
        return color_string

    def set_page_bgcolor(self, widget):
      #override to ColorSelectionDialog (to make it non-moda in order to pick color from other window with eyedropper)
      for i in gtk.window_list_toplevels():
        if i.get_name() == 'GtkColorChooserDialog':
          i.destroy()
          my_dialog = ColorDialog(self, widget.get_color(), False, 'false')
          response = my_dialog.run()
          if response == gtk.ResponseType.OK:
            widget.set_rgba(my_dialog.get_rgba())
            for page in self._window.acbf_document.pages:
              if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                page.attrib["bgcolor"] = self.get_hex_color(widget)
            self.selected_page_bgcolor = self.get_hex_color(widget)
            self.set_modified()
          my_dialog.destroy()
      return True

    def load_frames(self, *args):
        for i in self.frames_box.get_children():
          i.destroy()
        for idx, frame in enumerate(self._window.acbf_document.load_page_frames(self.get_current_page_number())):
          if self.get_current_page_number() > 1:
            self.add_frames_hbox(None, frame[0], frame[1], idx + 1)

    def scale_polygon(self, polygon, *args):
      polygon_out = []
      for point in polygon:
        polygon_out.append((int(point[0] * self.scale_factor), int(point[1] * self.scale_factor)))
      return polygon_out

    def add_frames_hbox(self, widget, polygon, bg_color, frame_number):
      hbox = gtk.HBox(False, 0)

      # frame number
      label = gtk.Label()
      label.set_markup('<span foreground="blue"><b><big>' + str(frame_number).rjust(3) + ' </big></b></span>')
      hbox.pack_start(label, False, False, 0)

      # up button
      up_button = gtk.ToolButton(gtk.STOCK_GO_UP)
      if frame_number > 1:
        up_button.set_tooltip_text('Move Up')
        up_button.connect("clicked", self.move_frame_up, polygon)
      else:
        up_button.set_sensitive(False)
      hbox.pack_start(up_button, False, False, 0)
      
      # coordinates
      entry = gtk.Entry()
      entry.set_text(str(polygon))
      entry.type = 'polygon'
      entry.set_tooltip_text('Frames Polygon')
      entry.set_sensitive(False)
      hbox.pack_start(entry, True, True, 0)

      # bg color
      if bg_color == None and self.selected_page_bgcolor == None:
        bg_color = self._window.acbf_document.bg_color
      elif bg_color == None:
        bg_color = self.selected_page_bgcolor

      color = Gdk.RGBA()
      Gdk.RGBA.parse(color, bg_color)
      color_button = gtk.ColorButton()
      color_button.set_rgba(color)
      color_button.set_title('Frame Background Color')
      color_button.connect("clicked", self.set_frame_bgcolor, polygon)
      hbox.pack_start(color_button, False, False, 0)

      # remove button
      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_frame, hbox, polygon)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()
      entry.grab_focus()

      self.frames_box.pack_start(hbox, False, False, 0)
      self.frames_box.show_all()
      return

    def remove_frame(self, widget, hbox, polygon):
      message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.YES_NO, message_format="Are you sure you want to remove the frame?")
      response = message.run()
      message.destroy()

      if response != gtk.ResponseType.YES:
        return False

      for page in self._window.acbf_document.pages:
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          xml_frame = ''
          for point in polygon:
            xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
          for frame in page.findall("frame"):
            if frame.get("points") == xml_frame.strip():
              page.remove(frame)
      self.set_modified()
      self.remove_hbox(widget, hbox)
      self.load_frames()
      self.draw_page_image()

    def remove_hbox(self, widget, hbox):
      hbox.destroy()
      return

    def set_frame_bgcolor(self, widget, polygon):
      #override to ColorSelectionDialog (to make it non-modal in order to pick color from other window with eyedropper)
      for i in self.list_toplevels():
        if i.get_name() == 'GtkColorChooserDialog':
          i.destroy()
          my_dialog = ColorDialog(self, widget.get_color(), False, 'false')
          response = my_dialog.run()
          if response == gtk.ResponseType.OK:
            widget.set_rgba(my_dialog.get_rgba())
            for page in self._window.acbf_document.pages:
              if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                xml_frame = ''
                for point in polygon:
                  xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
                for frame in page.findall("frame"):
                  if frame.get("points") == xml_frame.strip():
                    frame.attrib["bgcolor"] = self.get_hex_color(widget)
            self.set_modified()
          my_dialog.destroy()
      return True

    def move_frame_up(self, widget, polygon):
      for page in self._window.acbf_document.pages:
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          xml_frame = ''
          for point in polygon:
            xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
          current_page = deepcopy(page)
          for idx, frame in enumerate(page.findall("frame")):
            if frame.get("points") == xml_frame.strip():
              current_index = idx
              current_frame = deepcopy(frame)
              # remove frame from copy
              for fr in current_page.findall("frame"):
                if fr.get("points") == xml_frame.strip():
                  fr.getparent().remove(fr)
            frame.getparent().remove(frame)

          # add frame into copy at proper place
          for idx, frame in enumerate(current_page.findall("frame")):
            if idx == current_index - 1:
              page.append(current_frame)
            page.append(frame)
                      
      self.set_modified()
      self.load_frames()
      self.draw_page_image()

    def load_texts(self, *args):
      for i in self.texts_box.get_children():
        i.destroy()
      for lang in self._window.acbf_document.languages:
        if lang[1] != 'FALSE':
          for idx, text_areas in enumerate(self._window.acbf_document.load_page_texts(self.get_current_page_number(), lang[0])[0]):
            self.add_texts_hbox(None, text_areas[0], text_areas[1], text_areas[2], text_areas[4], text_areas[5], idx + 1, text_areas[6])  
          break

    def add_texts_hbox(self, widget, polygon, text, bg_color, area_type, inverted, area_number, is_transparent):
      hbox = gtk.HBox(False, 0)

      # text-area number
      label = gtk.Label()
      label.set_markup('<span foreground="red"><b><big>' + str(area_number).rjust(3) + ' </big></b></span>')
      hbox.pack_start(label, False, False, 0)

      # up button
      up_button = gtk.ToolButton(gtk.STOCK_GO_UP)
      if area_number > 1:
        up_button.set_tooltip_text('Move Up')
        up_button.connect("clicked", self.move_text_up, polygon)
      else:
        up_button.set_sensitive(False)
      hbox.pack_start(up_button, False, False, 0)

      # text
      entry = gtk.Entry()
      entry.set_text(unescape(text).replace('<BR>', ''))
      entry.type = 'polygon'
      entry.set_sensitive(False)
      hbox.pack_start(entry, True, True, 0)

      # Edit text
      button = gtk.Button(stock=gtk.STOCK_ITALIC)
      button.get_children()[0].get_children()[0].get_children()[1].set_text(' ...')
      button.connect("clicked", self.edit_texts, polygon, bg_color, area_number)
      button.type = 'texts_edit'
      button.set_tooltip_text('Edit Text Areas')
      hbox.pack_start(button, False, False, 0)

      # bg color
      if bg_color == None and self.selected_page_bgcolor == None:
        bg_color = self._window.acbf_document.bg_color
      elif bg_color == None:
        bg_color = self.selected_page_bgcolor

      color = Gdk.RGBA()
      Gdk.RGBA.parse(color, bg_color)
      color_button = gtk.ColorButton()
      color_button.set_rgba(color)
      if is_transparent:
        color_button.set_use_alpha(True)
        color_button.set_alpha(0)
      color_button.set_tooltip_text('Text Area Background Color')
      color_button.connect("clicked", self.set_text_bgcolor, polygon)
      hbox.pack_start(color_button, False, False, 0)

      # text layer type
      if area_type == 'code':
        area_type = 'c'
      elif area_type == 'speech':
        area_type = ' '
      else:
        area_type = area_type[0].upper()
      if inverted:
        area_type = area_type + '~'
      else:
        area_type = area_type + ' '
      label = gtk.Label()
      label.set_markup('<tt> <b>' + area_type + '</b> </tt>')
      hbox.pack_start(label, False, False, 0)

      # remove button
      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_text, hbox, polygon)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()
      entry.grab_focus()

      self.texts_box.pack_start(hbox, False, False, 0)
      self.texts_box.show_all()
      return

    def set_text_bgcolor(self, widget, polygon):
      #override to ColorSelectionDialog (to make it non-modal in order to pick color from other window with eyedropper)
      for i in self.list_toplevels():
        if i.get_name() == 'GtkColorChooserDialog':
          i.destroy()

          # get transparency value
          is_transparent = 'false'
          for page in self._window.acbf_document.pages:
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
              xml_frame = ''
              for point in polygon:
                xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
              for text_layer in page.findall("text-layer"):
                for text_area in text_layer.findall("text-area"):
                  if text_area.get("points") == xml_frame.strip():
                    is_transparent = text_area.get("transparent")

          # open dialog
          my_dialog = ColorDialog(self, widget.get_color(), True, is_transparent)
          response = my_dialog.run()
          if response == gtk.ResponseType.OK:
            if my_dialog.transparency_button.get_active():
              widget.set_use_alpha(True)
              widget.set_alpha(0)
            else:
              widget.set_use_alpha(False)
              widget.set_rgba(my_dialog.get_rgba())
            for page in self._window.acbf_document.pages:
              if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                xml_frame = ''
                for point in polygon:
                  xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
                for text_layer in page.findall("text-layer"):
                  for text_area in text_layer.findall("text-area"):
                    if text_area.get("points") == xml_frame.strip():
                      text_area.attrib["bgcolor"] = self.get_hex_color(widget)
                      if my_dialog.transparency_button.get_active():
                        text_area.attrib["transparent"] = "true"
                      else:
                        text_area.attrib.pop("transparent", None)
            self.set_modified()
          my_dialog.destroy()
      return True

    def move_text_up(self, widget, polygon):
      for page in self._window.acbf_document.pages:
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          xml_frame = ''
          for point in polygon:
            xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
          for text_layer in page.findall("text-layer"):
            current_text_layer = deepcopy(text_layer)
            for idx, text_area in enumerate(text_layer.findall("text-area")):
              if text_area.get("points") == xml_frame.strip():
                current_index = idx
                current_text_area = deepcopy(text_area)
                # remove area from copy
                for area in current_text_layer.findall("text-area"):
                  if area.get("points") == xml_frame.strip():
                    area.getparent().remove(area)
              text_area.getparent().remove(text_area)

            # add area into copy at proper place
            for idx, area in enumerate(current_text_layer.findall("text-area")):
              if idx == current_index - 1:
                text_layer.append(current_text_area)
              text_layer.append(area)
            
      self.set_modified()
      self.load_texts()
      self.draw_page_image()
      
    def remove_text(self, widget, hbox, polygon):
      message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.YES_NO, message_format="Are you sure you want to remove the text area?")
      response = message.run()
      message.destroy()

      if response != gtk.ResponseType.YES:
        return False

      for page in self._window.acbf_document.pages:
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          xml_frame = ''
          for point in polygon:
            xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
          for text_layer in page.findall("text-layer"):
            for text_area in text_layer.findall("text-area"):
              if text_area.get("points") == xml_frame.strip():
                text_layer.remove(text_area)
      self.set_modified()
      self.remove_hbox(widget, hbox)
      self.load_texts()
      self.draw_page_image()

    def edit_texts(self, widget, polygon, bg_color, area_number, *args):
      dialog = TextBoxDialog(self, area_number)
      dialog.set_size_request(700 * self._window.ui_scale_factor, 400 * self._window.ui_scale_factor)

      # Text Layers switch
      self.edit_text_languages = []
      for lang in self._window.acbf_document.languages:
        if lang[1] == 'TRUE':
          self.edit_text_languages.append(lang[0])
        
      hbox = gtk.HBox(False, 0)
      label = gtk.Label()
      label.set_markup('<b>Language</b>: ')
      hbox.pack_start(label, False, False, 0)

      self.lang_dropdown = gtk.ComboBoxText()
      for idx, item in enumerate(self.edit_text_languages):
        self.lang_dropdown.append_text(item)
      self.lang_dropdown.set_active(0)
      self.lang_dropdown.set_tooltip_text('Text Layer Language')
      self.old_lang_dropdown = self.lang_dropdown.get_active_text()

      self.lang_dropdown.connect("changed", self.update_edit_text_box, polygon, bg_color)

      hbox.pack_start(self.lang_dropdown, False, False, 0)

      # text-rotation
      label = gtk.Label()
      label.set_markup('  <b>Text-Rotation</b>: ')
      hbox.pack_start(label, False, False, 0)

      self.text_rotation = gtk.Adjustment(0.0, 0.0, 360, 1.0, 1.0, 1.0)
      scale = gtk.Scale(orientation = gtk.Orientation.HORIZONTAL, adjustment=self.text_rotation)
      #scale.set_update_policy(gtk.UPDATE_CONTINUOUS)
      scale.set_digits(0)
      scale.set_hexpand(True)
      scale.set_draw_value(True)
      hbox.pack_start(scale, True, True, 0)

      # inverted
      self.inverted_button = gtk.CheckButton(label="Inverted")
      hbox.pack_end(self.inverted_button, False, False, 10)

      # Text Area type
      self.type_dropdown = gtk.ComboBoxText()
      text_area_types = ['Speech', 'Commentary', 'Formal', 'Letter', 'Code', 'Heading', 'Audio', 'Thought', 'Sign']
      for ta_type in text_area_types:
        self.type_dropdown.append_text(ta_type)
      self.type_dropdown.set_active(0)
      self.type_dropdown.set_tooltip_text('Text Area Type')
      hbox.pack_end(self.type_dropdown, False, True, 0)

      label = gtk.Label()
      label.set_markup('  <b>Type</b>: ')
      hbox.pack_end(label, False, False, 0)

      hbox.show_all()
      dialog.vbox.pack_start(hbox, False, False, 0)

      # main box
      main_hbox = gtk.HBox(False, 0)
      self.text_box = gtk.TextView()
      self.text_box.set_wrap_mode(gtk.WrapMode.WORD)

      for text_areas in self._window.acbf_document.load_page_texts(self.get_current_page_number(), self.edit_text_languages[0])[0]:
        if str(polygon) == str(text_areas[0]):
          self.text_rotation.set_value(text_areas[3])
          self.text_box.get_buffer().set_text(unescape(text_areas[1].replace('<commentary>', '').replace('</commentary>', '').replace('<commentary/>', '').replace('<inverted>', '').replace('</inverted>', '').replace('<BR>', '\n')))
          for idx, ta_type in enumerate(text_area_types):
            if ta_type.lower() == text_areas[4]:
              self.type_dropdown.set_active(idx)
          if '<commentary>' in text_areas[1]:
            self.type_dropdown.set_active(1)
          if '<inverted>' in text_areas[1] or text_areas[5]:
            self.inverted_button.set_active(True)
      scrolled = gtk.ScrolledWindow()
      scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
      scrolled.add_with_viewport(self.text_box)
      main_hbox.pack_start(scrolled, True, True, 0)

      self.inverted_button.connect("toggled", self.change_text_box_type, polygon)
      self.type_dropdown.connect("changed", self.change_text_box_type, polygon)
      dialog.vbox.pack_start(main_hbox, True, True, 0)

      # show it
      dialog.show_all()
      response = dialog.run()

      if response == gtk.ResponseType.OK:
        self.save_edit_text_box(polygon, self.old_lang_dropdown)
        self.set_modified()
        self.load_texts()

      dialog.destroy()
      return

    def change_text_box_type(self, widget, polygon):
      self.set_modified()
      current_active = self.lang_dropdown.get_active()
      for idx, item in enumerate(self.edit_text_languages):
        self.lang_dropdown.set_active(idx)
      self.lang_dropdown.set_active(current_active)

    def save_edit_text_box(self, polygon, old_lang):
      for page in self._window.acbf_document.pages:
        if page.find("image").get("href").replace("\\", "/") == self.selected_page:
          for text_layer in page.findall("text-layer"):
            for text_area in text_layer:
              if str(polygon).replace('[', '').replace(')]', '').replace('(', '').replace('),', '').replace(', ', ',') == str(text_area.get("points")):
                if self.text_rotation.get_value() > 0:
                  text_area.attrib['text-rotation'] = str(int(self.text_rotation.get_value()))
                else:
                  text_area.attrib.pop('text-rotation', None)
                if self.type_dropdown.get_active() != 0:
                  text_area.attrib['type'] = self.type_dropdown.get_active_text().lower()
                else:
                  text_area.attrib.pop('type', None)
                if self.inverted_button.get_active():
                  text_area.attrib['inverted'] = 'true'
                else:
                  text_area.attrib.pop('inverted', None)
            if text_layer.get("lang") == old_lang:
              for text_area in text_layer:
                if str(polygon).replace('[', '').replace(')]', '').replace('(', '').replace('),', '').replace(', ', ',') == str(text_area.get("points")):
                  for p in text_area.findall("p"):
                    text_area.remove(p)

                  text_box = self.text_box.get_buffer().get_text(self.text_box.get_buffer().get_bounds()[0], self.text_box.get_buffer().get_bounds()[1], True)

                  for text in text_box.split('\n'):
                    element = xml.SubElement(text_area, "p")

                    tag_tail = None
                    for word in text.strip(' ').split('<'):
                      if re.sub("[^\/]*>.*", '', word) == '':
                        tag_name = re.sub(">.*", '', word)
                        tag_text = re.sub("[^>]*>", '', word)
                      elif '>' in word:
                        tag_tail = re.sub("/[^>]*>", '', word)
                      else:
                        element.text = str(word)

                      if tag_tail != None:
                        if ' ' in tag_name:
                          tag_attr = tag_name.split(' ')[1].split('=')[0]
                          tag_value = tag_name.split(' ')[1].split('=')[1].strip('"')
                          tag_name = tag_name.split(' ')[0]
                          sub_element = xml.SubElement(element, tag_name)
                          sub_element.attrib[tag_attr] = tag_value
                          sub_element.text = str(tag_text)
                          sub_element.tail = str(tag_tail)
                        else:
                          sub_element = xml.SubElement(element, tag_name)
                          sub_element.text = str(tag_text)
                          sub_element.tail = str(tag_tail)

                        tag_tail = None

    def update_edit_text_box(self, widget, polygon, bg_color):
      # save old
      self.save_edit_text_box(polygon, self.old_lang_dropdown)

      # activate new
      text_area_found = False
      text_layer_found = False
      #check if current language has this text-area
      for text_areas in self._window.acbf_document.load_page_texts(self.get_current_page_number(), self.lang_dropdown.get_active_text())[0]:
        if str(polygon) == str(text_areas[0]):
          text_area_found = True
          self.text_box.get_buffer().set_text(unescape(text_areas[1].replace('<commentary>', '').replace('</commentary>', '').replace('<commentary/>', '').replace('<inverted>', '').replace('</inverted>', '').replace('<BR>', '\n')))
      if not text_area_found:
        self.text_box.get_buffer().set_text('...')
        xml_frame = ''
        for point in polygon:
          xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
        #check if current language has this text-layer
        for page in self._window.acbf_document.pages:
          if page.find("image").get("href").replace("\\", "/") == self.selected_page:
            for text_layer in page.findall("text-layer"):
              if text_layer.get("lang") == self.lang_dropdown.get_active_text():
                area = xml.SubElement(text_layer, "text-area", points=xml_frame.strip(), bgcolor=bg_color)
                text_layer_found = True
            if not text_layer_found:
              layer = xml.SubElement(page, "text-layer", lang=self.lang_dropdown.get_active_text())
              area = xml.SubElement(layer, "text-area", points=xml_frame.strip(), bgcolor=bg_color)
            par = xml.SubElement(area, "p")
            par.text = '...'

      self.old_lang_dropdown = self.lang_dropdown.get_active_text()

    def close_dialog(self, *args):
      self.destroy()

    def expose_event(self, widget, event):
        #print('expose_event')
        
        # draw page image
        Gdk.cairo_set_source_pixbuf(event, self.drawing_area_pixbuf, 0, 0)
        event.paint()
        origin = (0, 0)

        # set frame color
        frames_color = self._window.preferences.get_value("frames_color")
        if len(frames_color) == 13: # workaround for PIL, which des not recognize 13 characters long colors
          frames_color = '#' + frames_color[1:3] + frames_color[5:7] + frames_color[9:11]
        frames_color = ImageColor.getcolor(frames_color, "RGB")
        
        # set text-layer color
        text_layers_color = self._window.preferences.get_value("text_layers_color")
        if len(text_layers_color) == 13: # workaround for PIL, which des not recognize 13 characters long colors
          text_layers_color = '#' + text_layers_color[1:3] + text_layers_color[5:7] + text_layers_color[9:11]
        text_layers_color = ImageColor.getcolor(text_layers_color, "RGB")
        
        # draw frames
        event.set_source_rgb(float(frames_color[0]/256), float(frames_color[1]/255), float(frames_color[2]/255))
        for idx, frame in enumerate(self._window.acbf_document.load_page_frames(self.get_current_page_number())):
          if self.get_current_page_number() > 1:
            event.set_line_width(3)
            for point_idx, point in enumerate(self.scale_polygon(frame[0])):
              if point_idx == 0:
                event.move_to(point[0], point[1])
                origin = point
              else:
                event.line_to(point[0], point[1])
            event.line_to(origin[0], origin[1])
            event.stroke()
            
            anchor = self.left_anochor_for_polygon(self.scale_polygon(frame[0]))
            if anchor[0] < 10:
              x_move = 0
            else:
              x_move = -10
            if anchor[1] < 10:
              y_move = 0
            else:
              y_move = -10
            
            #frame number background
            rectangle = (int(anchor[0]) + x_move - 6, int(anchor[1]) + y_move - 30, 38, 38)
            event.set_source_rgb(1,1,1)
            event.rectangle(rectangle[0], rectangle[1], rectangle[2], rectangle[3])
            event.fill()
            
            #frame number
            event.set_source_rgb(float(frames_color[0]/256), float(frames_color[1]/255), float(frames_color[2]/255))
            event.select_font_face("sans", cairo.FONT_WEIGHT_BOLD)
            event.set_font_size(32)
            event.move_to(int(anchor[0]) + x_move, int(anchor[1]) + y_move)
            event.show_text(str(idx+1))
            
        # draw text-layers
        event.set_source_rgb(float(text_layers_color[0]/256), float(text_layers_color[1]/255), float(text_layers_color[2]/255))
        for lang in self._window.acbf_document.languages:
          if lang[1] != 'FALSE':
            for idx, text_areas in enumerate(self._window.acbf_document.load_page_texts(self.get_current_page_number(), lang[0])[0]):
              event.set_line_width(3)
              for point_idx, point in enumerate(self.scale_polygon(text_areas[0])):
                if point_idx == 0:
                  event.move_to(point[0], point[1])
                  origin = point
                else:
                  event.line_to(point[0], point[1])
              event.line_to(origin[0], origin[1])
              event.stroke()
            
              min_x = min(text_areas[0],key=lambda item:item[0])[0]
              min_y = min(text_areas[0],key=lambda item:item[1])[1]
            
              #text-layer number background
              rectangle = (int(min_x * self.scale_factor) - 5, int(min_y * self.scale_factor) - 25, 30, 30)
              event.set_source_rgb(1,1,1)
              event.rectangle(rectangle[0], rectangle[1], rectangle[2], rectangle[3])
              event.fill()
            
              #text-layer number
              event.set_source_rgb(float(text_layers_color[0]/256), float(text_layers_color[1]/255), float(text_layers_color[2]/255))
              event.select_font_face("sans", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
              event.set_font_size(28)
              event.move_to(int(min_x * self.scale_factor), int(min_y * self.scale_factor))
              event.show_text(str(idx+1))
        
        # draw current point
        for point in self.points:
          rectangle = ((point[0]-2)* self.scale_factor, (point[1]-2)* self.scale_factor, 6, 6)
          event.set_source_rgb(0,0,0)
          event.rectangle(rectangle[0], rectangle[1], rectangle[2], rectangle[3])
          event.fill()
          rectangle = ((point[0])* self.scale_factor, (point[1])* self.scale_factor, 2, 2)
          event.set_source_rgb(1,1,1)
          event.rectangle(rectangle[0], rectangle[1], rectangle[2], rectangle[3])
          event.fill()
        return False

    def get_current_page_number(self, *args):
        for idx, page in enumerate(self._window.acbf_document.pages):
          if page.find("image").get("href").replace("\\", "/") == self.selected_page:
            ret_idx = idx + 2
            break
        else:
            ret_idx = 1
        return ret_idx

    def draw_drawable(self):
        self.drawing_area.queue_draw()

    def draw_page_image(self, *args):
        self.set_cursor_loading()
        x = self.drawing_area.get_allocation().x
        y = self.drawing_area.get_allocation().y
        width = self.drawing_area.get_allocation().width
        height = self.drawing_area.get_allocation().height

        if self.selected_page[:4] == 'Root':
          self.selected_page = self.selected_page[5:].replace("\\", "/")

        current_page_image = os.path.join(self._window.tempdir, self.selected_page)
        if not os.path.exists(current_page_image):
          self.get_window().set_cursor(None)	
          return

        if self.layer_dropdown.get_active_text()[-1] != '#':
          for idx, lang in enumerate(self._window.acbf_document.languages):
            if lang[0] == self.layer_dropdown.get_active_text():
              xx = text_layer.TextLayer(current_page_image, self._window.tempdir, self.get_current_page_number(), self._window.acbf_document, idx,
                                      self._window.acbf_document.font_styles['normal'],
                                      self._window.acbf_document.font_styles['strong'], self._window.acbf_document.font_styles['emphasis'],
                                      self._window.acbf_document.font_styles['code'], self._window.acbf_document.font_styles['commentary'],
                                      self._window.acbf_document.font_styles['sign'], self._window.acbf_document.font_styles['formal'],
                                      self._window.acbf_document.font_styles['heading'], self._window.acbf_document.font_styles['letter'],
                                      self._window.acbf_document.font_styles['audio'], self._window.acbf_document.font_styles['thought'])
              i = xx.PILBackgroundImage
              current_page_image = xx.PILBackgroundImageFile
        else:
          i, bg_color = self._window.acbf_document.load_page_image(self.get_current_page_number())

        w, h = i.size
        self.drawing_area.set_size_request(w, h)
        
        self.drawing_area_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(current_page_image, int(i.size[0] * self.scale_factor), int(i.size[1] * self.scale_factor), True)
        self.drawing_area.set_size_request(int(i.size[0] * self.scale_factor), int(i.size[1] * self.scale_factor))
        
        self.load_frames()
        self.load_texts()
        self.draw_drawable()
        self.get_window().set_cursor(None)		

    def scroll_window(self, button, event, *args):
        if event.direction == Gdk.Event_scroll.SCROLL_DOWN and event.state & Gdk.ModifierType.SHIFT_MASK:
          current_value = self.sw_image.get_hadjustment().value
          step = self.sw_image.get_hadjustment().get_step_increment()
          maximum = self.sw_image.get_hadjustment().get_upper() - self.sw_image.get_hadjustment().get_page_size()
          if current_value + step > maximum:
            self.sw_image.get_hadjustment().set_value(maximum)
          else:
            self.sw_image.get_hadjustment().set_value(current_value + step)
          return True
        elif event.direction == Gdk.Event_scroll.SCROLL_UP and event.state & Gdk.ModifierType.SHIFT_MASK:
          current_value = self.sw_image.get_hadjustment().value
          step = self.sw_image.get_hadjustment().get_step_increment()
          if current_value - step < 0:
            self.sw_image.get_hadjustment().set_value(0)
          else:
            self.sw_image.get_hadjustment().set_value(current_value - step)
          return True
        return

    def draw_brush(self, widget, event, *args):
        if self.detecting_bubble:
          try:
            self.text_bubble_detection(event.x, event.y)
          except:
            message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Failed to detect text area.")
            response = message.run()
            message.destroy()
          self.detecting_bubble = False
          self.get_window().set_cursor(None)
          return

        if (not self.drawing_frames and not self.drawing_texts) or self.get_current_page_number() == 1 or event.button != 1:
          if event.button == 3:
            self.enclose_rectangle()
          return

        #draw vertical/horizontal line with CTRL key pressed
        if (event.state & Gdk.ModifierType.CONTROL_MASK or self.straight_button.get_active()) and len(self.points) > 0:
          if abs(event.x / self.scale_factor - self.points[-1][0]) > abs(event.y / self.scale_factor - self.points[-1][1]):
            event.y = float(self.points[-1][1]) * self.scale_factor
          else:
            event.x = float(self.points[-1][0]) * self.scale_factor

        lang_found = False
        for lang in self._window.acbf_document.languages:
          if lang[1] == 'TRUE':
            lang_found = True
        if self.drawing_texts and not lang_found:
          message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Can't draw text areas. No languages are defined for this comic book with 'show' attribute checked.")
          response = message.run()
          message.destroy()
          return

        x = widget.get_allocation().x
        y = widget.get_allocation().y
        width = widget.get_allocation().width
        height = widget.get_allocation().height
        da_width, da_height = self.drawing_area.get_size_request()
        s_width, s_height = self.sidebar.get_size_request()

        if self._window.preferences.get_value("snap") == "True":
          if event.x > da_width - 7:
            event.x = float(da_width - 1)
          elif event.x < 7:
            event.x = float(1)

          if event.y > da_height - 7:
            event.y = float(da_height - 1)
          elif event.y < 7:
            event.y = float(1)
          
        if ((len(self.points) > 0) and
            (event.x > self.points[0][0] - 3 and event.x < self.points[0][0] + 3) and 
            (event.y > self.points[0][1] - 3 and event.y < self.points[0][1] + 3)):
          if len(self.points) > 2:
            self.enclose_rectangle()
          elif ((event.x >= x and event.x <= da_width) and 
                (event.y >= y and event.y <= da_height)):
            self.points.append((int(event.x / self.scale_factor), int(event.y / self.scale_factor)))
        elif ((event.x >= x and event.x <= da_width) and 
              (event.y >= y and event.y <= da_height)):
          self.points.append((int(event.x / self.scale_factor), int(event.y / self.scale_factor)))
        
        if self.drawing_rounded_rectangle and len(self.points) == 2:
          self.points = rounded_rectangle(self.points[0], self.points[1])
          self.enclose_rectangle()
          self.drawing_rounded_rectangle = False
          self.get_window().set_cursor(None)
        self.drawing_area.queue_draw()
    
    def cancel_rectangle(self, *args):
        self.draw_page_image()
        self.points = []

    def enclose_rectangle(self, color="#ffffff", *args):
        if len(self.points) > 2:
          xml_frame = ''
          for point in self.points:
            xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
          for page in self._window.acbf_document.pages:
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
              if self.drawing_frames:
                #add frame
                element = xml.SubElement(page, "frame", points=xml_frame.strip())
                self.load_frames()
                self.set_modified()
                    
              elif self.drawing_texts:
                #add text-area
                for lang in self._window.acbf_document.languages:
                  if lang[1] == 'TRUE':
                    layer_found = False
                    for layer in page.findall("text-layer"):
                      if layer.get("lang") == lang[0]:
                        layer_found = True
                        area = xml.SubElement(layer, "text-area", points=xml_frame.strip(), bgcolor=str(color))
                        par = xml.SubElement(area, "p")
                        par.text = '...'
                    if not layer_found:
                      layer = xml.SubElement(page, "text-layer", lang=lang[0])
                      area = xml.SubElement(layer, "text-area", points=xml_frame.strip(), bgcolor=str(color))
                      par = xml.SubElement(area, "p")
                      par.text = '...'
                self.load_texts()
                self.set_modified()
                #self.pixmap.draw_polygon(self.text_layers_gc, False, self.scale_polygon(self.points))

          self.draw_drawable()
          self.points = []

    def rotate_coords(self, x, y, theta, ox, oy):
      """Rotate arrays of coordinates x and y by theta radians about the
      point (ox, oy)."""
      s, c = numpy.sin(theta), numpy.cos(theta)
      x, y = numpy.asarray(x) - ox, numpy.asarray(y) - oy
      return x * c - y * s + ox, x * s + y * c + oy

    def rotate_image(self, src, theta, ox, oy, fill=0):
      """Rotate the image src by theta radians about (ox, oy).
      Pixels in the result that don't correspond to pixels in src are
      replaced by the value fill."""

      # Images have origin at the top left, so negate the angle.
      theta = -theta

      # Dimensions of source image. Note that scipy.misc.imread loads
      # images in row-major order, so src.shape gives (height, width).
      sh, sw = src.shape

      # Rotated positions of the corners of the source image.
      cx, cy = self.rotate_coords([0, sw, sw, 0], [0, 0, sh, sh], theta, ox, oy)

      # Determine dimensions of destination image.
      dw, dh = (int(numpy.ceil(c.max() - c.min())) for c in (cx, cy))

      # Coordinates of pixels in destination image.
      dx, dy = numpy.meshgrid(numpy.arange(dw), numpy.arange(dh))

      # Corresponding coordinates in source image. Since we are
      # transforming dest-to-src here, the rotation is negated.
      sx, sy = self.rotate_coords(dx + cx.min(), dy + cy.min(), -theta, ox, oy)

      # Select nearest neighbour.
      sx, sy = sx.round().astype(int), sy.round().astype(int)

      # Mask for valid coordinates.
      mask = (0 <= sx) & (sx < sw) & (0 <= sy) & (sy < sh)

      # Create destination image.
      dest = numpy.empty(shape=(dh, dw), dtype=src.dtype)

      # Copy valid coordinates from source image.
      dest[dy[mask], dx[mask]] = src[sy[mask], sx[mask]]

      # Fill invalid coordinates.
      dest[dy[~mask], dx[~mask]] = fill

      return dest

    def text_bubble_detection(self, x, y, *args):
        x = int(x / self.scale_factor)
        y = int(y / self.scale_factor)
        current_page_image = os.path.join(self._window.tempdir, self.selected_page)
        if current_page_image[-4:].upper() == 'WEBP':
          im = Image.open(current_page_image)
          rgb_im = im.convert('RGB')
          temp_image = current_page_image[:-4] + 'png'
          rgb_im.save(temp_image)
          rgb = cv2.imread(temp_image, 1)
          if os.path.isfile(temp_image):
            os.remove(temp_image)
        else:
          rgb = cv2.imread(current_page_image, 1)

        imgray = cv2.GaussianBlur(rgb,(5,5),0)
        imgray = cv2.cvtColor(imgray, cv2.COLOR_BGR2GRAY)
        imgray = cv2.copyMakeBorder(imgray,6,6,6,6,cv2.BORDER_CONSTANT,0)
        height, width = imgray.shape[:2]
        border = int(float((min(height, width))) * 0.008)
        if border < 2:
          border = 2
        #cv2.imshow("im", imgray)
          
        # get point color and range
        px = int(imgray[y + 6, x + 6])
        px_color = rgb[y, x]
        low_color = max(0, px - 30)
        high_color = min(255, px + 30)

        # threshold image on selected color
        thresholded = cv2.inRange(imgray, low_color, high_color)
        #cv2.imshow("threshold", thresholded)

        # floodfil with gray
        mask = numpy.zeros((height + 2, width + 2), numpy.uint8)
        cv2.floodFill(thresholded, mask, (x + 7, y + 7), 100)
        mask = cv2.inRange(thresholded, 99, 101)
        #cv2.circle(mask, (x + 7, y + 7), 2, 200)
        #cv2.imshow("flood", mask)

        # remove holes and narrow lines
        """self.text_bubble_fill_inside(mask, 0.1, True)
        #cv2.imshow("close1", mask)
        mask = numpy.rot90(mask, 1)
        self.text_bubble_fill_inside(mask, 0.08, True)
        mask = numpy.rot90(mask, 3)
        #cv2.imshow("close2", mask)"""
        
        #carve out the bubble first
        min_x = 0
        min_y = 0
        max_x = 0
        max_y = 0
        for idx, line in enumerate(mask):
          if cv2.countNonZero(line) > 0:
            if min_x == 0 or min_x > numpy.nonzero(line)[0][0]:
              min_x = numpy.nonzero(line)[0][0]
            if max_x == 0 or max_x < numpy.nonzero(line)[0][-1]:
              max_x = numpy.nonzero(line)[0][-1]
            if cv2.countNonZero(line) > 0 and min_y == 0:
              min_y = idx
            if cv2.countNonZero(line) > 0 and max_y < idx:
              max_y = idx
        mask = mask[min_y - 1:max_y + 1, min_x - 1:max_x + 2]
        hi, wi = mask.shape

        # check if it's rectangle
        check = numpy.copy(mask)
        self.text_bubble_fill_inside(check, 0.08)
        
        if (numpy.count_nonzero(check)/float(check.size)) > 0.9:
          is_rectangle = True
        else:
          is_rectangle = False

        # rotate and remove short lines (bubble tail)
        for angle in (0, 1):
          if is_rectangle:
            mask = self.rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
            mask = self.rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
          else:
            self.text_bubble_cut_tails(mask, 0.15)
            mask = self.rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
            #cv2.imshow("B" + str(angle), mask)
            self.text_bubble_cut_tails(mask, 0.15)
            mask = self.rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
            #cv2.imshow("C" + str(angle), mask)
        rhi, rwi = mask.shape
        mask = mask[int((rhi - hi) / 2) - 10:int((rhi - hi) / 2) + hi + 10, int((rwi - wi) / 2) - 10:int((rwi - wi) / 2) + wi + 10]

        # remove text
        self.text_bubble_fill_inside(mask, 0.08)
        mask = numpy.rot90(mask, 1)
        self.text_bubble_fill_inside(mask, 0.08)
        mask = numpy.rot90(mask, 1)

        # check if top/bottom is straight line
        if numpy.count_nonzero(mask[11])/float(mask[11].size) > 0.5:
          is_cut_at_top = True
        else:
          is_cut_at_top = False

        if numpy.count_nonzero(mask[-12])/float(mask[-12].size) > 0.5:
          is_cut_at_bottom = True
        else:
          is_cut_at_bottom = False

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border, border))
        mask = cv2.erode(mask, kernel, iterations = 1)

        # edges
        mask = cv2.Canny(mask, 10, 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(border / 2), int(border / 2)))
        mask = cv2.dilate(mask, kernel, iterations = 1)
        #cv2.imshow("edg", mask)

        # find contours
        i = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        try:
          contours, h = i[1], i[2]
        except:
          contours, h = i[0], i[1]

        if len(contours) == 0:
          raise

        countours_sorted = sorted(contours, key=lambda x:cv2.contourArea(x), reverse = True)
        arc_len = cv2.arcLength(countours_sorted[0], True)
        approx = cv2.approxPolyDP(countours_sorted[0], 0.003 * arc_len, True)
        self.points = []

        # move due to mask and image border added earlier + bubble carve out
        for point in approx.tolist():
          x = point[0][0] - 6 + min_x - 11
          y = point[0][1] - 6 + min_y - 10
          self.points.append((x, y))

        # cut top and bottom of the bubble (helps text-fitting algorithm)
        cut_by = 1 + round(height * 0.001, 0)
        min_y = min(self.points,key=lambda item:item[1])[1]
        max_y = max(self.points,key=lambda item:item[1])[1]
        new_points = []
        points_on_line_upper = []
        points_on_line_lower = []
        for point in self.points:
          if is_rectangle:
            if point[1] < min_y + (cut_by * 0.5):
              new_points.append((point[0], min_y + int(cut_by * 0.5)))
              points_on_line_upper.append((point[0], min_y + int(cut_by * 0.5)))
            elif point[1] > (max_y - (cut_by * 0.3)):
              new_points.append((point[0], max_y - int(cut_by * 0.3)))
              points_on_line_lower.append((point[0], max_y - int(cut_by * 0.3)))
            else:
              new_points.append((point[0], point[1]))
          elif is_cut_at_top:
            if point[1] < min_y + (cut_by * 0.1):
              new_points.append((point[0], min_y + int(cut_by * 0.1)))
              points_on_line_upper.append((point[0], min_y + int(cut_by * 0.1)))
            elif point[1] > (max_y - (cut_by * 0.7)):
              new_points.append((point[0], max_y - int(cut_by * 0.7)))
              points_on_line_lower.append((point[0], max_y - int(cut_by * 0.7)))
            else:
              new_points.append((point[0], point[1]))
          elif is_cut_at_bottom:
            if point[1] < min_y + (cut_by * 1):
              new_points.append((point[0], min_y + int(cut_by * 1)))
              points_on_line_upper.append((point[0], min_y + int(cut_by * 1)))
            elif point[1] > (max_y - (cut_by * 0.1)):
              new_points.append((point[0], max_y - int(cut_by * 0.1)))
              points_on_line_lower.append((point[0], max_y - int(cut_by * 0.1)))
            else:
              new_points.append((point[0], point[1]))
          else:
            if point[1] < min_y + (cut_by * 1):
              new_points.append((point[0], min_y + int(cut_by * 1)))
              points_on_line_upper.append((point[0], min_y + int(cut_by * 1)))
            elif point[1] > (max_y - (cut_by * 0.7)):
              new_points.append((point[0], max_y - int(cut_by * 0.7)))
              points_on_line_lower.append((point[0], max_y - int(cut_by * 0.7)))
            else:
              new_points.append((point[0], point[1]))

        # remove points on the same line
        try:
          points_on_line_upper_max_x = max(points_on_line_upper,key=lambda x:x[0])
          points_on_line_upper_min_x = min(points_on_line_upper,key=lambda x:x[0])
          points_on_line_lower_max_x = max(points_on_line_lower,key=lambda x:x[0])
          points_on_line_lower_min_x = min(points_on_line_lower,key=lambda x:x[0])

          self.points = []
          for point in new_points:
            if point in (points_on_line_upper_max_x, points_on_line_upper_min_x, points_on_line_lower_max_x, points_on_line_lower_min_x):
              self.points.append(point)
            elif point not in points_on_line_upper and point not in points_on_line_lower:
              self.points.append(point)
        except:
          self.points = new_points

        #print(len(self.points))
        
        self.enclose_rectangle('#%02x%02x%02x' % (px_color[2], px_color[1], px_color[0]))
        return True

    def text_bubble_cut_tails(self, mask, narrow_by, *args):
        zero_these = {}
        for idx, line in enumerate(mask):
          if cv2.countNonZero(line) > 0:
            zero_these[idx] = (numpy.nonzero(line)[0][0], numpy.nonzero(line)[0][-1], len(numpy.nonzero(line)[0]))
            
        values = list(zero_these.values())
        keys = list(zero_these.keys())
        keys.sort()
        bubble_width = max(values,key=lambda item:item[2])[2]
        
        for idx, line in enumerate(mask):
          if idx in zero_these and zero_these[idx][2] < bubble_width * narrow_by: # remove narrow lines
            mask[idx] = 0
        return mask

    def text_bubble_fill_inside(self, mask, narrow_by, *args):
        zero_these = {}
        for idx, line in enumerate(mask):
          if cv2.countNonZero(line) > 0:
            zero_these[idx] = (numpy.nonzero(line)[0][0], numpy.nonzero(line)[0][-1], len(numpy.nonzero(line)[0]))
            
        values = list(zero_these.values())
        keys = list(zero_these.keys())
        keys.sort()
        bubble_width = max(values,key=lambda item:item[2])[2]
        
        for idx, line in enumerate(mask):
          if idx in zero_these: # remove inside holes
            mask[idx][zero_these[idx][0]:zero_these[idx][1]] = 255
        return mask

    def text_bubble_detection_cursor(self, *args):
        if self.get_current_page_number() == 1:
          return
        if not self.drawing_texts:
          self.notebook.set_current_page(2)
        
        lang_found = False
        for lang in self._window.acbf_document.languages:
          if lang[1] == 'TRUE':
            lang_found = True
        if self.drawing_texts and not lang_found:
          message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Can't draw text areas. No languages are defined for this comic book with 'show' attribute checked.")
          response = message.run()
          message.destroy()
          return
        
        self.detecting_bubble = True
        cross_cursor = Gdk.Cursor(Gdk.CursorType.CROSS)
        self.get_window().set_cursor(cross_cursor)

    def frames_detection(self, *args):
        if self.get_current_page_number() == 1:
          return
        if not self.drawing_frames:
          self.notebook.set_current_page(1)
        self.set_cursor_loading()
        
        CANNY = 500
        
        current_page_image = os.path.join(self._window.tempdir, self.selected_page)
        if current_page_image[-4:].upper() == 'WEBP':
          im = Image.open(current_page_image)
          rgb_im = im.convert('RGB')
          temp_image = current_page_image[:-4] + 'png'
          rgb_im.save(temp_image)
          rgb = cv2.imread(temp_image, 1)
          if os.path.isfile(temp_image):
            os.remove(temp_image)
        else:
          rgb = cv2.imread(current_page_image, 1)

        height, width, channels = rgb.shape
        mask = numpy.zeros((height, width), numpy.uint8)
        
        border = int(float((min(height, width))) * 0.008)
        if border < 2:
          border = 2
        
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 2, 10, 120)
        gray = cv2.copyMakeBorder(gray,6,6,6,6,cv2.BORDER_CONSTANT,value=250)
        edges = cv2.Canny(gray, 10, CANNY)
        #cv2.imshow("edges", edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(border / 2), int(border / 2)))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        #cv2.imshow("closed", closed)
        i = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        try:
          contours, h = i[1], i[2]
        except:
          contours, h = i[0], i[1]
        rectangles = []

        cont_area = 0
        for cont in contours:
          # shapes greater than 10% of image size and less than 90%
          if cv2.contourArea(cont) > (height * width) * 0.03 and cv2.contourArea(cont) < (height * width) * 0.95:
            arc_len = cv2.arcLength(cont, True)
            approx = cv2.approxPolyDP(cont, 0.01 * arc_len, True)
            # it is rectangle
            if (len(approx) in (3, 4, 5, 6)):
              cont_area = cont_area + cv2.contourArea(cont)
              cv2.drawContours(mask, [cont], 0, 255, -1)
              M = cv2.moments(cont)
              cX = int(M["m10"] / M["m00"])
              cY = int(M["m01"] / M["m00"])
              self.points = []
              min_x = 99999999999
              min_y = 99999999999
              for point in approx.tolist():
                x = point[0][0] - 6
                y = point[0][1] - 6
                
                # enlarge rectangle
                if x > cX:
                  x = x + border
                else:
                  x = x - border

                if y > cY:
                  y = y + border
                else:
                  y = y - border

                if x < 0:
                  x = 0
                if y < 0:
                  y = 0
                if x > width:
                 x = width
                if y > height:
                  y = height                

                if x < min_x:
                  min_x = x
                if y < min_y:
                  min_y = y
                
                self.points.append((x, y))

              centroid = self.centroid_for_polygon(self.points, border)
              rectangles.append((self.points, centroid[0], centroid[1], min_x, min_y))

        if len(rectangles) == 0:
          message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.INFO, buttons=gtk.ButtonsType.OK, message_format="Failed to detect frames.")
          response = message.run()
          message.destroy()
          self.get_window().set_cursor(None)
          return

        # find unindentified frames
        all_recs = []
        for rec in rectangles:
          all_recs = all_recs + rec[0]

        min_x = min(all_recs,key=lambda item:item[0])[0] - border
        max_x = max(all_recs,key=lambda item:item[0])[0] + border
        min_y = min(all_recs,key=lambda item:item[1])[1] - border
        max_y = max(all_recs,key=lambda item:item[1])[1] + border
        horizontal_length = max_x - min_x
        vertical_length = max_y - min_y

        # area with identified frames less than 90%
        if cont_area / (horizontal_length * vertical_length) < 0.9:
          for idx, line in enumerate(mask):
            if idx <= min_y or idx >= max_y:
              mask[idx] = 255
          mask = numpy.rot90(mask, 3)
          for idx, line in enumerate(mask):
            if idx <= min_x or idx >= max_x:
              mask[idx] = 255
          mask = numpy.rot90(mask, 1)
          
          #small = cv2.resize(mask, (0,0), fx=0.2, fy=0.2) 
          #cv2.imshow("1", small)
          kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border * 4, border * 4))
          mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
          mask = cv2.bitwise_not(mask)
          kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border * 2, border * 2))
          mask = cv2.erode(mask, kernel, iterations = 1)
          mask = cv2.Canny(mask, 10, CANNY)
          kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(border / 2), int(border / 2)))
          mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
          i = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
          try:
            contours, h = i[1], i[2]
          except:
            contours, h = i[0], i[1]

          for cont in contours:
            # shapes greater than 10% of image size and less than 90%
            if cv2.contourArea(cont) > (height * width) * 0.03 and cv2.contourArea(cont) < (height * width) * 0.95:
              arc_len = cv2.arcLength(cont, True)
              approx = cv2.approxPolyDP(cont, 0.01 * arc_len, True)
              # it is rectangle
              if (len(approx) > 3):
                self.points = []
                for point in approx.tolist():
                  x = point[0][0]
                  y = point[0][1]
                  self.points.append((x, y))
                min_x = min(self.points,key=lambda item:item[0])[0]
                min_y = min(self.points,key=lambda item:item[1])[1]
                centroid = self.centroid_for_polygon(self.points, border)
                rectangles.append((self.points, centroid[0], centroid[1], min_x, min_y))
        
        rectangles.sort(key=lambda tup: (tup[2], tup[1]))
        for idx, rect in enumerate(rectangles):
          self.points = rect[0]
          self.enclose_rectangle()
        
        self.get_window().set_cursor(None)
        return

    def round_to(self, value, base):
        return int(base * round(float(value)/base))

    def left_anochor_for_polygon(self, polygon):
        min_dist = 999999999999999999999
        min_point = (10, 10)
        for point in polygon:
          dist = ((0 - point[0])**2 + (0 - point[1])**2)**0.5
          if dist < min_dist:
            min_dist = dist
            min_point = point
        return min_point
        
    def area_for_polygon(self, polygon):
        result = 0
        imax = len(polygon) - 1
        for i in range(0,imax):
            result += (polygon[i][0] * polygon[i+1][1]) - (polygon[i+1][0] * polygon[i][1])
        result += (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1])
        return result / 2.

    def centroid_for_polygon(self, polygon, border):
        area = self.area_for_polygon(polygon)
        imax = len(polygon) - 1

        result_x = 0
        result_y = 0
        for i in range(0,imax):
            result_x += (polygon[i][0] + polygon[i+1][0]) * ((polygon[i][0] * polygon[i+1][1]) - (polygon[i+1][0] * polygon[i][1]))
            result_y += (polygon[i][1] + polygon[i+1][1]) * ((polygon[i][0] * polygon[i+1][1]) - (polygon[i+1][0] * polygon[i][1]))
        result_x += (polygon[imax][0] + polygon[0][0]) * ((polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1]))
        result_y += (polygon[imax][1] + polygon[0][1]) * ((polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1]))
        result_x /= (area * 6.0)
        result_y /= (area * 6.0)

        return (self.round_to(result_x, border * 25), self.round_to(result_y, border * 38))

    def onPageSelectionChanged(self, tree_selection):
        (model, pathlist) = tree_selection.get_selected_rows()
        for path in pathlist:
            page_tree_iter = model.get_iter(path)
            page = model.get_value(page_tree_iter,0)
            dir_tree_iter = model.get_iter(path[0])
            directory = model.get_value(dir_tree_iter,0)
            color = Gdk.RGBA()
            if page != directory:
              if directory == 'Cover Page':
                self.selected_page = self._window.acbf_document.bookinfo.find("coverpage/" + "image").get("href").replace("\\", "/")
                self.selected_page_bgcolor = None
                Gdk.RGBA.parse(color, self._window.acbf_document.bg_color)
              else:
                if directory == 'Root':
                  self.selected_page = page.replace("\\", "/")
                else:
                  self.selected_page = os.path.join(directory, page).replace("\\", "/")
                for p in self._window.acbf_document.tree.findall("body/page"):
                  if p.find("image").get("href").replace("\\", "/") == self.selected_page:
                    self.selected_page_bgcolor = p.get("bgcolor")
              try:
                Gdk.RGBA.parse(color, self.selected_page_bgcolor)
              except:
                Gdk.RGBA.parse(color, self._window.acbf_document.bg_color)
              self.page_color_button.set_rgba(color)
              for key in self.transition_dropdown_dict:
                if self.transition_dropdown_dict[key].replace(' ', '_').upper() == self._window.acbf_document.get_page_transition(self.get_current_page_number()).upper():
                  self.transition_dropdown_is_active = False
                  self.transition_dropdown.set_active(key)
                  self.transition_dropdown_is_active = True
              if self._window.acbf_document.get_page_transition(self.get_current_page_number()).upper() == 'UNDEFINED':
                self.transition_dropdown_is_active = False
                self.transition_dropdown.set_active(0)
                self.transition_dropdown_is_active = True
              self.draw_page_image()
              self.points = []
              self.sw_image.get_vadjustment().value = 0
              self.sw_image.get_hadjustment().value = 0
              self.fsw.get_vadjustment().value = 0
              self.tsw.get_vadjustment().value = 0

class ColorDialog(gtk.ColorChooserDialog):
    
    def __init__(self, window, color, set_transparency, is_transparent):
        self._window = window
        gtk.Dialog.__init__(self, 'Color Selection Dialog', None, gtk.DialogFlags.DESTROY_WITH_PARENT)
        color_string = 'rgb(' + str(int(color.red/256)) + ',' + str(int(color.green/256)) + ',' + str(int(color.blue/256)) + ')'
        self.color_RGBA = Gdk.RGBA()
        self.color_RGBA.parse(color_string)
        self.set_rgba(self.color_RGBA)
        #self.get_color_selection().set_has_palette(True)
        self.transparency_button = gtk.CheckButton("Set Transparent")
        self.transparency_button.set_active(False)
        
        #if set_transparency:
        #  self.get_color_selection().get_children()[0].get_children()[1].pack_start(self.transparency_button, True, True, 0)
        #  self.transparency_button.show_all()
        #  self.transparency_button.connect('toggled', self.change_transparency)
        self.show_all()
        #if is_transparent != None and is_transparent.upper() == 'TRUE':
        #  self.transparency_button.set_active(True)

    def change_transparency(self, widget, *args):
        if widget.get_active():
          for i in widget.get_parent().get_parent().get_children()[0]:
            i.set_sensitive(False)
          for i in widget.get_parent().get_parent().get_children()[1]:
            i.set_sensitive(False)
          widget.set_sensitive(True)
        else:
          for i in widget.get_parent().get_parent().get_children()[0]:
            i.set_sensitive(True)
          for i in widget.get_parent().get_parent().get_children()[1]:
            i.set_sensitive(True)

class TextBoxDialog(gtk.Dialog):
    
    def __init__(self, window, area_number):
        self._window = window
        gtk.Dialog.__init__(self, 'Edit Text Layers (' + str(area_number) + ')', None, gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        self.set_resizable(True)
        self.set_border_width(8)
        self.set_size_request(700 * self._window._window.ui_scale_factor, 400 * self._window._window.ui_scale_factor)
        self.connect('key_press_event', self.key_pressed)
        
    def key_pressed(self, widget, event):
      """print(dir(Gdk.KEY))"""
      if event.keyval == Gdk.KEY_F1:
        self.show_help()
        return True
      elif event.state & Gdk.ModifierType.CONTROL_MASK:
        if event.keyval in (Gdk.KEY_e, Gdk.KEY_E):
          if len(self._window.text_box.get_buffer().get_selection_bounds()) > 0:
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[0],'<emphasis>')
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[1],'</emphasis>')
            self._window.text_box.get_buffer().place_cursor(self._window.text_box.get_buffer().get_selection_bounds()[0])
          else:
            self._window.text_box.get_buffer().insert_at_cursor('<emphasis></emphasis>')
            cursorPosition = self._window.text_box.get_buffer().get_property("cursor-position") - 11
            cursorIter = self._window.text_box.get_buffer().get_iter_at_offset(cursorPosition)
            self._window.text_box.get_buffer().place_cursor(cursorIter)
        elif event.keyval in (Gdk.KEY_s, Gdk.KEY_S):
          if len(self._window.text_box.get_buffer().get_selection_bounds()) > 0:
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[0],'<strong>')
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[1],'</strong>')
            self._window.text_box.get_buffer().place_cursor(self._window.text_box.get_buffer().get_selection_bounds()[0])
          else:
            self._window.text_box.get_buffer().insert_at_cursor('<strong></strong>')
            cursorPosition = self._window.text_box.get_buffer().get_property("cursor-position") - 9
            cursorIter = self._window.text_box.get_buffer().get_iter_at_offset(cursorPosition)
            self._window.text_box.get_buffer().place_cursor(cursorIter)
        elif event.keyval in (Gdk.KEY_r, Gdk.KEY_R):
          if len(self._window.text_box.get_buffer().get_selection_bounds()) > 0:
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[0],'<strikethrough>')
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[1],'</strikethrough>')
            self._window.text_box.get_buffer().place_cursor(self._window.text_box.get_buffer().get_selection_bounds()[0])
          else:
            self._window.text_box.get_buffer().insert_at_cursor('<strikethrough></strikethrough>')
            cursorPosition = self._window.text_box.get_buffer().get_property("cursor-position") - 16
            cursorIter = self._window.text_box.get_buffer().get_iter_at_offset(cursorPosition)
            self._window.text_box.get_buffer().place_cursor(cursorIter)
        elif event.keyval in (Gdk.KEY_p, Gdk.KEY_P):
          if len(self._window.text_box.get_buffer().get_selection_bounds()) > 0:
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[0],'<sup>')
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[1],'</sup>')
            self._window.text_box.get_buffer().place_cursor(self._window.text_box.get_buffer().get_selection_bounds()[0])
          else:
            self._window.text_box.get_buffer().insert_at_cursor('<sup></sup>')
            cursorPosition = self._window.text_box.get_buffer().get_property("cursor-position") - 6
            cursorIter = self._window.text_box.get_buffer().get_iter_at_offset(cursorPosition)
            self._window.text_box.get_buffer().place_cursor(cursorIter)
        elif event.keyval in (Gdk.KEY_b, Gdk.KEY_B):
          if len(self._window.text_box.get_buffer().get_selection_bounds()) > 0:
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[0],'<sub>')
            self._window.text_box.get_buffer().insert(self._window.text_box.get_buffer().get_selection_bounds()[1],'</sub>')
            self._window.text_box.get_buffer().place_cursor(self._window.text_box.get_buffer().get_selection_bounds()[0])
          else:
            self._window.text_box.get_buffer().insert_at_cursor('<sub></sub>')
            cursorPosition = self._window.text_box.get_buffer().get_property("cursor-position") - 6
            cursorIter = self._window.text_box.get_buffer().get_iter_at_offset(cursorPosition)
            self._window.text_box.get_buffer().place_cursor(cursorIter)
        elif event.keyval in (Gdk.KEY_u, Gdk.KEY_U):
          if len(self._window.text_box.get_buffer().get_selection_bounds()) > 0:
            bounds = self._window.text_box.get_buffer().get_selection_bounds()
            text = self._window.text_box.get_buffer().get_text(bounds[0], bounds[1]).decode('utf-8').upper()
            text = text.replace(u'<EMPHASIS>', u'<emphasis>').replace(u'</EMPHASIS>', u'</emphasis>')
            text = text.replace(u'<STRONG>', u'<strong>').replace(u'</STRONG>', u'</strong>')
            text = text.replace(u'<STRIKETHROUGH>', u'<strikethrough>').replace(u'</STRIKETHROUGH>', u'</strikethrough>')
            text = text.replace(u'<SUP>', u'<sup>').replace(u'</SUP>', u'</sup>')
            text = text.replace(u'<SUB>', u'<sub>').replace(u'</SUB>', u'</sub>')
            self._window.text_box.get_buffer().delete(bounds[0], bounds[1])
            self._window.text_box.get_buffer().insert(bounds[0],text)
          else:
            bounds = self._window.text_box.get_buffer().get_bounds()
            text = self._window.text_box.get_buffer().get_text(bounds[0], bounds[1]).decode('utf-8').upper()
            text = text.replace(u'<EMPHASIS>', u'<emphasis>').replace(u'</EMPHASIS>', u'</emphasis>')
            text = text.replace(u'<STRONG>', u'<strong>').replace(u'</STRONG>', u'</strong>')
            text = text.replace(u'<STRIKETHROUGH>', u'<strikethrough>').replace(u'</STRIKETHROUGH>', u'</strikethrough>')
            text = text.replace(u'<SUP>', u'<sup>').replace(u'</SUP>', u'</sup>')
            text = text.replace(u'<SUB>', u'<sub>').replace(u'</SUB>', u'</sub>')
            self._window.text_box.get_buffer().set_text(text)
        elif event.keyval == Gdk.KEY_space:
          self._window.text_box.get_buffer().insert_at_cursor(' ')
      return False

    def show_help(self, *args):
      dialog = gtk.Dialog('Help', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT, (gtk.STOCK_CLOSE, gtk.ResponseType.CLOSE))
      dialog.height = 300
      dialog.set_resizable(False)
      dialog.set_border_width(8)

      #Shortcuts
      hbox = gtk.HBox(False, 10)
      label = gtk.Label()
      label.set_markup('<b>Shortcuts</b>')
      hbox.pack_start(label, False, False, 0)
      dialog.vbox.pack_start(hbox, False, False, 10)

      # left side
      main_hbox = gtk.HBox(False, 3)
      left_vbox = gtk.VBox(False, 3)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_HELP)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('This help window (F1)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_ITALIC)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Add &lt;emphasis> tags (CTRL + e)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_GOTO_TOP)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Add &lt;sup&gt; tags (CTRL + p)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)
      
      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_STRIKETHROUGH)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Add &lt;strikethrough&gt; tags (CTRL + r)')
      hbox.pack_start(label, False, False, 3)
      left_vbox.pack_start(hbox, False, False, 0)
      
      main_hbox.pack_start(left_vbox, False, False, 10)

      # right side
      right_vbox = gtk.VBox(False, 3)

      hbox = gtk.HBox(False, 3)
      button = gtk.Button(label = 'a..A')
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Convert text to uppercase (CTRL + u)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_BOLD)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Add &lt;strong&gt; tags (CTRL + s)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.ToolButton()
      button.set_stock_id(gtk.STOCK_GOTO_BOTTOM)
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Add &lt;sub&gt; tags (CTRL + b)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 3)
      button = gtk.Button(label = 'a___b')
      hbox.pack_start(button, False, False, 3)
      label = gtk.Label()
      label.set_markup('Insert non-breaking space (CTRL + space)')
      hbox.pack_start(label, False, False, 3)
      right_vbox.pack_start(hbox, False, False, 0)
      
      main_hbox.pack_start(right_vbox, False, False, 10)

      dialog.vbox.pack_start(main_hbox, False, False, 0)
      dialog.get_action_area().get_children()[0].grab_focus()

      # show it
      dialog.show_all()
      dialog.run()
      if dialog != None:
        dialog.destroy()

      return

def circle_quadrant(center_x, center_y, radius, quadrant):
    step_size = 0.1
    circle_points = []
    
    t = 0
    while t < 2 * math.pi:
      if t <= (math.pi / 2) and quadrant == 3:
        circle_points.append((int(radius * math.cos(t) + center_x), int(radius * math.sin(t) + center_y)))
      elif t >= (math.pi / 2) and t <= math.pi and quadrant == 4:
        circle_points.append((int(radius * math.cos(t) + center_x), int(radius * math.sin(t) + center_y)))
      elif t >= math.pi and t <= (math.pi * 1.5) and quadrant == 1:
        circle_points.append((int(radius * math.cos(t) + center_x), int(radius * math.sin(t) + center_y)))
      elif t >= (math.pi * 1.5) and quadrant == 2:
        circle_points.append((int(radius * math.cos(t) + center_x), int(radius * math.sin(t) + center_y)))
      t = t + step_size
    
    return circle_points

def rounded_rectangle(point_one, point_two):
    points = []
    width = abs(point_one[0] - point_two[0])
    height = abs(point_one[1] - point_two[1])
    top_left = (min(point_one[0], point_two[0]), min(point_one[1], point_two[1]))
    bottom_right = (max(point_one[0], point_two[0]), max(point_one[1], point_two[1]))
    radius = int(min(width, height) / 4)
    
    top_left_circle_center = (top_left[0] + radius, top_left[1] + radius)
    top_right_circle_center = (bottom_right[0] - radius, top_left[1] + radius)
    bottom_right_circle_center = (bottom_right[0] - radius, bottom_right[1] - radius)
    bottom_left_circle_center = (top_left[0] + radius, bottom_right[1] - radius)
    
    # add first quadrant
    circle_points = circle_quadrant(top_left_circle_center[0], top_left_circle_center[1], radius, 1)
    for i in circle_points:
      points.append(i)
    
    # add top line
    points.append((top_left[0] + radius, top_left[1]))
    points.append((top_left[0] + width - (radius * 2), top_left[1]))
    
    # add second quadrant
    circle_points = circle_quadrant(top_right_circle_center[0], top_right_circle_center[1], radius, 2)
    for i in circle_points:
      points.append(i)
    
    # add right line
    points.append((bottom_right[0], top_left[1] + radius))
    points.append((bottom_right[0], bottom_right[1] - (radius * 2)))
    
    # add third quadrant
    circle_points = circle_quadrant(bottom_right_circle_center[0], bottom_right_circle_center[1], radius, 3)
    for i in circle_points:
      points.append(i)
    
    # add bottom line
    points.append((bottom_right[0] - radius, bottom_right[1]))
    points.append((top_left[0] + radius, bottom_right[1]))
    
    # add fourth quadrant
    circle_points = circle_quadrant(bottom_left_circle_center[0], bottom_left_circle_center[1], radius, 4)
    for i in circle_points:
      points.append(i)
      
    # add bottom line
    points.append((top_left[0], bottom_right[1] - radius))
    points.append((top_left[0], top_left[1] + radius))
      
    return points
