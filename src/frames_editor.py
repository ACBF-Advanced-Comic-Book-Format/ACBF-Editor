# -*- coding: utf-8 -*-
"""frameseditor.py - Frames/Text Layers Editor Dialog.

Copyright (C) 2011-2018 Robert Kubik
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
import pathlib

import PIL.Image
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, PangoCairo, GObject, Gio
import cairo
import gi
from PIL import Image
import lxml.etree as xml
import re
from xml.sax.saxutils import escape, unescape
from copy import deepcopy
import numpy
import cv2

import constants
import text_layer
from typing import Any
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ListItem(GObject.Object):
    __gtype_name__ = "ListItem"
    label = GObject.Property(type=str)
    path = GObject.Property(type=str)
    is_cover = GObject.Property(type=bool, default=True)

    def __init__(self, label: str, path: str, is_cover: bool = False):
        super().__init__()
        self.label = label
        self.path = path
        self.is_cover = is_cover


class FrameItem(GObject.Object):
    __gtype_name__ = "FrameItem"
    cords = GObject.Property(type=GObject.TYPE_PYOBJECT)
    colour = GObject.Property(type=str)

    def __init__(self, cords, colour):
        super().__init__()
        self.cords = cords
        self.colour = colour

    def cords_str(self) -> str:
        cords_str: str = ""
        for cords in self.cords:
            cords_str += str(cords[0]) + "," + str(cords[1]) + " "

        return cords_str[:-1]


class TextLayerItem(GObject.Object):
    __gtype_name__ = "TextLayerItem"
    polygon = GObject.Property(type=GObject.TYPE_PYOBJECT)
    text = GObject.Property(type=str)
    colour = GObject.Property(type=str)
    is_inverted = GObject.Property(type=bool, default=False)
    is_transparent = GObject.Property(type=bool, default=False)
    type = GObject.Property(type=str)
    rotation = GObject.Property(type=int)
    references = GObject.Property(type=GObject.TYPE_PYOBJECT)

    def __init__(self, polygon: list, text: str, colour: str, is_inverted: bool, is_transparent: bool, type: str,
                 rotation: int, references: list):
        super().__init__()
        self.polygon = polygon
        self.text = text
        self.colour = colour
        self.is_inverted = is_inverted
        self.is_transparent = is_transparent
        self.type = type
        self.rotation = rotation
        self.references = references

    def poly_str(self) -> str:
        return str(self.polygon).replace("[", "").replace(")]", "").replace("(", "").replace("),", "").replace(", ", ",")

    def __str__(self) -> str:
        return f"Text: '{self.text}', Colour: '{self.colour}', Type: '{self.type}', Rotation: '{str(self.rotation)}'"


class FramesEditorDialog(Gtk.Window):
    """Frames Editor dialog."""

    def __init__(self, parent):
        self.parent = parent

        super().__init__(title="Frames/Text Layers Editor")
        self.set_transient_for(parent)
        self.connect("close-request", self.exit)
        self.set_size_request(1000, 1000)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)
        toolbar_top_tools: Gtk.ActionBar = Gtk.ActionBar()

        self.is_modified: bool = False
        self.points: list = []
        self.root_directory: pathlib.Path = os.path.dirname(self.parent.filename)
        self.selected_page = ""  # self.parent.acbf_document.bookinfo.find("coverpage/" + "image").get("href").replace("\\", "/")
        self.selected_page_bgcolor = None
        self.page_color_button: Gtk.ColorDialogButton = Gtk.ColorDialogButton()
        self.drawing_frames: bool = False
        self.drawing_texts: bool = False
        self.detecting_bubble: bool = False
        self.scale_factor: int = 1
        self.transition_dropdown_dict: dict[int, str] = {0: "", 1: "None", 2: "Fade", 3: "Blend", 4: "Scroll Right",
                                                         5: "Scroll Down"}
        self.transition_dropdown_is_active: bool = True

        self.frame_model = Gio.ListStore(item_type=FrameItem)
        self.text_layer_model = Gio.ListStore(item_type=TextLayerItem)

        frames_selection_model = Gtk.NoSelection(model=self.frame_model)
        texts_selection_model = Gtk.NoSelection(model=self.text_layer_model)

        # Create the ColumnView
        frames_column_view = Gtk.ColumnView(model=frames_selection_model)
        texts_column_view = Gtk.ColumnView(model=texts_selection_model)

        frames_order_factory = Gtk.SignalListItemFactory()
        frames_order_factory.connect("setup", self.setup_order_column)
        frames_order_factory.connect("bind", self.bind_order_column, "frame")
        frames_order_column = Gtk.ColumnViewColumn(title="Order", factory=frames_order_factory)
        frames_order_column.set_resizable(True)
        frames_column_view.append_column(frames_order_column)

        frames_move_factory = Gtk.SignalListItemFactory()
        frames_move_factory.connect("setup", self.setup_move_column)
        frames_move_factory.connect("bind", self.bind_move_column, "frame")
        frames_move_factory.connect("unbind", self.unbind_move_column)
        frames_move_column = Gtk.ColumnViewColumn(title="Move", factory=frames_move_factory)
        frames_move_column.set_resizable(True)
        frames_column_view.append_column(frames_move_column)

        frames_entry_factory = Gtk.SignalListItemFactory()
        frames_entry_factory.connect("setup", self.setup_entry_column)
        frames_entry_factory.connect("bind", self.bind_entry_column, "frame")
        frames_entry_column = Gtk.ColumnViewColumn(title="Coordinates", factory=frames_entry_factory)
        frames_entry_column.set_resizable(True)
        frames_entry_column.set_expand(True)
        frames_column_view.append_column(frames_entry_column)

        frames_colour_factory = Gtk.SignalListItemFactory()
        frames_colour_factory.connect("setup", self.setup_colour_column)
        frames_colour_factory.connect("bind", self.bind_colour_column, "frame")
        frames_colour_factory.connect("unbind", self.unbind_colour_column)
        frames_colour_column = Gtk.ColumnViewColumn(title="Colour", factory=frames_colour_factory)
        frames_column_view.append_column(frames_colour_column)

        frames_remove_factory = Gtk.SignalListItemFactory()
        frames_remove_factory.connect("setup", self.setup_remove_column)
        frames_remove_factory.connect("bind", self.bind_remove_column, "frame")
        frames_remove_factory.connect("unbind", self.unbind_remove_column)
        frames_remove_column = Gtk.ColumnViewColumn(title="Remove", factory=frames_remove_factory)
        frames_column_view.append_column(frames_remove_column)

        # Text layer factory
        texts_order_factory = Gtk.SignalListItemFactory()
        texts_order_factory.connect("setup", self.setup_order_column)
        texts_order_factory.connect("bind", self.bind_order_column, "text")
        texts_order_column = Gtk.ColumnViewColumn(title="Order", factory=frames_order_factory)
        texts_order_column.set_resizable(True)
        texts_column_view.append_column(texts_order_column)

        texts_move_factory = Gtk.SignalListItemFactory()
        texts_move_factory.connect("setup", self.setup_move_column)
        texts_move_factory.connect("bind", self.bind_move_column, "text")
        texts_move_factory.connect("unbind", self.unbind_move_column)
        texts_move_column = Gtk.ColumnViewColumn(title="Move", factory=texts_move_factory)
        texts_move_column.set_resizable(True)
        texts_column_view.append_column(texts_move_column)

        texts_entry_factory = Gtk.SignalListItemFactory()
        texts_entry_factory.connect("setup", self.setup_entry_column)
        texts_entry_factory.connect("bind", self.bind_entry_column, "text")
        texts_entry_factory.connect("unbind", self.unbind_entry_column)
        texts_entry_column = Gtk.ColumnViewColumn(title="Text", factory=texts_entry_factory)
        texts_entry_column.set_resizable(True)
        texts_entry_column.set_expand(True)
        texts_column_view.append_column(texts_entry_column)

        texts_colour_factory = Gtk.SignalListItemFactory()
        texts_colour_factory.connect("setup", self.setup_colour_column)
        texts_colour_factory.connect("bind", self.bind_colour_column, "text")
        texts_colour_factory.connect("unbind", self.unbind_colour_column)
        texts_colour_column = Gtk.ColumnViewColumn(title="Colour", factory=texts_colour_factory)
        texts_column_view.append_column(texts_colour_column)

        texts_type_factory = Gtk.SignalListItemFactory()
        texts_type_factory.connect("setup", self.setup_type_column)
        texts_type_factory.connect("bind", self.bind_type_column)
        texts_type_factory.connect("unbind", self.unbind_type_column)
        texts_type_column = Gtk.ColumnViewColumn(title="Type", factory=texts_type_factory)
        texts_column_view.append_column(texts_type_column)

        texts_remove_factory = Gtk.SignalListItemFactory()
        texts_remove_factory.connect("setup", self.setup_remove_column)
        texts_remove_factory.connect("bind", self.bind_remove_column, "text")
        texts_remove_factory.connect("unbind", self.unbind_remove_column)
        texts_remove_column = Gtk.ColumnViewColumn(title="Remove", factory=texts_remove_factory)
        texts_column_view.append_column(texts_remove_column)

        main_pane_vert = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        main_pane_horz = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_pane_vert.set_start_child(main_pane_horz)

        sidebar_sw = Gtk.ScrolledWindow()
        #sidebar_sw.set_hexpand(False)
        sidebar_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.pages_treestore = Gio.ListStore.new(item_type=ListItem)
        page_list_factory = Gtk.SignalListItemFactory()
        page_list_factory.connect("setup", self.setup_list_item)
        page_list_factory.connect("bind", self.bind_list_item)

        selection_model: Gtk.SingleSelection = Gtk.SingleSelection.new(self.pages_treestore)
        #selection_model.connect("selection-changed", self.page_selection_change)

        self.pages_tree: Gtk.ListView = Gtk.ListView.new(selection_model, page_list_factory)
        self.pages_tree.set_single_click_activate(True)

        for page in self.parent.acbf_document.pages:
            page_path = page.find("image").get("href").replace("\\", "/")
            # Remove extension from file name
            page_path_split = page_path.rsplit(".", 1)
            path_label = page_path_split[0].capitalize()
            self.pages_treestore.append(ListItem(label=path_label, path=page_path))

        '''directories.append('Cover Page')
        directories.append('Root')

        for page in self.parent.acbf_document.pages:
            page_path = page.find("image").get("href").replace("\\", "/")
            if '/' in page_path:
                if page_path[0:page_path.find('/')] not in directories:
                    directories.append(page_path[0:page_path.find('/')])

        for directory in directories:
            if directory == 'Cover Page':
                if '/' in page_path:
                    pages_treestore.append(ListItem("Cover", self.selected_page[self.selected_page.find('/') + 1:], True))
                else:
                    pages_treestore.append(ListItem("Cover", self.selected_page))
            else:
                for page in self.parent.acbf_document.pages:
                    page_path = page.find("image").get("href").replace("\\", "/")
                    if '/' in page_path and page_path[0:page_path.find('/')] == directory:
                        pages_treestore.append(ListItem(page_path[page_path.find('/') + 1:], page_path[page_path.find('/')]))
                    elif '/' not in page_path and directory == 'Root':
                        pages_treestore.append(ListItem(page_path, page_path))'''

        self.pages_tree.connect("activate", self.page_selection_changed)

        sidebar_sw.set_child(self.pages_tree)
        main_pane_horz.set_start_child(sidebar_sw)

        # page image
        self.sw_image = Gtk.ScrolledWindow()
        self.sw_image.set_size_request(500, 500)
        self.sw_image.set_min_content_width(50)
        self.sw_image.set_min_content_height(50)
        self.sw_image.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_content_height(500)
        self.drawing_area.set_content_width(300)
        self.drawing_area.set_draw_func(self.draw_func)
        da_mouse_press = Gtk.GestureClick()
        da_mouse_press.set_button(0)
        da_mouse_press.connect('pressed', self.draw_brush)
        self.drawing_area.add_controller(da_mouse_press)
        #self.drawing_area.connect("scroll-event", self.scrollparent)

        self.sw_image.set_child(self.drawing_area)
        main_pane_horz.set_end_child(self.sw_image)

        # general & frames & text-layers
        self.notebook = Gtk.Notebook()
        self.notebook.set_size_request(100, 200)
        self.notebook.set_vexpand(True)

        self.notebook.connect("switch-page", self.tab_change)

        # general
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.general_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.transition_dropdown: Gtk.DropDown = Gtk.DropDown.new_from_strings(list(self.transition_dropdown_dict.values()))
        self.transition_dropdown_model = self.transition_dropdown.get_model()
        self.load_general()

        sw.set_child(self.general_box)
        self.notebook.insert_page(sw, Gtk.Label(label='General'), -1)

        # frames
        self.fsw = Gtk.ScrolledWindow()
        #self.fsw.set_size_request(550, 150)

        self.fsw.set_child(frames_column_view)
        self.fsw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.notebook.insert_page(self.fsw, Gtk.Label(label='Frames'), -1)

        # text-layers
        self.tsw = Gtk.ScrolledWindow()
        self.tsw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.tsw.set_child(texts_column_view)
        self.notebook.insert_page(self.tsw, Gtk.Label(label='Text-Layers'), -1)

        main_pane_vert.set_end_child(self.notebook)

        # action area top tools
        copy_layer_button = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_layer_button.set_tooltip_text('Copy Text Layer')
        self.source_layer_frames = ""
        self.source_layer_frames_no = 0
        self.source_layer_texts = ""
        self.source_layer_texts_no = 0
        copy_layer_button.connect("clicked", self.copy_layer)
        #toolbar_top_tools.pack_start(copy_layer_button)

        paste_layer_button = Gtk.Button.new_from_icon_name("edit-paste-symbolic")
        paste_layer_button.set_tooltip_text("Paste Text Layer")
        paste_layer_button.connect("clicked", self.paste_layer)
        #toolbar_top_tools.pack_start(paste_layer_button)

        self.straight_button = Gtk.CheckButton.new_with_label("Draw straight lines")
        toolbar_top_tools.pack_start(self.straight_button)
        #toolbar.add_top_bar(toolbar_top_tools)

        self.zoom_dropdown: Gtk.DropDown = Gtk.DropDown.new_from_strings(
            ["10%", "25%", "50%", "75%", "100%", "125%", "175%", "200%"])
        self.zoom_dropdown.set_tooltip_text("Zoom")
        self.zoom_dropdown.set_selected(4)
        self.zoom_dropdown.connect("notify::selected", self.change_zoom)

        self.layer_dropdown: Gtk.DropDown = self.parent.create_lang_dropdown(self.parent.all_lang_store,
                                                                             self.change_layer)
        self.layer_dropdown.set_margin_end(5)

        toolbar_header.pack_start(self.layer_dropdown)
        toolbar_header.pack_start(self.zoom_dropdown)

        self.frames_color = Gdk.RGBA()
        self.frames_color.parse(self.parent.preferences.get_value("frames_color"))

        self.text_layers_color = Gdk.RGBA()
        self.text_layers_color.parse(self.parent.preferences.get_value("text_layers_color"))

        self.background_color = Gdk.RGBA()
        self.background_color.parse("#FFFFFF")

        self.frame_model.connect("items_changed", self.list_item_changed)
        self.text_layer_model.connect("items_changed", self.list_text_item_changed)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(toolbar_top_tools)
        content.append(main_pane_vert)
        # Add the ScrolledWindow to the main window
        self.set_child(content)

    def page_selection_change(self, selection_model, position, n_items):
        #print(position)
        pass

    def set_header_title(self, text: str = "") -> None:
        new_title: str = "Frames/Text Layers Editor - " + self.selected_page
        if self.is_modified:
            new_title += "*"
        self.set_title(new_title)

    def copy_layer(self, *args):
        number_of_frames = len(self.parent.acbf_document.load_page_frames(self.get_current_page_number()))
        number_of_texts = 0
        selected_layer = self.layer_dropdown.get_selected_item()
        if selected_layer.show:
            number_of_texts = len(
                self.parent.acbf_document.load_page_texts(self.get_current_page_number(), selected_layer)[0])

        if self.drawing_frames == False and self.drawing_texts == False:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Nothing to copy.\nSelect 'Frames' or 'Text-Layers' tab.")
        elif self.drawing_frames == True and number_of_frames == 0:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Nothing to copy.\nNo frames found on this page.")
        elif self.drawing_texts == True and number_of_texts == 0:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Nothing to copy.\nNo text-layers found on this page for layer: " + selected_layer)
        elif self.drawing_frames:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Frames layer copied: " + str(number_of_frames) + " objects.")
            self.source_layer_frames = self.selected_page
            self.source_layer_frames_no = self.get_current_page_number()
        elif self.drawing_texts:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Text-layer copied: " + str(number_of_texts) + " objects.")
            self.source_layer_texts = self.selected_page
            self.source_layer_texts_no = self.get_current_page_number()
        else:
            return
        #response = message.run()
        #message.destroy()
        return

    def paste_layer(self, *args):
        if self.drawing_frames:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.YES_NO,
                                        message_format="Are you sure you want to paste frames from page '" + self.source_layer_frames + "'?\nCurrent layer will be removed.")
        else:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.YES_NO,
                                        message_format="Are you sure you want to paste text-layers from page '" + self.source_layer_texts + "'?\nCurrent layer will be removed.")
        response = message.run()
        message.destroy()
        if response != Gtk.ResponseType.YES:
            return False

        if self.drawing_frames == False and self.drawing_texts == False:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Select 'Frames' or 'Text-Layers' tab to paste into.")
        elif self.drawing_frames and (
                self.source_layer_frames_no == 0 or self.source_layer_frames_no == self.get_current_page_number()):
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Nothing to paste. Copy frames from some other page first.")
        elif self.drawing_texts and (
                self.source_layer_texts_no == 0 or self.source_layer_texts_no == self.get_current_page_number()):
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Nothing to paste. Copy text-layer from some other page first.")
        elif self.drawing_frames:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Frames pasted from page " + self.source_layer_frames)
            self.set_modified()

            for page in self.parent.acbf_document.pages:
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    # delete all frames
                    for frame in page.findall("frame"):
                        page.remove(frame)

                    # copy frames from source page
                    for source_page in self.parent.acbf_document.pages:
                        if source_page.find("image").get("href").replace("\\", "/") == self.source_layer_frames:
                            for source_frame in source_page.findall("frame"):
                                page.append(deepcopy(source_frame))

            self.drawing_area.queue_draw()

        elif self.drawing_texts:
            selected_layer = self.layer_dropdown.get_selected_item()
            #message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, message_format="Text-layer pasted from page " + self.source_layer_texts)
            self.set_modified()
            layer_found = False

            for page in self.parent.acbf_document.pages:
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    for text_layer in page.findall("text-layer"):
                        if text_layer.get("lang") == selected_layer.lang_iso:
                            # delete text-areas
                            layer_found = True
                            for text_area in text_layer.findall("text-area"):
                                text_layer.remove(text_area)

                            # copy text-areas from source page
                            for source_page in self.parent.acbf_document.pages:
                                if source_page.find("image").get("href").replace("\\", "/") == self.source_layer_texts:
                                    for source_text_layer in source_page.findall("text-layer"):
                                        if source_text_layer.get("lang") == selected_layer.lang_iso:
                                            for source_text_area in source_text_layer.findall("text-area"):
                                                text_layer.append(deepcopy(source_text_area))

                    if not layer_found and selected_layer.show:
                        text_layer = xml.SubElement(page, "text-layer", lang=selected_layer.lang_iso)
                        for source_page in self.parent.acbf_document.pages:
                            if source_page.find("image").get("href").replace("\\", "/") == self.source_layer_texts:
                                for source_text_layer in source_page.findall("text-layer"):
                                    if source_text_layer.get("lang") == selected_layer.lang_iso:
                                        for source_text_area in source_text_layer.findall("text-area"):
                                            text_layer.append(deepcopy(source_text_area))

            self.load_texts()
        return

    def key_pressed(self, widget, event):
        """print dir(Gdk.KEY_"""
        # ALT + key
        if event.get_state() == Gdk.ModifierType.MOD1_MASK:
            None
        # CTRL + key
        if event.get_state() == Gdk.ModifierType.CONTROL_MASK:
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
                # self.window.set_cursor(None)
            elif event.keyval == Gdk.KEY_BackSpace:
                if len(self.points) == 1:
                    self.cancel_rectangle()
                    self.detecting_bubble = False
                    # self.window.set_cursor(None)
                elif len(self.points) > 1:
                    del self.points[-1]
                    #self.draw_page_image()
                    for point in self.points:
                        rect = (int(point[0] * self.scale_factor - 3), int(point[1] * self.scale_factor - 3), 6, 6)
                        rect2 = (int(point[0] * self.scale_factor - 1), int(point[1] * self.scale_factor - 1), 2, 2)
                        self.pixbuf.draw_rectangle(widget.get_style().black_gc, True,
                                                   rect[0], rect[1], rect[2], rect[3])
                        self.drawing_area.queue_draw_area(rect[0], rect[1], rect[2], rect[3])
                        self.pixbuf.draw_rectangle(widget.get_style().white_gc, True,
                                                   rect2[0], rect2[1], rect2[2], rect2[3])
                        self.drawing_area.queue_draw_area(rect2[0], rect2[1], rect2[2], rect2[3])
            elif event.keyval == Gdk.KEY_F1:
                self.show_help()
            elif event.keyval == Gdk.KEY_Delete:
                self.delete_page()
            elif event.keyval in (Gdk.KEY_F8, Gdk.KEY_F, Gdk.KEY_f):
                self.frames_detection()
            elif event.keyval in (Gdk.KEY_F7, Gdk.KEY_T, Gdk.KEY_t):
                self.text_bubble_detection_cursor()
            elif event.keyval == Gdk.KEY_F5:
                self.drawing_area.queue_draw()
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
                    self.pages_tree.set_cursor((path[0] + 1,), focus_column, False)
                else:
                    self.pages_tree.set_cursor((path[0], path[1] + 1), focus_column, False)

                (new_path, focus_column) = self.pages_tree.get_cursor()
                if new_path == None:
                    self.pages_tree.set_cursor((path[0] + 1,), focus_column, False)

                (final_path, focus_column) = self.pages_tree.get_cursor()
                if final_path == None:
                    self.pages_tree.set_cursor(path, focus_column, False)
            elif event.keyval == Gdk.KEY_Up:
                (path, focus_column) = self.pages_tree.get_cursor()
                if len(path) == 1 and path[0] == 0:
                    return True
                elif len(path) == 1:
                    self.pages_tree.set_cursor((path[0] - 1,), focus_column, False)
                elif path[1] > 0:
                    self.pages_tree.set_cursor((path[0], path[1] - 1), focus_column, False)
                else:
                    self.pages_tree.set_cursor((path[0],), focus_column, False)

                (final_path, focus_column) = self.pages_tree.get_cursor()
                if final_path == None:
                    self.pages_tree.set_cursor(path, focus_column, False)

        return True

    def set_cursor_loading(self, *args):
        '''loading_cursor = Gdk.Cursor.new_from_name("wait")

        try:
            self.window.getparent().set_cursor(loading_cursor)
        except Exception as e:
            print(type(loading_cursor))
            print(f"Error setting cursor: {e}")
        while Gtk.events_pending():
            Gtk.main_iteration()'''
        pass

    def show_help(self, *args):
        dialog = Gtk.Window()
        dialog.set_title("Help")
        dialog.set_geometry_hints(min_height=230)
        dialog.set_resizable(False)

        # Shortcuts
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label()
        label.set_markup('<b>Shortcuts</b>')
        hbox.append(label)
        dialog.set_child(hbox)

        # left side
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("help")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('This help window (F1)')
        hbox.append(label)
        left_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("copy")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Copy Frames/Text-Layer (CTRL + C)')
        hbox.append(label)
        left_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("ok")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Enclose Rectangle (ENTER, right click)')
        hbox.append(label)
        left_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("ctrl")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Draw straight line by holding down Control key')
        hbox.append(label)
        left_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("F5")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Refresh image (F5)')
        hbox.append(label)
        left_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("F8")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Detect Frames (F8 or "F" key)')
        hbox.append(label)
        left_vbox.append(hbox)

        main_hbox.append(left_vbox)

        # right side
        right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("del")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Delete current page (DEL)')
        hbox.append(label)
        right_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("paste")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Paste Frames/Text-Layer (CTRL + V)')
        hbox.append(label)
        right_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("stop")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Cancel Drawing Rectangle (ESC)')
        hbox.append(label)
        right_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("BKSP")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Remove Last Point (BackSpace)')
        hbox.append(label)
        right_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("F7")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Detect Bubble at cursor (F7 or "T" key)')
        hbox.append(label)
        right_vbox.append(hbox)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button = Gtk.Button.new_with_label("F11")
        hbox.append(button)
        label = Gtk.Label()
        label.set_markup('Hide bottom and side bars (F11 or "H" key)')
        hbox.append(label)
        right_vbox.append(hbox)

        main_hbox.append(right_vbox)

        dialog.vbox.append(main_hbox)
        #dialog.get_action_area().get_children()[0].grab_focus()

        # show it
        #dialog.show_all()
        dialog.present()
        '''if dialog != None:
            dialog.destroy()'''

        return

    def delete_page(self, *args):
        if self.get_current_page_number() <= 1:
            return False

        message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.YES_NO,
                                    message_format="Are you sure you want to remove this page?")
        response = message.run()
        message.destroy()

        if response != Gtk.ResponseType.YES:
            return False

        for page in self.parent.acbf_document.tree.findall("body/page"):
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                self.parent.acbf_document.tree.find("body").remove(page)
                in_path = os.path.join(self.parent.tempdir, page.find("image").get("href").replace("\\", "/"))
                if os.path.isfile(in_path):
                    os.remove(in_path)

        for image in self.parent.acbf_document.tree.findall("data/binary"):
            if image.get("id") == self.selected_page[1:]:
                self.parent.acbf_document.tree.find("data").remove(image)

        self.parent.acbf_document.pages = self.parent.acbf_document.tree.findall("body/" + "page")

        self.pages_tree.get_selection().get_selected()[0].remove(self.pages_tree.get_selection().get_selected()[1])
        self.pages_tree.set_cursor((0, 0))
        self.pages_tree.grab_focus()
        #self.draw_page_image()

        self.set_modified()

    def set_modified(self, modified: bool = True):
        self.is_modified = modified
        self.set_header_title()
        self.drawing_area.queue_draw()

    def change_zoom(self, *args):
        self.scale_factor = float(self.zoom_dropdown.get_selected_item().get_string()[0:-1]) / 100
        self.drawing_area.queue_draw()

    def change_layer(self, *args):
        self.load_texts()
        self.drawing_area.queue_draw()

    def tab_change(self, notebook: Gtk.Notebook, page, page_num, *args):
        if page_num == 1:
            self.drawing_frames = True
            self.drawing_texts = False
            self.drawing_area.set_cursor_from_name("crosshair")
        elif page_num == 2:
            self.drawing_frames = False
            self.drawing_texts = True
            self.drawing_area.set_cursor_from_name("crosshair")
        else:
            self.drawing_frames = False
            self.drawing_texts = False
            self.drawing_area.set_cursor_from_name("default")

    def load_general(self, *args):
        # main bg_color
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label = Gtk.Label()
        label.set_markup('Main Background Color: ')
        hbox.append(label)

        color = Gdk.RGBA()
        color.parse(self.parent.acbf_document.bg_color)

        color_button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        color_button.set_rgba(color)
        #color_button.set_foreground_color(color)
        #color_button.set_title('Select Color')
        color_button.connect("notify::rgba", self.set_body_bgcolor)
        hbox.append(color_button)
        self.general_box.append(hbox)

        # page bg_color
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label = Gtk.Label()
        label.set_markup('Page Background Color: ')
        hbox.append(label)

        color = Gdk.RGBA()
        try:
            color.parse(self.selected_page_bgcolor)
        except:
            color.parse(self.parent.acbf_document.bg_color)
        self.page_color_button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        self.page_color_button.set_rgba(color)
        #self.page_color_button.set_title('Select Color')
        self.page_color_button.connect("notify::rgba", self.set_page_bgcolor)
        hbox.append(self.page_color_button)
        self.general_box.append(hbox)

        # transition
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label = Gtk.Label()
        label.set_markup('Page Transition: ')
        hbox.append(label)

        #self.transition_dropdown.connect("notify::selected", self.page_transition_changed)

        hbox.append(self.transition_dropdown)
        self.update_page_transition()
        self.general_box.append(hbox)

    def update_page_transition(self):
        current_trans = self.parent.acbf_document.get_page_transition(self.get_current_page_number())
        if current_trans is None:
            self.transition_dropdown.set_selected(0)
            #self.transition_dropdown.set_sensitive(False)
        else:
            self.transition_dropdown.set_sensitive(True)
            position: int = 0
            i = 0
            while i < 99:
                string = self.transition_dropdown_model.get_item(i)
                if string is None:
                    break

                if string.get_string().lower().replace(" ", "_") == current_trans:
                    position = i

                i += 1

            self.transition_dropdown.set_selected(position)

    def page_transition_changed(self, widget: Gtk.DropDown, _pspec):
        transition = widget.get_selected_item().get_string()
        active = widget.get_sensitive()
        if active:
            for page in self.parent.acbf_document.pages:
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    page.attrib["transition"] = transition.lower().replace(' ', '_')
            self.set_modified()

    def set_body_bgcolor(self, widget, _pspec=None):
        colour: Gdk.RGBA = widget.get_rgba()
        self.parent.acbf_document.tree.find("body").attrib["bgcolor"] = self.rgb_to_hex(colour.to_string())
        self.parent.modified()

    def get_hex_color(self, widget):
        color_string = widget.get_color().to_string()
        if len(color_string) == 13:
            color = '#' + color_string[1:3] + color_string[5:7] + color_string[9:11]
            return color
        else:
            return color_string

    def rgb_to_hex(self, rgb_string: str) -> str:
        """Converts an rgb or rgba string to a hexadecimal color string."""
        # Remove 'rgb(' and ')'
        rgb_string = rgb_string.strip('rgb()')
        # Split the string into components
        rgb_values = [int(x) for x in rgb_string.split(',')]
        # Convert to hex
        hex_values = [hex(x)[2:].zfill(2) for x in rgb_values]
        # Format the output
        hex_color = '#' + ''.join(hex_values)
        return hex_color

    def set_page_bgcolor(self, widget, _pspec=None):
        colour: Gdk.RGBA = widget.get_rgba()
        self.selected_page_bgcolor = self.rgb_to_hex(colour.to_string())
        self.set_modified()

    def load_frames(self, *args) -> None:
        # Don't trigger a change so as not to mark as modified
        self.frame_model.disconnect_by_func(self.list_item_changed)
        # Clear previous frames
        self.frame_model.remove_all()

        current_page_number = self.get_current_page_number()
        frames = self.parent.acbf_document.load_page_frames(current_page_number)

        for frame in frames:
            self.frame_model.append(FrameItem(frame[0], frame[1]))

        self.frame_model.connect("items_changed", self.list_item_changed)

    def draw_frames(self) -> cairo.Surface:
        width = self.drawing_area.get_content_width()
        height = self.drawing_area.get_content_height()

        # Create a Cairo ImageSurface to draw frames on
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)

        # Draw frames
        i = -1
        while i < 9999:
            i = i + 1
            frame: FrameItem = self.frame_model.get_item(i)
            if frame is None:
                break

            # Prepare drawing data
            polygon = self.scale_polygon(frame.cords)
            anchor = self.left_anochor_for_polygon(frame.cords)
            label_text = f'<span foreground="blue" background="white" size="{self.scale_factor * 150}%"><b><big>{i + 1}</big></b></span>'

            # Set the color for the polygon
            cr.set_source_rgba(self.frames_color.red, self.frames_color.green, self.frames_color.blue,
                               self.frames_color.alpha)

            cr.set_dash([5])
            cr.set_line_width(2)

            # Draw the polygon
            cr.move_to(polygon[0][0], polygon[0][1])
            for point in polygon[1:]:
                cr.line_to(point[0], point[1])
            cr.close_path()
            cr.stroke()

            # Create Pango layout for the text
            layout = PangoCairo.create_layout(cr)
            layout.set_markup(label_text)

            # Calculate position for the text
            x, y = anchor
            x_move = -10 if x >= 10 else 0
            y_move = -10 if y >= 10 else 0
            x = int(x * self.scale_factor) + x_move
            y = int(y * self.scale_factor) + y_move

            # Draw the text
            cr.move_to(x, y)
            PangoCairo.show_layout(cr, layout)

        return surface

    '''def load_frames(self, *args):
        for i in self.frames_box.get_children():
            i.destroy()
        for idx, frame in enumerate(self.parent.acbf_document.load_page_frames(self.get_current_page_number())):
            if self.get_current_page_number() > 1:
                self.add_frames_hbox(None, frame[0], frame[1], idx + 1)
                self.pixbuf.draw_polygon(self.frames_gc, False, self.scale_polygon(frame[0]))
                self.pangolayout = self.drawing_area.create_pango_layout("")
                self.pangolayout.set_markup(
                    '<span foreground="blue" background="white"><b><big> ' + str(idx + 1) + ' </big></b></span>')

                anchor = self.left_anochor_for_polygon(frame[0])
                if anchor[0] < 10:
                    x_move = 0
                else:
                    x_move = -10
                if anchor[1] < 10:
                    y_move = 0
                else:
                    y_move = -10
                self.pixbuf.draw_layout(self.frames_gc, int(anchor[0] * self.scale_factor) + x_move,
                                        int(anchor[1] * self.scale_factor) + y_move, self.pangolayout)'''

    def scale_polygon(self, polygon, *args):
        polygon_out = []
        for point in polygon:
            polygon_out.append((int(point[0] * self.scale_factor), int(point[1] * self.scale_factor)))
        return polygon_out

    '''def add_frames_hbox(self, widget, polygon, bg_color, frame_number):
        #self.frame_model.append(FrameItem(frame_number, polygon, bg_color))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # frame number
        label = Gtk.Label()
        label.set_markup('<span foreground="blue"><b><big>' + str(frame_number).rjust(3) + ' </big></b></span>')
        hbox.append(label)

        # up button
        up_button = Gtk.Button.new_with_label("up")
        if frame_number > 1:
            up_button.set_tooltip_text('Move Up')
            up_button.connect("clicked", self.move_frame_up, polygon)
        else:
            up_button.set_sensitive(False)
        hbox.append(up_button)

        # coordinates
        entry = Gtk.Entry()
        entry.set_text(str(polygon))
        entry.type = 'polygon'
        entry.set_tooltip_text('Frames Polygon')
        entry.set_sensitive(False)
        hbox.append(entry)

        # bg color
        if bg_color == None and self.selected_page_bgcolor == None:
            bg_color = self.parent.acbf_document.bg_color
        elif bg_color == None:
            bg_color = self.selected_page_bgcolor

        color = Gdk.RGBA()
        color.parse(bg_color)
        color_button = Gtk.ColorButton.new_with_rgba(color)
        color_button.set_title('Frame Background Color')
        color_button.connect("activate", self.set_frame_bgcolor, polygon)
        hbox.append(color_button)

        # remove button
        remove_button = Gtk.Button.new_with_label("del")
        remove_button.connect("clicked", self.remove_frame, hbox, polygon)
        hbox.append(remove_button)

        hbox.show()
        #entry.grab_focus()

        self.frames_box.append(hbox)
        self.frames_box.show()
        return'''

    '''def remove_frame(self, widget, hbox, polygon):
        message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.YES_NO,
                                    message_format="Are you sure you want to remove the frame?")
        response = message.run()
        message.destroy()

        if response != Gtk.ResponseType.YES:
            return False

        for page in self.parent.acbf_document.pages:
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
        #self.draw_page_image()'''

    '''def remove_hbox(self, widget, hbox):
        hbox.destroy()
        return'''

    def set_frame_bgcolor(self, widget, polygon):
        # override to ColorSelectionDialog (to make it non-modal in order to pick color from other window with eyedropper)
        for i in Gtk.window_list_toplevels():
            if i.get_name() == 'GtkColorSelectionDialog':
                i.hide_all()
                i.destroy()
                my_dialog = ColorDialog(self, widget.get_color(), False, 'false')
                response = my_dialog.run()
                if response == Gtk.ResponseType.OK:
                    widget.set_color(my_dialog.get_color_selection().get_current_color())
                    for page in self.parent.acbf_document.pages:
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

    '''def move_frame_up(self, widget, polygon):
        for page in self.parent.acbf_document.pages:
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
        self.drawing_area.queue_draw()'''

    def load_texts(self, *args) -> None:
        try:
            self.text_layer_model.disconnect_by_func(self.list_text_item_changed)
        except:
            pass

        # Clear previous text areas
        self.text_layer_model.remove_all()

        current_page_number = self.get_current_page_number()
        current_lang = self.layer_dropdown.get_selected_item()
        if current_lang is not None and current_lang.show:
            texts, refs = self.parent.acbf_document.load_page_texts(current_page_number, current_lang.lang_iso)
        else:
            return
        # Load texts
        for text_areas in texts:
            self.text_layer_model.append(
                TextLayerItem(polygon=text_areas[0], text=text_areas[1], colour=text_areas[2], rotation=text_areas[3],
                              type=text_areas[4], is_inverted=text_areas[5], is_transparent=text_areas[6],
                              references=refs))

        self.text_layer_model.connect("items_changed", self.list_text_item_changed)

    def draw_texts(self) -> cairo.Surface:
        """Draws around the text boxes and the numbers next to the text boxes not the actual text"""
        width = self.drawing_area.get_content_width()
        height = self.drawing_area.get_content_height()
        # Create a Cairo ImageSurface to draw text on
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)

        current_page_number = self.get_current_page_number()

        i = -1
        while i < 9999:
            i = i + 1
            text_area: TextLayerItem = self.text_layer_model.get_item(i)
            if text_area is None:
                break
            # Prepare drawing data
            polygon = self.scale_polygon(text_area.polygon)
            label_text = f'<span foreground="red" background="white" size="{self.scale_factor * 125}%"><b>{i + 1}</b></span>'

            # Set the color for the polygon
            cr.set_source_rgba(self.text_layers_color.red, self.text_layers_color.green, self.text_layers_color.blue,
                               self.text_layers_color.alpha)
            cr.set_line_width(2)

            # Draw the polygon
            cr.move_to(polygon[0][0], polygon[0][1])
            for point in polygon[1:]:
                cr.line_to(point[0], point[1])
            cr.close_path()
            cr.stroke()

            # Create Pango layout for the text
            layout = PangoCairo.create_layout(cr)
            layout.set_markup(label_text)

            # Calculate position for the text
            min_x = min(text_area.polygon, key=lambda item: item[0])[0]
            min_y = min(text_area.polygon, key=lambda item: item[1])[1]
            x = int(min_x * self.scale_factor) - 5
            y = int(min_y * self.scale_factor) - 5

            # Draw the text
            cr.move_to(x, y)
            PangoCairo.show_layout(cr, layout)

        return surface

    '''def load_texts(self, *args):
        for i in self.texts_box.get_children():
            i.destroy()
        for lang in self.parent.acbf_document.languages:
            if lang[1] != 'FALSE':
                for idx, text_areas in enumerate(
                        self.parent.acbf_document.load_page_texts(self.get_current_page_number(), lang[0])[0]):
                    self.add_texts_hbox(None, text_areas[0], text_areas[1], text_areas[2], text_areas[4], text_areas[5],
                                        idx + 1, text_areas[6])
                    self.pixbuf.draw_polygon(self.text_layers_gc, False, self.scale_polygon(text_areas[0]))
                    self.pangolayout = self.drawing_area.create_pango_layout("")
                    self.pangolayout.set_markup(
                        '<span foreground="red" background="white"><b> ' + str(idx + 1) + ' </b></span>')
                    min_x = min(text_areas[0], key=lambda item: item[0])[0]
                    min_y = min(text_areas[0], key=lambda item: item[1])[1]
                    self.pixbuf.draw_layout(self.text_layers_gc, int(min_x * self.scale_factor) - 5,
                                            int(min_y * self.scale_factor) - 5, self.pangolayout)
                break'''

    '''def add_texts_hbox(self, widget, polygon, text, bg_color, area_type, inverted, area_number, is_transparent):
        # self.text_layer_model.append(TexyLayerItem(area_number, text, bg_color, area_type))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        # text-area number
        label = Gtk.Label()
        label.set_markup('<span foreground="red"><b><big>' + str(area_number).rjust(3) + ' </big></b></span>')
        hbox.append(label)

        # up button
        up_button = Gtk.Button.new_with_label("up")
        if area_number > 1:
            up_button.set_tooltip_text('Move Up')
            up_button.connect("clicked", self.move_text_up, polygon)
        else:
            up_button.set_sensitive(False)
        hbox.append(up_button)

        # text
        entry = Gtk.Entry()
        entry.set_text(unescape(text).replace('<BR>', ''))
        entry.type = 'polygon'
        entry.set_sensitive(False)
        hbox.append(entry)

        # Edit text
        button = Gtk.Button.new_with_label("i")
        #button.get_children()[0].get_children()[0].get_children()[1].set_text(' ...')
        button.connect("clicked", self.edit_texts, polygon, bg_color)
        button.type = 'texts_edit'
        button.set_tooltip_text('Edit Text Areas')
        hbox.append(button)

        # bg color
        if bg_color == None and self.selected_page_bgcolor == None:
            bg_color = self.parent.acbf_document.bg_color
        elif bg_color == None:
            bg_color = self.selected_page_bgcolor

        color = Gdk.RGBA()
        color.parse(bg_color)
        color_button = Gtk.ColorButton.new_with_rgba(color)
        if is_transparent:
            color_button.set_use_alpha(True)
            color_button.set_alpha(0)
        color_button.set_tooltip_text('Text Area Background Color')
        color_button.connect("activate", self.set_text_bgcolor, polygon)
        hbox.append(color_button)

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
        label = Gtk.Label()
        label.set_markup('<tt> <b>' + area_type + '</b> </tt>')
        hbox.append(label)

        # remove button
        remove_button = Gtk.Button.new_with_label("del")
        remove_button.connect("clicked", self.remove_text, hbox, polygon)
        hbox.append(remove_button)

        #hbox.show()
        entry.grab_focus()

        self.texts_box.append(hbox)
        #self.texts_box.show()
        return'''

    def set_text_bgcolor(self, widget, polygon):
        # override to ColorSelectionDialog (to make it non-modal in order to pick color from other window with eyedropper)
        for i in Gtk.window_list_toplevels():
            if i.get_name() == 'GtkColorSelectionDialog':
                i.hide_all()
                i.destroy()

                # get transparency value
                is_transparent = 'false'
                for page in self.parent.acbf_document.pages:
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
                if response == Gtk.ResponseType.OK:
                    if my_dialog.transparency_button.get_active():
                        widget.set_use_alpha(True)
                        widget.set_alpha(0)
                    else:
                        widget.set_use_alpha(False)
                        widget.set_color(my_dialog.get_color_selection().get_current_color())
                    for page in self.parent.acbf_document.pages:
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
        for page in self.parent.acbf_document.pages:
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
        self.drawing_area.queue_draw()
        #self.draw_page_image()

    '''def remove_text(self, widget, hbox, polygon):
        message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.YES_NO,
                                    message_format="Are you sure you want to remove the text area?")
        response = message.run()
        message.destroy()

        if response != Gtk.ResponseType.YES:
            return False

        for page in self.parent.acbf_document.pages:
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                xml_frame = ''
                for point in polygon:
                    xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
                for text_layer in page.findall("text-layer"):
                    for text_area in text_layer.findall("text-area"):
                        if text_area.get("points") == xml_frame.strip():
                            text_layer.remove(text_area)
        self.set_modified()
        self.load_texts()
        #self.draw_page_image()'''

    def edit_texts(self, widget: Gtk.Button, pos: Gtk.EntryIconPosition, position: int):
        dialog = TextBoxDialog(self, position)
        dialog.present()

    '''def save_edit_text_box(self, widget: Gtk.Button, text_layer: TextLayerItem, edit_data: dict) -> None:
        for page in self.parent.acbf_document.pages:
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                for xml_text_layer in page.findall("text-layer"):
                    for text_area in xml_text_layer:
                        if str(text_layer.polygon).replace("[", "").replace(")]", "").replace("(", "").replace("),", "").replace(", ", ",") == str(text_area.get("points")):
                            if edit_data["text_rotation"].get_value() > 0:
                                text_area.attrib["text-rotation"] = str(int(edit_data["text_rotation"].get_value()))
                            else:
                                text_area.attrib.pop("text-rotation", None)
                            if edit_data["type_dropdown"].get_active() != 0:
                                text_area.attrib["type"] = edit_data["type_dropdown"].get_selected_item().to_string().lower()
                            else:
                                text_area.attrib.pop("type", None)
                            if edit_data["inverted_button"].get_active():
                                text_area.attrib["inverted"] = "true"
                            else:
                                text_area.attrib.pop("inverted", None)
                    if xml_text_layer.get("lang") == edit_data["lang"]:
                        for text_area in xml_text_layer:
                            if str(text_layer.polygon).replace("[", "").replace(")]", "").replace("(", "").replace("),", "").replace(", ", ",") == str(text_area.get("points")):
                                for p in text_area.findall("p"):
                                    text_area.remove(p)

                                text_box: Gtk.TextBuffer = edit_data["text_box"].get_buffer().get_text(
                                    edit_data["text_box"].get_buffer().get_bounds()[0],
                                    edit_data["text_box"].get_buffer().get_bounds()[1],
                                    False)

                                for text in text_box.split('\n'):
                                    element = xml.SubElement(text_area, "p")

                                    tag_tail = None
                                    for word in text.strip(" ").split("<"):
                                        if re.sub("[^\/]*>.*", "", word) == "":
                                            tag_name = re.sub(">.*", "", word)
                                            tag_text = re.sub("[^>]*>", "", word)
                                        elif ">" in word:
                                            tag_tail = re.sub("/[^>]*>", "", word)
                                        else:
                                            element.text = str(word)

                                        if tag_tail is not None:
                                            if " " in tag_name:
                                                tag_attr = tag_name.split(" ")[1].split("=")[0]
                                                tag_value = tag_name.split(" ")[1].split("=")[1].strip('"')
                                                tag_name = tag_name.split(" ")[0]
                                                sub_element = xml.SubElement(element, tag_name)
                                                sub_element.attrib[tag_attr] = tag_value
                                                sub_element.text = str(tag_text)
                                                sub_element.tail = str(tag_tail)
                                            else:
                                                sub_element = xml.SubElement(element, tag_name)
                                                sub_element.text = str(tag_text)
                                                sub_element.tail = str(tag_tail)

                                            tag_tail = None
        self.close()'''

    def draw_func(self, widget: Gtk.DrawingArea, cr: Gdk.CairoContext, w: int, h: int) -> None:
        try:
            image_surface = self.draw_page_image()
            text_surface = self.draw_texts()
            frame_surface = self.draw_frames()

            # Merge image, frames and text surfaces
            cr.set_source_surface(image_surface)
            cr.paint()
            cr.set_source_surface(frame_surface)
            cr.paint()
            cr.set_source_surface(text_surface)
            cr.paint()

            points_len = len(self.points)
            if points_len > 0:
                cr.set_source_rgb(0, 0, 0)
                cr.set_line_width(1)
                for point in self.points:
                    cr.rectangle(point[0] - 3, point[1] - 3, 6, 6)
                    cr.stroke()

            # Draw connecting line
            if points_len > 1:
                cr.set_source_rgb(0.2, 0.2, 0.2)
                cr.set_line_width(1)
                for point in self.points:
                    cr.line_to(point[0], point[1])
                cr.stroke()

        except Exception as e:
            logger.error("Failed to paint window: %s", e)

    def get_current_page_number(self, *args):
        for idx, page in enumerate(self.parent.acbf_document.pages):
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                ret_idx = idx + 2
                break
        else:
            ret_idx = 1
        return ret_idx

    def draw_page_image(self) -> cairo.Surface:
        #self.set_cursor_loading()
        '''if self.selected_page[:4] == 'Root':
            self.selected_page = self.selected_page[5:].replace("\\", "/")'''

        lang = self.layer_dropdown.get_selected_item()
        if lang is not None and lang.show:
            current_page_image = os.path.join(self.parent.tempdir, self.selected_page)
            i = 0
            while i < 999:
                lang = self.parent.lang_store.get_item(i)
                if lang is None:
                    break
                if lang.lang_iso == self.layer_dropdown.get_selected_item().lang_iso:
                    # This draws the text in the text boxes
                    xx = text_layer.TextLayer(current_page_image, self.get_current_page_number(),
                                              self.parent.acbf_document, i, self.text_layer_model, self.frame_model)
                    img = xx.PILBackgroundImage

                i = i + 1
        else:
            img, bg_color = self.parent.acbf_document.load_page_image(self.get_current_page_number())

        if self.scale_factor != 1:
            img = img.resize((int(img.size[0] * self.scale_factor), int(img.size[1] * self.scale_factor)),
                             Image.Resampling.BICUBIC)

        '''if (i.mode in ('RGBA', 'LA') or (i.mode == 'P' and 'transparency' in i.info)) and self.selected_page[-4:].upper() != '.GIF' and len(i.split()) > 2:
            color = (0, 0, 0)
            background = Image.new('RGB', i.size, color)
            background.paste(i, mask=i.split()[3])
            try:
                imagestr = background.tostring()
            except:
                imagestr = background.tobytes()
        elif i.mode != 'RGB':
            bg = Image.new("RGB", i.size, (255, 255, 255))
            bg.paste(i, (0, 0))
            try:
              imagestr = bg.tostring()
            except:
              imagestr = bg.tobytes()
        else:
            try:
              imagestr = i.tostring()
            except:
              imagestr = i.tobytes()

        data = i.tobytes()'''
        w, h = img.size

        # TODO Need to create a solid background if transparent?
        image = img.convert("RGBA")
        rgba_data = image.tobytes()
        # Convert RGBA to ARGB (BGRA for little-endian)
        argb_data = bytearray()
        for i in range(0, len(rgba_data), 4):
            r = rgba_data[i]
            g = rgba_data[i + 1]
            b = rgba_data[i + 2]
            a = rgba_data[i + 3]
            argb_data.extend([b, g, r, a])

        surface = cairo.ImageSurface.create_for_data(argb_data, cairo.FORMAT_ARGB32, w, h, w * 4)

        self.drawing_area.set_content_height(h)
        self.drawing_area.set_content_width(w)
        #self.pixbuf = GdkPixbuf.Pixbuf.new_from_data(data, GdkPixbuf.Colorspace.RGB, False, 8, w, h, w * 3)

        #surface = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h)
        #return cairo.Context(surface)

        return surface

    def scrollparent(self, button, event, *args):
        if event.direction == Gdk.ScrollDirection.DOWN and event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            current_value = self.sw_image.get_hadjustment().value
            step = self.sw_image.get_hadjustment().get_step_increment()
            maximum = self.sw_image.get_hadjustment().get_upper() - self.sw_image.get_hadjustment().get_page_size()
            if current_value + step > maximum:
                self.sw_image.get_hadjustment().set_value(maximum)
            else:
                self.sw_image.get_hadjustment().set_value(current_value + step)
            return True
        elif event.direction == Gdk.ScrollDirection.UP and event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            current_value = self.sw_image.get_hadjustment().value
            step = self.sw_image.get_hadjustment().get_step_increment()
            if current_value - step < 0:
                self.sw_image.get_hadjustment().set_value(0)
            else:
                self.sw_image.get_hadjustment().set_value(current_value - step)
            return True
        return

    def draw_brush(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> bool:
        # No boxes allowed on cover (for some reason)
        if self.get_current_page_number() == 1:
            return True

        # Must be in frames or texts notebook tab
        if not self.drawing_frames and not self.drawing_texts:
            return False

        if self.detecting_bubble:
            try:
                self.text_bubble_detection(x, y)
            except:
                message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                            message_format="Failed to detect text area.")
                response = message.run()
                message.destroy()
            self.detecting_bubble = False
            # self.window.set_cursor(None)
            return False

        # Close current points if double or right-click
        if n_press > 1 or gesture.get_current_button() == 3:
            self.enclose_rectangle()
            return True

        # TODO More tools Old comment: draw vertical/horizontal line with CTRL key pressed
        '''if self.straight_button.get_active() and len(self.points) > 0:
            if abs(x / self.scale_factor - self.points[-1][0]) > abs(y / self.scale_factor - self.points[-1][1]):
                y = float(self.points[-1][1]) * self.scale_factor
            else:
                x = float(self.points[-1][0]) * self.scale_factor'''

        lang_found = False
        for lang in self.parent.acbf_document.languages:
            if lang[1] == 'TRUE':
                lang_found = True
        if self.drawing_texts and not lang_found:
            # TODO alert
            print("Can't draw text areas. No languages are defined for this comic book with 'show' attribute checked.")
            '''message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Can't draw text areas. No languages are defined for this comic book with 'show' attribute checked.")
            response = message.run()
            message.destroy()
            return'''

        if ((len(self.points) > 0) and
                (x > self.points[0][0] - 5 and x < self.points[0][0] + 5) and
                (y > self.points[0][1] - 5 and y < self.points[0][1] + 5)):
            if len(self.points) > 2:
                self.enclose_rectangle()
            else:
                self.points.append((int(x / self.scale_factor), int(y / self.scale_factor)))
        else:
            self.points.append((int(x / self.scale_factor), int(y / self.scale_factor)))

        # Trigger redraw
        self.drawing_area.queue_draw()

        return True

    def cancel_rectangle(self, *args):
        self.drawing_area.queue_draw()
        self.points = []

    def enclose_rectangle(self, color="#ffffff", *args):
        if len(self.points) > 2:
            xml_frame = ''
            for point in self.points:
                xml_frame = xml_frame + str(point[0]) + ',' + str(point[1]) + ' '
            for page in self.parent.acbf_document.pages:
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    if self.drawing_frames:
                        # add frame
                        element = xml.SubElement(page, "frame", points=xml_frame.strip())
                        self.load_frames()
                        self.set_modified()

                    elif self.drawing_texts:
                        # add text-area
                        for lang in self.parent.acbf_document.languages:
                            if lang[1] == 'TRUE':
                                layer_found = False
                                for layer in page.findall("text-layer"):
                                    if layer.get("lang") == lang[0]:
                                        layer_found = True
                                        area = xml.SubElement(layer, "text-area", points=xml_frame.strip(),
                                                              bgcolor=str(color))
                                        par = xml.SubElement(area, "p")
                                        par.text = '...'
                                if not layer_found:
                                    layer = xml.SubElement(page, "text-layer", lang=lang[0])
                                    area = xml.SubElement(layer, "text-area", points=xml_frame.strip(),
                                                          bgcolor=str(color))
                                    par = xml.SubElement(area, "p")
                                    par.text = '...'
                        self.load_texts()
                        self.set_modified()
                        # self.pixmap.draw_polygon(self.text_layers_gc, False, self.scale_polygon(self.points))

            #self.draw_drawable()
            self.points = []
            # Trigger redraw
            self.drawing_area.queue_draw()

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
        current_page_image = os.path.join(self.parent.tempdir, self.selected_page)
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

        imgray = cv2.GaussianBlur(rgb, (5, 5), 0)
        imgray = cv2.cvtColor(imgray, cv2.COLOR_BGR2GRAY)
        imgray = cv2.copyMakeBorder(imgray, 6, 6, 6, 6, cv2.BORDER_CONSTANT, 0)
        height, width = imgray.shape[:2]
        border = int(float((min(height, width))) * 0.008)
        if border < 2:
            border = 2
        # cv2.imshow("im", imgray)

        # get point color and range
        px = imgray[y + 6, x + 6]
        px_color = rgb[y, x]
        low_color = max(0, px - 30)
        high_color = min(255, px + 30)

        # threshold image on selected color
        thresholded = cv2.inRange(imgray, low_color, high_color)
        # cv2.imshow("threshold", thresholded)

        # floodfil with gray
        mask = numpy.zeros((height + 2, width + 2), numpy.uint8)
        cv2.floodFill(thresholded, mask, (x + 7, y + 7), 100)
        mask = cv2.inRange(thresholded, 99, 101)
        # cv2.circle(mask, (x + 7, y + 7), 2, 200)
        # cv2.imshow("flood", mask)

        # remove holes and narrow lines
        """self.text_bubble_fill_inside(mask, 0.1, True)
        #cv2.imshow("close1", mask)
        mask = numpy.rot90(mask, 1)
        self.text_bubble_fill_inside(mask, 0.08, True)
        mask = numpy.rot90(mask, 3)
        #cv2.imshow("close2", mask)"""

        # carve out the bubble first
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

        if (numpy.count_nonzero(check) / float(check.size)) > 0.9:
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
                # cv2.imshow("B" + str(angle), mask)
                self.text_bubble_cut_tails(mask, 0.15)
                mask = self.rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
                # cv2.imshow("C" + str(angle), mask)
        rhi, rwi = mask.shape
        mask = mask[int((rhi - hi) / 2) - 10:int((rhi - hi) / 2) + hi + 10,
               int((rwi - wi) / 2) - 10:int((rwi - wi) / 2) + wi + 10]

        # remove text
        self.text_bubble_fill_inside(mask, 0.08)
        mask = numpy.rot90(mask, 1)
        self.text_bubble_fill_inside(mask, 0.08)
        mask = numpy.rot90(mask, 1)

        # check if top/bottom is straight line
        if numpy.count_nonzero(mask[11]) / float(mask[11].size) > 0.5:
            is_cut_at_top = True
        else:
            is_cut_at_top = False

        if numpy.count_nonzero(mask[-12]) / float(mask[-12].size) > 0.5:
            is_cut_at_bottom = True
        else:
            is_cut_at_bottom = False

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border, border))
        mask = cv2.erode(mask, kernel, iterations=1)

        # edges
        mask = cv2.Canny(mask, 10, 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(border / 2), int(border / 2)))
        mask = cv2.dilate(mask, kernel, iterations=1)
        # cv2.imshow("edg", mask)

        # find contours
        i = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        try:
            contours, h = i[1], i[2]
        except:
            contours, h = i[0], i[1]

        if len(contours) == 0:
            raise

        contours.sort(key=lambda x: cv2.contourArea(x), reverse=True)
        arc_len = cv2.arcLength(contours[0], True)
        approx = cv2.approxPolyDP(contours[0], 0.003 * arc_len, True)
        self.points = []

        # move due to mask and image border added earlier + bubble carve out
        for point in approx.tolist():
            x = point[0][0] - 6 + min_x - 11
            y = point[0][1] - 6 + min_y - 10
            self.points.append((x, y))

        # cut top and bottom of the bubble (helps text-fitting algorithm)
        cut_by = 1 + round(height * 0.001, 0)
        min_y = min(self.points, key=lambda item: item[1])[1]
        max_y = max(self.points, key=lambda item: item[1])[1]
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
            points_on_line_upper_max_x = max(points_on_line_upper, key=lambda x: x[0])
            points_on_line_upper_min_x = min(points_on_line_upper, key=lambda x: x[0])
            points_on_line_lower_max_x = max(points_on_line_lower, key=lambda x: x[0])
            points_on_line_lower_min_x = min(points_on_line_lower, key=lambda x: x[0])

            self.points = []
            for point in new_points:
                if point in (points_on_line_upper_max_x, points_on_line_upper_min_x, points_on_line_lower_max_x,
                             points_on_line_lower_min_x):
                    self.points.append(point)
                elif point not in points_on_line_upper and point not in points_on_line_lower:
                    self.points.append(point)
        except:
            self.points = new_points

        # print len(self.points)

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
        bubble_width = max(values, key=lambda item: item[2])[2]

        for idx, line in enumerate(mask):
            if idx in zero_these and zero_these[idx][2] < bubble_width * narrow_by:  # remove narrow lines
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
        bubble_width = max(values, key=lambda item: item[2])[2]

        for idx, line in enumerate(mask):
            if idx in zero_these:  # remove inside holes
                mask[idx][zero_these[idx][0]:zero_these[idx][1]] = 255
        return mask

    def text_bubble_detection_cursor(self, *args):
        if self.get_current_page_number() == 1:
            return
        if not self.drawing_texts:
            self.notebook.set_current_page(2)

        lang_found = False
        for lang in self.parent.acbf_document.languages:
            if lang[1] == 'TRUE':
                lang_found = True
        if self.drawing_texts and not lang_found:
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Can't draw text areas. No languages are defined for this comic book with 'show' attribute checked.")
            response = message.run()
            message.destroy()
            return

        self.detecting_bubble = True
        cross_cursor = Gdk.Cursor.new(Gdk.CursorType.X_CURSOR)
        self.window.set_cursor(cross_cursor)

    def frames_detection(self, *args):
        if self.get_current_page_number() == 1:
            return
        if not self.drawing_frames:
            self.notebook.set_current_page(1)
        self.set_cursor_loading()

        CANNY = 500

        current_page_image = os.path.join(self.parent.tempdir, self.selected_page)
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
        gray = cv2.copyMakeBorder(gray, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=250)
        edges = cv2.Canny(gray, 10, CANNY)
        # cv2.imshow("edges", edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border / 2, border / 2))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        # cv2.imshow("closed", closed)
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
            message = Gtk.MessageDialog(parent=self, flags=0, type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                                        message_format="Failed to detect frames.")
            response = message.run()
            message.destroy()
            # self.window.set_cursor(None)
            return

        # find unindentified frames
        all_recs = []
        for rec in rectangles:
            all_recs = all_recs + rec[0]

        min_x = min(all_recs, key=lambda item: item[0])[0] - border
        max_x = max(all_recs, key=lambda item: item[0])[0] + border
        min_y = min(all_recs, key=lambda item: item[1])[1] - border
        max_y = max(all_recs, key=lambda item: item[1])[1] + border
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

            # small = cv2.resize(mask, (0,0), fx=0.2, fy=0.2)
            # cv2.imshow("1", small)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border * 4, border * 4))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.bitwise_not(mask)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border * 2, border * 2))
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.Canny(mask, 10, CANNY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border / 2, border / 2))
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
                        min_x = min(self.points, key=lambda item: item[0])[0]
                        min_y = min(self.points, key=lambda item: item[1])[1]
                        centroid = self.centroid_for_polygon(self.points, border)
                        rectangles.append((self.points, centroid[0], centroid[1], min_x, min_y))

        rectangles.sort(key=lambda tup: (tup[2], tup[1]))
        for idx, rect in enumerate(rectangles):
            self.points = rect[0]
            self.enclose_rectangle()

        # self.window.set_cursor(None)
        return

    def round_to(self, value, base):
        return int(base * round(float(value) / base))

    def left_anochor_for_polygon(self, polygon):
        min_dist = 999999999999999999999
        min_point = (10, 10)
        for point in polygon:
            dist = ((0 - point[0]) ** 2 + (0 - point[1]) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                min_point = point
        return min_point

    def area_for_polygon(self, polygon):
        result = 0
        imax = len(polygon) - 1
        for i in range(0, imax):
            result += (polygon[i][0] * polygon[i + 1][1]) - (polygon[i + 1][0] * polygon[i][1])
        result += (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1])
        return result / 2.

    def centroid_for_polygon(self, polygon, border):
        area = self.area_for_polygon(polygon)
        imax = len(polygon) - 1

        result_x = 0
        result_y = 0
        for i in range(0, imax):
            result_x += (polygon[i][0] + polygon[i + 1][0]) * (
                    (polygon[i][0] * polygon[i + 1][1]) - (polygon[i + 1][0] * polygon[i][1]))
            result_y += (polygon[i][1] + polygon[i + 1][1]) * (
                    (polygon[i][0] * polygon[i + 1][1]) - (polygon[i + 1][0] * polygon[i][1]))
        result_x += (polygon[imax][0] + polygon[0][0]) * (
                (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1]))
        result_y += (polygon[imax][1] + polygon[0][1]) * (
                (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1]))
        result_x /= (area * 6.0)
        result_y /= (area * 6.0)

        return (self.round_to(result_x, border * 25), self.round_to(result_y, border * 38))

    def page_selection_changed(self, list_view: Gtk.ListView, selection: int):
        def switch_page():
            model: Gio.ListStore = list_view.get_model()
            item: ListItem = model.get_item(selection)

            self.set_header_title(item.label)

            if item.is_cover:
                # TODO Disable frame and text tabs
                self.selected_page = self.parent.acbf_document.bookinfo.find("coverpage/" + "image").get(
                    "href").replace("\\", "/")
                self.selected_page_bgcolor = None
                color = Gdk.RGBA()
                color.parse(self.parent.acbf_document.bg_color)
            else:
                self.selected_page = item.path.replace("\\", "/")  # os.path.join(directory, page).replace("\\", "/")
                for p in self.parent.acbf_document.tree.findall("body/page"):
                    if p.find("image").get("href").replace("\\", "/") == self.selected_page:
                        self.selected_page_bgcolor = p.get("bgcolor")
                        break

            color = Gdk.RGBA()
            try:
                color.parse(self.selected_page_bgcolor)
            except:
                color.parse(self.parent.acbf_document.bg_color)
            self.page_color_button.set_rgba(color)

            self.update_page_transition()

            self.points = []
            self.load_frames()
            self.load_texts()
            self.set_modified(False)
            # Trigger redraw
            self.drawing_area.queue_draw()

        if self.is_modified:
            def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any):
                response = dialog.choose_finish(task)
                if response == 2:
                    switch_page()
                elif response == 1:
                    self.save_current_page()
                    switch_page()

            alert = Gtk.AlertDialog()
            alert.set_message("Unsaved Changes")
            alert.set_detail("There are unsaved changes that will be lost:")
            alert.set_buttons(["Cancel", "Save and Switch", "Switch (lose changes)"])
            alert.set_cancel_button(0)
            alert.set_default_button(1)
            alert.choose(self, None, handle_response, None)
        else:
            switch_page()

    def save_current_page(self) -> None:
        for page in self.parent.acbf_document.pages:
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                # Save page colour if it's different from the <body> colour
                if self.selected_page_bgcolor is not None and self.selected_page_bgcolor != self.parent.acbf_document.bg_color:
                    page.attrib["bgcolor"] = self.selected_page_bgcolor

                # Save page transition is it's not None
                if self.transition_dropdown.get_selected() > 1:
                    transition = self.transition_dropdown.get_selected_item().get_string()
                    active = self.transition_dropdown.get_sensitive()
                    if active:
                        page.attrib["transition"] = transition.lower().replace(' ', '_')

                # Save text layers
                for xml_text_layer in page.findall("text-layer"):
                    if xml_text_layer.get("lang") == self.layer_dropdown.get_selected_item().lang_iso:
                        for text_areas in xml_text_layer.findall("text-area"):
                            xml_text_layer.remove(text_areas)

                        i = 0
                        while i < 9999:
                            text_row: TextLayerItem = self.text_layer_model.get_item(i)
                            if text_row is None:
                                break

                            if text_row.polygon:
                                text_area = xml.SubElement(xml_text_layer, "text-area")
                                text_area.attrib["points"] = text_row.poly_str()
                                if text_row.rotation > 0:
                                    text_area.attrib["text-rotation"] = str(text_row.rotation)
                                if text_row.type != "speech":
                                    text_area.attrib["type"] = text_row.type
                                if text_row.colour:
                                    text_area.attrib["bgcolor"] = text_row.colour
                                if text_row.is_inverted:
                                    text_area.attrib["inverted"] = "true"

                                for text in text_row.text.split("\n"):
                                    element = xml.SubElement(text_area, "p")

                                    tag_tail = None
                                    for word in text.strip(" ").split("<"):
                                        if re.sub("[^\/]*>.*", "", word) == "":
                                            tag_name = re.sub(">.*", "", word)
                                            tag_text = re.sub("[^>]*>", "", word)
                                        elif ">" in word:
                                            tag_tail = re.sub("/[^>]*>", "", word)
                                        else:
                                            element.text = str(word)

                                        if tag_tail is not None:
                                            if " " in tag_name:
                                                tag_attr = tag_name.split(" ")[1].split("=")[0]
                                                tag_value = tag_name.split(" ")[1].split("=")[1].strip('"')
                                                tag_name = tag_name.split(" ")[0]
                                                sub_element = xml.SubElement(element, tag_name)
                                                sub_element.attrib[tag_attr] = tag_value
                                                sub_element.text = str(tag_text)
                                                sub_element.tail = str(tag_tail)
                                            else:
                                                sub_element = xml.SubElement(element, tag_name)
                                                sub_element.text = str(tag_text)
                                                sub_element.tail = str(tag_tail)

                                            tag_tail = None
                            else:
                                # Skip any record with no coordinates
                                continue
                            i += 1

                # Save frames
                for frame in page.findall("frame"):
                    frame.getparent().remove(frame)

                i = 0
                while i < 9999:
                    frame_row: FrameItem = self.frame_model.get_item(i)
                    if frame_row is None:
                        break

                    element = xml.SubElement(page, "frame")
                    element.attrib["points"] = frame_row.cords_str()
                    if frame_row.colour is not None and (
                            frame_row.colour != self.selected_page_bgcolor or frame_row.colour != self.parent.acbf_document.bg_color):
                        element.attrib["bgcolor"] = frame_row.colour

                    i += 1

        self.set_modified(False)
        self.parent.modified()

    def exit(self, widget):
        def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any):
            response = dialog.choose_finish(task)
            if response == 2:
                self.disconnect_by_func(self.exit)
                self.close()
            elif response == 1:
                self.disconnect_by_func(self.exit)
                self.save_current_page()
                self.close()
            else:
                pass

        if self.is_modified:
            alert = Gtk.AlertDialog()
            alert.set_message("Unsaved Changes")
            alert.set_detail("There are unsaved changes that will be lost:")
            alert.set_buttons(["Cancel", "Save and Close", "Close"])
            alert.set_cancel_button(0)
            alert.set_default_button(1)
            alert.choose(self, None, handle_response, None)
        else:
            return False

        return True

    def setup_list_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Label()
        #entry.set_hexpand(True)
        #entry.set_halign(Gtk.Align.FILL)
        entry.set_margin_start(5)
        entry.set_margin_end(5)
        list_item.set_child(entry)

    def bind_list_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
        item: Gtk.ListItem = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(str(item.label) or "")
        item.connect("notify::selected", self.selected_item, position)

    def setup_order_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Label()
        list_item.set_child(entry)

    def setup_move_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Button.new_from_icon_name("arrow-up-symbolic")
        list_item.set_child(entry)

    def setup_entry_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Entry()
        entry.set_editable(False)
        entry.set_can_focus(False)
        list_item.set_child(entry)

    def setup_edit_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Button.new_from_icon_name("pencil-and-paper-small-symbolic")
        list_item.set_child(entry)

    def setup_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        list_item.set_child(button)

    def setup_type_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        #entry = Gtk.Label()
        text_area_types = ["Speech", "Commentary", "Formal", "Letter", "Code", "Heading", "Audio", "Thought", "Sign"]
        entry: Gtk.DropDown = Gtk.DropDown.new_from_strings(text_area_types)
        entry.set_tooltip_text("Text Area Type")
        list_item.set_child(entry)

    def setup_remove_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(entry)

    def bind_order_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str):
        item = list_item.get_item()
        order = list_item.get_position() + 1
        entry = list_item.get_child()
        entry.set_text(str(order))

    def bind_move_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str):
        item = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Button = list_item.get_child()
        entry.set_tooltip_text(str(position))
        if position == 0:
            entry.set_sensitive(False)
        else:
            entry.set_sensitive(True)
        entry.connect("clicked", self.move_button_click, item, attribute, position)

    def unbind_move_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry: Gtk.Button = list_item.get_child()
        entry.disconnect_by_func(self.move_button_click)

    def bind_entry_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str):
        item = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Entry = list_item.get_child()
        if attribute == "frame":
            entry.set_text(str(item.cords) or "")
            entry.set_sensitive(False)
        else:
            item.bind_property("text", entry, "text", GObject.BindingFlags.SYNC_CREATE)
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-entry-symbolic")
            entry.connect("icon-release", self.edit_texts, position)

    def unbind_entry_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.edit_texts)

    def bind_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str):
        item = list_item.get_item()
        button: Gtk.ColorButton = list_item.get_child()
        colour = Gdk.RGBA()
        if item.colour is not None:
            colour.parse(item.colour)
        elif self.selected_page_bgcolor is not None:
            colour.parse(self.selected_page_bgcolor)
        elif self.parent.acbf_document.bg_color:
            colour.parse(self.parent.acbf_document.bg_color)
        else:
            colour.parse("#fff")
        button.set_rgba(colour)

        button.connect("notify::rgba", self.colour_button_set, item, attribute)

    def unbind_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        button: Gtk.ColorButton = list_item.get_child()
        button.disconnect_by_func(self.colour_button_set)

    def bind_type_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        item: TextLayerItem = list_item.get_item()
        entry: Gtk.DropDown = list_item.get_child()
        position: int = 0
        model = entry.get_model()
        i = 0
        while i < 999:
            row = model.get_item(i)
            if row is None:
                break

            if item.type.capitalize() == row.get_string():
                position = i
                break

            i += 1

        entry.set_selected(position)

        entry.connect("notify::selected", self.type_changed, item)

    def unbind_type_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.type_changed)

    def bind_remove_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str):
        item = list_item.get_item()
        entry: Gtk.Button = list_item.get_child()
        entry.connect("clicked", self.remove_button_clicked, item, attribute)

    def unbind_remove_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry: Gtk.Button = list_item.get_child()
        entry.disconnect_by_func(self.remove_button_clicked)

    def move_button_click(self, widget: Gtk.Button, item: TextLayerItem | FrameItem, attribute: str, position: int):
        if attribute == "frame":
            move_item = self.frame_model.get_item(position - 1)
            self.frame_model.splice(position - 1, 2, [item, move_item])
        else:
            move_item = self.text_layer_model.get_item(position - 1)
            self.text_layer_model.splice(position - 1, 2, [item, move_item])

    def remove_button_clicked(self, button: Gtk.Button, item, attribute: str):
        if attribute == "frame":
            found, position = self.frame_model.find(item)
            if found:
                self.frame_model.remove(position)
        else:
            found, position = self.text_layer_model.find(item)
            if found:
                self.text_layer_model.remove(position)

    def colour_button_set(self, widget: Gtk.ColorButton, _pspec, item: TextLayerItem | FrameItem, attribute: str):
        colour = widget.get_rgba()
        item.colour = self.rgb_to_hex(colour.to_string())
        found, position = self.text_layer_model.find(item)
        if found:
            self.text_layer_model.items_changed(position, 0, 0)

    def type_changed(self, widget: Gtk.DropDown, position, item: TextLayerItem):
        text_type = widget.get_selected_item().get_string()
        item.type = text_type
        self.set_modified()

    def selected_item(self, widget: Gtk.Widget, position: int):
        self.page_selection_changed(self.pages_tree, position)

    def list_item_changed(self, list_model, position, removed, added):
        self.set_modified()

    def list_text_item_changed(self, list_model, position, removed, added):
        self.set_modified()


class ColorDialog(Gtk.ColorDialog):
    def __init__(self, window, color, set_transparency, is_transparent):
        self.parent = window
        GObject.GObject.__init__(self, 'Color Selection Dialog', self, Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.get_color_selection().set_current_color(color)
        self.get_color_selection().set_has_palette(True)
        self.transparency_button = Gtk.CheckButton("Set Transparent")
        if set_transparency:
            self.get_color_selection().get_children()[0].get_children()[1].pack_start(self.transparency_button, True,
                                                                                      True, 0)
            self.transparency_button.show_all()
            self.transparency_button.connect('toggled', self.change_transparency)
        self.show_all()
        if is_transparent is not None and is_transparent.upper() == 'TRUE':
            self.transparency_button.set_active(True)

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


class TextBoxDialog(Gtk.Window):
    def __init__(self, parent: FramesEditorDialog, position: int):
        super().__init__()
        self.parent = parent
        self.set_transient_for(parent)
        self.set_size_request(500, 330)
        keycont = Gtk.EventControllerKey()
        keycont.connect("key-pressed", self.key_pressed)
        self.add_controller(keycont)

        text_layer: TextLayerItem = self.parent.text_layer_model.get_item(position)
        self.is_modified: bool = False

        self.set_size_request(600, 380)

        toolbar_header = Gtk.HeaderBar()
        toolbar_header.set_title_widget(Gtk.Label(label="Edit Texts"))
        self.set_titlebar(toolbar_header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toolbar_top = Gtk.ActionBar()

        # Being able to switch text language in the text dialogue doesn't make sense so removed
        # lang = self.parent.layer_dropdown.get_selected_item().lang_iso

        text_rotation = Gtk.Adjustment.new(0.0, 0.0, 360, 1.0, 1.0, 1.0)
        scale: Gtk.Scale = Gtk.Scale.new(orientation=Gtk.Orientation.HORIZONTAL, adjustment=text_rotation)
        scale.set_size_request(100, 50)
        scale.set_tooltip_text("Text Rotation")
        scale.set_hexpand(True)
        scale.add_mark(value=0, position=Gtk.PositionType.TOP, markup="Text Rotation")
        scale.add_mark(value=90, position=Gtk.PositionType.LEFT, markup="90")
        scale.add_mark(value=180, position=Gtk.PositionType.LEFT, markup="180")
        scale.add_mark(value=270, position=Gtk.PositionType.LEFT, markup="270")
        scale.set_digits(0)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_draw_value(True)
        scale.set_value(text_layer.rotation)
        scale.connect("value-changed", self.text_rotation_change, text_layer)
        toolbar_top.pack_start(scale)

        inverted_button = Gtk.CheckButton(label="Inverted")
        inverted_button.set_tooltip_text("Invert Text")
        inverted_button.set_active(text_layer.is_inverted)
        inverted_button.connect("toggled", self.text_invert_change, text_layer)
        toolbar_top.pack_start(inverted_button)

        transparent_button = Gtk.CheckButton(label="Transparent")
        transparent_button.set_tooltip_text("Transparent background")
        transparent_button.set_active(text_layer.is_transparent)
        transparent_button.connect("toggled", self.text_transparent_change, text_layer)
        toolbar_top.pack_start(transparent_button)

        # main box
        text_box = Gtk.TextView()
        text_box.set_wrap_mode(Gtk.WrapMode.WORD)
        text_box.get_buffer().set_text(text_layer.text)
        text_box.get_buffer().connect("changed", self.text_text_change, text_layer)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_child(text_box)

        content.append(toolbar_top)
        content.append(scrolled)

        self.set_child(content)

        self.connect("close-request", self.exit, position)

    # keyval, keycode, state, user_data
    def key_pressed(self, keyval, keycode, state, user_data):
        """print dir(Gdk.KEY_"""
        if keyval == Gdk.KEY_F1:
            self.show_help()
            return True
        elif state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (Gdk.KEY_e, Gdk.KEY_E):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0], '<emphasis>')
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1], '</emphasis>')
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0])
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor('<emphasis></emphasis>')
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 11
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_s, Gdk.KEY_S):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0], '<strong>')
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1], '</strong>')
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0])
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor('<strong></strong>')
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 9
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0], '<strikethrough>')
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1], '</strikethrough>')
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0])
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor('<strikethrough></strikethrough>')
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 16
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_p, Gdk.KEY_P):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0], '<sup>')
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1], '</sup>')
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0])
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor('<sup></sup>')
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 6
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_b, Gdk.KEY_B):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0], '<sub>')
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1], '</sub>')
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0])
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor('<sub></sub>')
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 6
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_u, Gdk.KEY_U):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    bounds = self.parent.text_box.get_buffer().get_selection_bounds()
                    text = self.parent.text_box.get_buffer().get_text(bounds[0], bounds[1]).decode('utf-8').upper()
                    text = text.replace('<EMPHASIS>', '<emphasis>').replace('</EMPHASIS>', '</emphasis>')
                    text = text.replace('<STRONG>', '<strong>').replace('</STRONG>', '</strong>')
                    text = text.replace('<STRIKETHROUGH>', '<strikethrough>').replace('</STRIKETHROUGH>',
                                                                                      '</strikethrough>')
                    text = text.replace('<SUP>', '<sup>').replace('</SUP>', '</sup>')
                    text = text.replace('<SUB>', '<sub>').replace('</SUB>', '</sub>')
                    self.parent.text_box.get_buffer().delete(bounds[0], bounds[1])
                    self.parent.text_box.get_buffer().insert(bounds[0], text)
                else:
                    bounds = self.parent.text_box.get_buffer().get_bounds()
                    text = self.parent.text_box.get_buffer().get_text(bounds[0], bounds[1]).decode('utf-8').upper()
                    text = text.replace('<EMPHASIS>', '<emphasis>').replace('</EMPHASIS>', '</emphasis>')
                    text = text.replace('<STRONG>', '<strong>').replace('</STRONG>', '</strong>')
                    text = text.replace('<STRIKETHROUGH>', '<strikethrough>').replace('</STRIKETHROUGH>',
                                                                                      '</strikethrough>')
                    text = text.replace('<SUP>', '<sup>').replace('</SUP>', '</sup>')
                    text = text.replace('<SUB>', '<sub>').replace('</SUB>', '</sub>')
                    self.parent.text_box.get_buffer().set_text(text)
            elif keyval == Gdk.KEY_space:
                self.parent.text_box.get_buffer().insert_at_cursor(' ')
        return False

    def show_help(self, *args):
        dialog: Gtk.ShortcutsWindow = Gtk.ShortcutsWindow()

        dialog.set_size_request(500, 500)

        section_one: Gtk.ShortcutsSection = Gtk.ShortcutsSection.new(Gtk.Orientation.HORIZONTAL)
        group_one: Gtk.ShortcutsGroup = Gtk.ShortcutsGroup.new(Gtk.Orientation.VERTICAL)
        #help_window: Gtk.ShortcutsShortcut = Gtk.ShortcutsShortcut(title="Help", accelerator=)
        #help_window.set_property()
        #help_window.set_title("Help")
        #help_window.set_subtitle("Show help window")
        #group_one.add_shortcut()
        section_one.add_group(group_one)
        dialog.add_section(section_one)

        # Shortcuts
        hbox = Gtk.HBox(False, 10)
        label = Gtk.Label()
        label.set_markup('<b>Shortcuts</b>')
        hbox.pack_start(label, False, False, 0)
        dialog.vbox.pack_start(hbox, False, False, 10)

        # left side
        main_hbox = Gtk.HBox(False, 3)
        left_vbox = Gtk.VBox(False, 3)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_HELP)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('This help window (F1)')
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_ITALIC)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Add &lt;emphasis> tags (CTRL + e)')
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_GOTO_TOP)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Add &lt;sup&gt; tags (CTRL + p)')
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_STRIKETHROUGH)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Add &lt;strikethrough&gt; tags (CTRL + r)')
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        main_hbox.pack_start(left_vbox, False, False, 10)

        # right side
        right_vbox = Gtk.VBox(False, 3)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.Button(label='a..A')
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Convert text to uppercase (CTRL + u)')
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_BOLD)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Add &lt;strong&gt; tags (CTRL + s)')
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_GOTO_BOTTOM)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Add &lt;sub&gt; tags (CTRL + b)')
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.Button(label='a___b')
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup('Insert non-breaking space (CTRL + space)')
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        main_hbox.pack_start(right_vbox, False, False, 10)

        dialog.vbox.pack_start(main_hbox, False, False, 0)
        dialog.get_action_area().get_children()[0].grab_focus()

        dialog.present()

        return

    def text_rotation_change(self, widget: Gtk.Scale, text_item: TextLayerItem):
        new_rotation = widget.get_value()
        text_item.rotation = new_rotation
        self.is_modified = True

    def text_invert_change(self, widget: Gtk.CheckButton, text_item: TextLayerItem):
        checked = widget.get_active()
        text_item.is_inverted = checked
        self.is_modified = True

    def text_transparent_change(self, widget: Gtk.CheckButton, text_item: TextLayerItem):
        checked = widget.get_active()
        text_item.is_transparent = checked
        self.is_modified = True

    def text_text_change(self, widget: Gtk.TextBuffer, text_item: TextLayerItem):
        text = widget.get_text(widget.get_bounds()[0], widget.get_bounds()[1], False)
        text_item.set_property("text", text)
        self.is_modified = True

    def exit(self, widget, position: int):
        if self.is_modified:
            self.parent.text_layer_model.items_changed(position, 0, 0)
