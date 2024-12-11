"""frameseditor.py - Frames/Text Layers Editor Dialog.

Copyright (C) 2011-2018 Robert Kubik
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

import logging
import os
import re
from copy import deepcopy
from typing import Any
from typing import TYPE_CHECKING

import cairo
import lxml.etree as xml
import text_layer
import detection
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import PangoCairo
from PIL import Image

from kumiko.kumikolib import Kumiko

if TYPE_CHECKING:
    import pathlib


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

    def __init__(self, cords: list[tuple[int, int]], colour: str):
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

    def __init__(
        self,
        polygon: list[tuple[int, int]],
        text: str,
        colour: str,
        is_inverted: bool,
        is_transparent: bool,
        type: str,
        rotation: int,
        references: list[str],
    ):
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
        return (
            str(self.polygon)
            .replace("[", "")
            .replace(")]", "")
            .replace(
                "(",
                "",
            )
            .replace("),", "")
            .replace(", ", ",")
        )

    def __str__(self) -> str:
        return f"Text: '{self.text}', Colour: '{self.colour}', Type: '{self.type}', Rotation: '{str(self.rotation)}'"


class FramesEditorDialog(Gtk.Window):
    """Frames Editor dialog."""

    def __init__(self, parent: Gtk.Window):
        self.parent = parent

        super().__init__(title="Frames/Text Layers Editor")
        self.set_transient_for(parent)
        self.connect("close-request", self.exit)
        self.set_size_request(1000, 1000)

        toolbar_header = Gtk.HeaderBar()
        help_button: Gtk.Button = Gtk.Button.new_from_icon_name("dialog-question-symbolic")
        help_button.connect("clicked", self.show_help)
        toolbar_header.pack_end(help_button)
        self.set_titlebar(toolbar_header)
        toolbar_top_tools: Gtk.ActionBar = Gtk.ActionBar()

        self.is_modified: bool = False
        self.points: list[tuple[int | float, int | float]] = []
        self.root_directory: pathlib.Path = os.path.dirname(
            self.parent.filename,
        )
        self.selected_page = (
            self.parent.acbf_document.bookinfo.find("coverpage/" + "image").get("href").replace("\\", "/")
        )
        self.selected_page_bgcolor: str | None = None
        self.page_color_button: Gtk.ColorDialogButton = Gtk.ColorDialogButton()
        self.drawing_frames: bool = False
        self.drawing_texts: bool = False
        self.detecting_bubble: bool = False
        self.scale_factor: float = 1
        self.transition_dropdown_dict: dict[int, str] = {
            0: "",
            1: "None",
            2: "Fade",
            3: "Blend",
            4: "Scroll Right",
            5: "Scroll Down",
        }
        self.transition_dropdown_is_active: bool = True

        self.frame_model = Gio.ListStore(item_type=FrameItem)
        self.text_layer_model = Gio.ListStore(item_type=TextLayerItem)

        frames_selection_model = Gtk.NoSelection(model=self.frame_model)
        texts_selection_model = Gtk.NoSelection(model=self.text_layer_model)

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
        sidebar_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.pages_treestore = Gio.ListStore.new(item_type=ListItem)
        page_list_factory = Gtk.SignalListItemFactory()
        page_list_factory.connect("setup", self.setup_list_item)
        page_list_factory.connect("bind", self.bind_list_item)

        selection_model: Gtk.SingleSelection = Gtk.SingleSelection.new(self.pages_treestore)
        # Enables `activate` on item single click
        selection_model.connect("selection-changed", self.tree_selection_changed)

        self.pages_tree: Gtk.ListView = Gtk.ListView.new(selection_model, page_list_factory)

        # Cover is separate, add to tree list
        cover_path: str = self.parent.acbf_document.cover_page_uri.file_path
        if cover_path:
            cover_path.replace("\\", "/")
            cover_label = cover_path.rsplit(".", 1)[0].capitalize()
            self.pages_treestore.append(ListItem(label=cover_label, path=cover_path))
        for page in self.parent.acbf_document.pages:
            page_path = page.find("image").get("href").replace("\\", "/")
            # Remove extension from file name
            page_path_split = page_path.rsplit(".", 1)
            path_label = page_path_split[0].capitalize()
            self.pages_treestore.append(
                ListItem(label=path_label, path=page_path),
            )

        self.pages_tree.connect("activate", self.page_selection_changed)

        sidebar_sw.set_child(self.pages_tree)
        main_pane_horz.set_start_child(sidebar_sw)

        # page image
        self.sw_image = Gtk.ScrolledWindow()
        self.sw_image.set_size_request(500, 500)
        self.sw_image.set_min_content_width(50)
        self.sw_image.set_min_content_height(50)
        self.sw_image.set_policy(
            Gtk.PolicyType.AUTOMATIC,
            Gtk.PolicyType.AUTOMATIC,
        )

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_content_height(500)
        self.drawing_area.set_content_width(300)
        self.drawing_area.set_draw_func(self.draw_func)
        da_mouse_press = Gtk.GestureClick()
        da_mouse_press.set_button(0)
        da_mouse_press.connect("pressed", self.draw_brush)
        self.drawing_area.add_controller(da_mouse_press)

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
        self.transition_dropdown: Gtk.DropDown = Gtk.DropDown.new_from_strings(
            list(self.transition_dropdown_dict.values()),
        )
        self.transition_dropdown_model = self.transition_dropdown.get_model()
        self.load_general()

        sw.set_child(self.general_box)
        self.notebook.insert_page(sw, Gtk.Label(label="General"), -1)

        # frames
        self.fsw = Gtk.ScrolledWindow()

        self.fsw.set_child(frames_column_view)
        self.fsw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.notebook.insert_page(self.fsw, Gtk.Label(label="Frames"), -1)

        # text-layers
        self.tsw = Gtk.ScrolledWindow()
        self.tsw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.tsw.set_child(texts_column_view)
        self.notebook.insert_page(self.tsw, Gtk.Label(label="Text-Layers"), -1)

        main_pane_vert.set_end_child(self.notebook)

        # action area top tools
        copy_layer_button = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_layer_button.set_tooltip_text("Copy Text Layer")
        self.source_layer_frames = ""
        self.source_layer_frames_no = 0
        self.source_layer_texts = ""
        self.source_layer_texts_no = 0
        copy_layer_button.connect("clicked", self.copy_layer)

        paste_layer_button = Gtk.Button.new_from_icon_name("edit-paste-symbolic")
        paste_layer_button.set_tooltip_text("Paste Text Layer")
        paste_layer_button.connect("clicked", self.paste_layer)

        self.straight_button = Gtk.CheckButton.new_with_label("Draw straight lines")
        toolbar_top_tools.pack_start(self.straight_button)
        self.find_frames_buttons: Gtk.Button = Gtk.Button.new_with_label("Find frames")
        self.find_frames_buttons.connect("clicked", self.find_frames)
        self.find_frames_buttons.set_sensitive(False)
        toolbar_top_tools.pack_start(self.find_frames_buttons)
        self.find_bubble_button: Gtk.Button = Gtk.Button.new_with_label("Find bubble")
        self.find_bubble_button.connect("clicked", lambda widget: self.set_bubble_detection(True))
        self.find_bubble_button.set_sensitive(False)
        toolbar_top_tools.pack_start(self.find_bubble_button)

        self.zoom_dropdown: Gtk.DropDown = Gtk.DropDown.new_from_strings(
            ["10%", "25%", "50%", "75%", "100%", "125%", "175%", "200%"],
        )
        self.zoom_dropdown.set_tooltip_text("Zoom")
        self.zoom_dropdown.set_selected(4)
        self.zoom_dropdown.connect("notify::selected", self.change_zoom)

        self.layer_dropdown: Gtk.DropDown = self.parent.create_lang_dropdown(
            self.parent.all_lang_store,
            self.change_layer,
        )
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

        self.set_child(content)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.key_pressed)
        self.add_controller(key_controller)

    def set_header_title(self, text: str = "") -> None:
        new_title: str = "Frames/Text Layers Editor - " + self.selected_page
        if self.is_modified:
            new_title += "*"
        self.set_title(new_title)

    def tree_selection_changed(self, selection_model: Gtk.SingleSelection, position: int, n_items: int) -> None:
        model: Gio.ListStore = selection_model.get_model()
        # Seem we need to find the change ourselves
        i = 0
        while i < 9999:
            item = model.get_item(i)
            if item is None:
                break

            is_selected = selection_model.is_selected(i)
            if is_selected:
                self.pages_tree.emit("activate", i)
                break

            i = i + 1

    def detect_bubble(self, x: float, y: float) -> None:
        tree_model: Gtk.SingleSelection = self.pages_tree.get_model()
        item: ListItem | None = tree_model.get_selected_item()

        if item is not None:
            full_path = os.path.join(self.parent.tempdir, item.path)
            points = detection.text_bubble_detection(full_path, x, y)
            if len(points) > 0:
                polygons: list[tuple[int, int]] = []
                for point in points:
                    polygons.append((int(point[0]), int(point[1])))
                self.text_layer_model.append(
                    TextLayerItem(
                        polygon=polygons,
                        text=" ",
                        colour="#ffffff",
                        rotation=0,
                        type="normal",
                        is_inverted=False,
                        is_transparent=False,
                        references=[],
                    ),
                )
                self.drawing_area.queue_draw()
            else:
                message: Gtk.AlertDialog = Gtk.AlertDialog()
                message.set_message("Failed to detect text area.")
                message.show(self)

    def copy_layer(self, widget: Gtk.Button | None = None) -> None:
        number_of_frames = len(self.parent.acbf_document.load_page_frames(self.get_current_page_number()))
        number_of_texts = 0
        selected_layer = self.layer_dropdown.get_selected_item()
        if selected_layer.show:
            number_of_texts = len(
                self.parent.acbf_document.load_page_texts(self.get_current_page_number(), selected_layer)[0],
            )

        message = Gtk.AlertDialog()

        if self.drawing_frames is False and self.drawing_texts is False:
            message.set_message("Nothing to copy.\nSelect 'Frames' or 'Text-Layers' tab.")
        elif self.drawing_frames is True and number_of_frames == 0:
            message.set_message("Nothing to copy.\nNo frames found on this page.")
        elif self.drawing_texts is True and number_of_texts == 0:
            message.set_message("Nothing to copy.\nNo text-layers found on this page for layer: " + selected_layer)
        elif self.drawing_frames:
            message.set_message(f"Frames layer copied: {str(number_of_frames)} objects.")
            self.source_layer_frames = self.selected_page
            self.source_layer_frames_no = self.get_current_page_number()
        elif self.drawing_texts:
            message.set_message(f"Text-layer copied: {str(number_of_texts)} objects.")
            self.source_layer_texts = self.selected_page
            self.source_layer_texts_no = self.get_current_page_number()
        else:
            return
        message.show()
        return

    def set_bubble_detection(self, active: bool = False) -> None:
        self.detecting_bubble = active
        if active:
            self.set_mouse_cursor(self.drawing_area, "crosshair")
        else:
            self.set_mouse_cursor(self.drawing_area)

    def paste_layer(self, widget: Gtk.Button | None = None) -> None:
        def paste_layer() -> None:
            alert = Gtk.AlertDialog()

            if self.drawing_frames is False and self.drawing_texts is False:
                alert.set_message("Select 'Frames' or 'Text-Layers' tab to paste into.")
                alert.show()
            elif self.drawing_frames and (
                self.source_layer_frames_no == 0 or self.source_layer_frames_no == self.get_current_page_number()
            ):
                alert.set_message("Nothing to paste. Copy frames from some other page first.")
                alert.show()
            elif self.drawing_texts and (
                self.source_layer_texts_no == 0 or self.source_layer_texts_no == self.get_current_page_number()
            ):
                alert.set_message("Nothing to paste. Copy text-layer from some other page first.")
                alert.show()
            elif self.drawing_frames:
                alert.set_message("Frames pasted from page " + self.source_layer_frames)
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

                alert.show()

                self.drawing_area.queue_draw()

            elif self.drawing_texts:
                selected_layer = self.layer_dropdown.get_selected_item()
                alert.set_message("Text-layer pasted from page " + self.source_layer_texts)
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
                                    if (
                                        source_page.find("image").get("href").replace("\\", "/")
                                        == self.source_layer_texts
                                    ):
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
                alert.show()

        def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any) -> None:
            response = dialog.choose_finish(task)
            if response == 0:
                paste_layer()

        alert = Gtk.AlertDialog()
        alert.set_message("Paste Layer")
        alert.set_buttons(["Yes", "No"])
        alert.set_cancel_button(1)
        alert.set_default_button(0)

        if self.drawing_frames:
            alert.set_detail(
                f"Are you sure you want to paste frames from page {self.source_layer_frames}? Current layer will be removed.",
            )
        else:
            alert.set_detail(
                f"Are you sure you want to paste text-layers from page {self.source_layer_texts}? Current layer will be removed.",
            )

        alert.choose(self, None, handle_response, None)

    def key_pressed(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> bool:
        modifiers = state & Gtk.accelerator_get_default_mod_mask()
        control_mask = Gdk.ModifierType.CONTROL_MASK

        if modifiers == control_mask and keyval == Gdk.KEY_c:
            self.copy_layer()
        elif modifiers == control_mask and keyval == Gdk.KEY_v:
            self.paste_layer()
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.enclose_rectangle()
        elif keyval == Gdk.KEY_Escape:
            self.cancel_rectangle()
            self.set_bubble_detection()
        elif keyval == Gdk.KEY_BackSpace:
            if len(self.points) == 1:
                self.cancel_rectangle()
                self.set_bubble_detection()
            elif len(self.points) > 1:
                del self.points[-1]
                self.drawing_area.queue_draw()

        elif keyval == Gdk.KEY_F1:
            self.show_help()
        elif keyval == Gdk.KEY_Delete:
            self.delete_page()
        elif keyval in (Gdk.KEY_F8, Gdk.KEY_F, Gdk.KEY_f):
            self.find_frames()
        elif keyval in (Gdk.KEY_F7, Gdk.KEY_T, Gdk.KEY_t):
            self.set_bubble_detection(True)
        elif keyval == Gdk.KEY_F5:
            self.drawing_area.queue_draw()
        elif keyval in (Gdk.KEY_h, Gdk.KEY_H, Gdk.KEY_F11):
            if self.notebook.get_property("visible"):
                self.notebook.hide()
                self.pages_tree.hide()
            else:
                self.notebook.show()
                self.pages_tree.show()
        elif keyval == Gdk.KEY_Right:
            return False
        elif keyval == Gdk.KEY_Left:
            return False
        elif keyval == Gdk.KEY_Down:
            return False
        elif keyval == Gdk.KEY_Up:
            return False

        return True

    def show_help(self, widget: Gtk.Widget | None = None) -> None:
        dialog = Gtk.ShortcutsWindow()
        dialog.set_title("Help")

        shortcut_section: Gtk.ShortcutsSection = Gtk.ShortcutsSection(section_name="frames")
        dialog.add_section(shortcut_section)

        shortcut_group: Gtk.ShortcutsGroup = Gtk.ShortcutsGroup(title="General")
        shortcut_section.add_group(shortcut_group)

        shortcut: Gtk.ShortcutsShortcut = Gtk.ShortcutsShortcut(
            title="Help", subtitle="This help window", accelerator="F1"
        )
        shortcut_group.add_shortcut(shortcut)
        shortcut = Gtk.ShortcutsShortcut(
            title="Hide windows", subtitle="Hide bottom and side bars", accelerator="h F11"
        )
        shortcut_group.add_shortcut(shortcut)
        shortcut = Gtk.ShortcutsShortcut(title="Delete Page", subtitle="Delete current page", accelerator="Delete")
        shortcut_group.add_shortcut(shortcut)

        shortcut_group = Gtk.ShortcutsGroup(title="Panels")
        shortcut_section.add_group(shortcut_group)

        shortcut = Gtk.ShortcutsShortcut(
            title="Find Panels", subtitle="Automatically find panels on this page", accelerator="f"
        )
        shortcut_group.add_shortcut(shortcut)
        shortcut = Gtk.ShortcutsShortcut(title="Copy Layer", subtitle="Copy Frames/Text-Layer", accelerator="<ctrl>c")
        shortcut_group.add_shortcut(shortcut)
        shortcut = Gtk.ShortcutsShortcut(title="Paste Layer", subtitle="Paste Frames/Text-Layer", accelerator="<ctrl>v")
        shortcut_group.add_shortcut(shortcut)

        shortcut_group = Gtk.ShortcutsGroup(title="Drawing")
        shortcut_section.add_group(shortcut_group)

        shortcut = Gtk.ShortcutsShortcut(
            title="Enclose Rectangle", subtitle="Finalise and enclose the current rectangle", accelerator="Return"
        )
        shortcut_group.add_shortcut(shortcut)
        shortcut = Gtk.ShortcutsShortcut(
            title="Cancel Rectangle", subtitle="Cancel drawing the current rectangle", accelerator="Escape"
        )
        shortcut_group.add_shortcut(shortcut)
        shortcut = Gtk.ShortcutsShortcut(
            title="Remove Last Point", subtitle="Remove the last drawn point", accelerator="BackSpace"
        )
        shortcut_group.add_shortcut(shortcut)

        # dialog.props.section_name = "main"
        """# Shortcuts
        label.set_markup("Draw straight line by holding down Control key")
        label.set_markup("Refresh image (F5)")
        label.set_markup('Detect Frames (F8 or "F" key)')
        label.set_markup('Detect Bubble at cursor (F7 or "T" key)')"""

        dialog.present()

    def delete_page(self) -> None:
        if self.get_current_page_number() <= 1:
            return

        def delete_page() -> None:
            for page in self.parent.acbf_document.tree.findall("body/page"):
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    self.parent.acbf_document.tree.find("body").remove(page)
                    in_path = os.path.join(self.parent.tempdir, page.find("image").get("href").replace("\\", "/"))
                    if os.path.isfile(in_path):
                        os.remove(in_path)

            for image in self.parent.acbf_document.tree.findall("data/binary"):
                if image.get("id") == self.selected_page[1:]:
                    self.parent.acbf_document.tree.find("data").remove(image)

            self.parent.acbf_document.pages = self.parent.acbf_document.tree.findall("body/page")

            self.pages_tree.get_selection().get_selected()[0].remove(self.pages_tree.get_selection().get_selected()[1])
            self.pages_tree.set_cursor((0, 0))
            self.pages_tree.grab_focus()

            self.set_modified()

        def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any) -> None:
            response = dialog.choose_finish(task)
            if response == 0:
                delete_page()

        alert = Gtk.AlertDialog()
        alert.set_message("Delete Page")
        alert.set_detail("Are you sure you want to delete this page?")
        alert.set_buttons(["Yes", "No"])
        alert.set_cancel_button(1)
        alert.set_default_button(0)

        alert.choose(self, None, handle_response, None)

    def set_modified(self, modified: bool = True) -> None:
        self.is_modified = modified
        self.set_header_title()
        self.drawing_area.queue_draw()

    def change_zoom(self, widget: Gtk.Button, _pspec: GObject.GParamSpec) -> None:
        self.scale_factor = float(self.zoom_dropdown.get_selected_item().get_string()[0:-1]) / 100
        self.drawing_area.queue_draw()

    def change_layer(self, widget: Gtk.DropDown, _pspec: GObject.GParamSpec) -> None:
        self.load_texts()
        self.drawing_area.queue_draw()

    def set_mouse_cursor(self, widget: Gtk.Widget | None = None, icon_name: str = "default") -> None:
        if widget is not None:
            widget.set_cursor_from_name(icon_name)
        else:
            self.set_cursor_from_name(icon_name)

    def tab_change(self, notebook: Gtk.Notebook, page: Gtk.ScrolledWindow, page_num: int) -> None:
        if page_num == 1:
            self.drawing_frames = True
            self.drawing_texts = False
            self.find_frames_buttons.set_sensitive(True)
            self.find_bubble_button.set_sensitive(False)
            self.set_mouse_cursor(self.drawing_area, "crosshair")
        elif page_num == 2:
            self.drawing_frames = False
            self.drawing_texts = True
            self.find_bubble_button.set_sensitive(True)
            self.find_frames_buttons.set_sensitive(False)
            self.set_mouse_cursor(self.drawing_area, "crosshair")
        else:
            self.drawing_frames = False
            self.drawing_texts = False
            self.find_frames_buttons.set_sensitive(False)
            self.find_bubble_button.set_sensitive(False)
            self.set_mouse_cursor(self.drawing_area)

    def load_general(self) -> None:
        # main bg_color
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label = Gtk.Label()
        label.set_markup("Main Background Color: ")
        hbox.append(label)

        color = Gdk.RGBA()
        color.parse(self.parent.acbf_document.bg_color)

        color_button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        color_button.set_rgba(color)
        color_button.connect("notify::rgba", self.set_body_bgcolor)
        hbox.append(color_button)
        self.general_box.append(hbox)

        # page bg_color
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label = Gtk.Label()
        label.set_markup("Page Background Color: ")
        hbox.append(label)

        color = Gdk.RGBA()
        try:
            color.parse(self.selected_page_bgcolor)
        except Exception:
            color.parse(self.parent.acbf_document.bg_color)
        self.page_color_button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        self.page_color_button.set_rgba(color)
        self.page_color_button.connect("notify::rgba", self.set_page_bgcolor)
        hbox.append(self.page_color_button)
        self.general_box.append(hbox)

        # transition
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label = Gtk.Label()
        label.set_markup("Page Transition: ")
        hbox.append(label)

        # self.transition_dropdown.connect("notify::selected", self.page_transition_changed)

        hbox.append(self.transition_dropdown)
        self.update_page_transition()
        self.general_box.append(hbox)

    def update_page_transition(self) -> None:
        current_trans = self.parent.acbf_document.get_page_transition(
            self.get_current_page_number(),
        )
        if current_trans is None:
            self.transition_dropdown.set_selected(0)
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

    def page_transition_changed(self, widget: Gtk.DropDown, _pspec: GObject.GParamSpec) -> None:
        transition = widget.get_selected_item().get_string()
        active = widget.get_sensitive()
        if active:
            for page in self.parent.acbf_document.pages:
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    page.attrib["transition"] = transition.lower().replace(" ", "_")
            self.set_modified()

    def set_body_bgcolor(self, widget: Gtk.Button, _pspec: GObject.GParamSpec | None = None) -> None:
        colour: Gdk.RGBA = widget.get_rgba()
        self.parent.acbf_document.tree.find(
            "body",
        ).attrib["bgcolor"] = self.rgb_to_hex(colour.to_string())
        self.parent.modified()

    def rgb_to_hex(self, rgb_string: str) -> str:
        """Converts an rgb or rgba string to a hexadecimal color string."""
        # Remove 'rgb(' and ')'
        rgb_string = rgb_string.strip("rgb()")
        # Split the string into components
        rgb_values = [int(x) for x in rgb_string.split(",")]
        # Convert to hex
        hex_values = [hex(x)[2:].zfill(2) for x in rgb_values]
        # Format the output
        hex_color = "#" + "".join(hex_values)
        return hex_color

    def set_page_bgcolor(self, widget: Gtk.DropDown, _pspec: GObject.GParamSpec | None = None) -> None:
        colour: Gdk.RGBA = widget.get_rgba()
        self.selected_page_bgcolor = self.rgb_to_hex(colour.to_string())
        self.set_modified()

    def load_frames(self) -> None:
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
            cr.set_source_rgba(
                self.frames_color.red,
                self.frames_color.green,
                self.frames_color.blue,
                self.frames_color.alpha,
            )

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

    def scale_polygon(self, polygon: list[tuple[int, int]]) -> list[tuple[int, int]]:
        polygon_out = []
        for point in polygon:
            polygon_out.append(
                (
                    int(point[0] * self.scale_factor),
                    int(point[1] * self.scale_factor),
                ),
            )
        return polygon_out

    def load_texts(self) -> None:
        try:
            self.text_layer_model.disconnect_by_func(self.list_text_item_changed)
        except Exception:
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
                TextLayerItem(
                    polygon=text_areas[0],
                    text=text_areas[1],
                    colour=text_areas[2],
                    rotation=text_areas[3],
                    type=text_areas[4],
                    is_inverted=text_areas[5],
                    is_transparent=text_areas[6],
                    references=refs,
                ),
            )

        self.text_layer_model.connect(
            "items_changed",
            self.list_text_item_changed,
        )

    def draw_texts(self) -> cairo.Surface:
        """Draws around the text boxes and the numbers next to the text boxes not the actual text"""
        width = self.drawing_area.get_content_width()
        height = self.drawing_area.get_content_height()
        # Create a Cairo ImageSurface to draw text on
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)

        i = -1
        while i < 9999:
            i = i + 1
            text_area: TextLayerItem = self.text_layer_model.get_item(i)
            if text_area is None:
                break
            # Prepare drawing data
            polygon = self.scale_polygon(text_area.polygon)
            label_text = (
                f'<span foreground="red" background="white" size="{self.scale_factor * 125}%"><b>{i + 1}</b></span>'
            )

            # Set the color for the polygon
            cr.set_source_rgba(
                self.text_layers_color.red,
                self.text_layers_color.green,
                self.text_layers_color.blue,
                self.text_layers_color.alpha,
            )
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

    def move_text_up(self, widget: Gtk.Button, polygon: list[tuple[int, int]]) -> None:
        for page in self.parent.acbf_document.pages:
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                xml_frame = ""
                for point in polygon:
                    xml_frame = xml_frame + str(point[0]) + "," + str(point[1]) + " "
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

    def edit_texts(self, widget: Gtk.Button, pos: Gtk.EntryIconPosition, position: int) -> None:
        dialog = TextBoxDialog(self, position)
        dialog.present()

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

    def get_current_page_number(self) -> int:
        for idx, page in enumerate(self.parent.acbf_document.pages):
            if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                ret_idx = idx + 2
                break
        else:
            ret_idx = 1
        return ret_idx

    def draw_page_image(self) -> cairo.Surface:
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
                    xx = text_layer.TextLayer(
                        current_page_image,
                        self.get_current_page_number(),
                        self.parent.acbf_document,
                        i,
                        self.text_layer_model,
                        self.frame_model,
                    )
                    img = xx.PILBackgroundImage

                i = i + 1
        else:
            img, bg_color = self.parent.acbf_document.load_page_image(self.get_current_page_number())

        if self.scale_factor != 1:
            img = img.resize(
                (
                    int(img.size[0] * self.scale_factor),
                    int(img.size[1] * self.scale_factor),
                ),
                Image.Resampling.BICUBIC,
            )

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

        return surface

    def draw_brush(self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float) -> bool:
        # TODO Remove as frames and texts ARE allowed on cover page
        if self.get_current_page_number() == 1:
            return True

        # Must be in frames or texts notebook tab
        if not self.drawing_frames and not self.drawing_texts:
            return False

        if self.detecting_bubble:
            self.detect_bubble(x, y)
            self.set_bubble_detection()
            return False

        # Close current points if double or right-click
        if n_press > 1 or gesture.get_current_button() == 3:
            self.enclose_rectangle()
            return True

        # TODO More tools Old comment: draw vertical/horizontal line with CTRL key pressed

        lang_found = False
        for lang in self.parent.acbf_document.languages:
            if lang[1] == "TRUE":
                lang_found = True
        if self.drawing_texts and not lang_found:
            # TODO alert
            print("Can't draw text areas. No languages are defined for this comic book with 'show' attribute checked.")

        if (
            (len(self.points) > 0)
            and (x > self.points[0][0] - 5 and x < self.points[0][0] + 5)
            and (y > self.points[0][1] - 5 and y < self.points[0][1] + 5)
        ):
            if len(self.points) > 2:
                self.enclose_rectangle()
            else:
                self.points.append((int(x / self.scale_factor), int(y / self.scale_factor)))
        else:
            self.points.append(
                (
                    int(x / self.scale_factor),
                    int(y / self.scale_factor),
                ),
            )

        # Trigger redraw
        self.drawing_area.queue_draw()

        return True

    def cancel_rectangle(self) -> None:
        self.drawing_area.queue_draw()
        self.points = []

    def enclose_rectangle(self, color: str = "#ffffff") -> None:
        if len(self.points) > 2:
            xml_frame = ""
            for point in self.points:
                xml_frame = xml_frame + str(point[0]) + "," + str(point[1]) + " "
            for page in self.parent.acbf_document.pages:
                if page.find("image").get("href").replace("\\", "/") == self.selected_page:
                    if self.drawing_frames:
                        # add frame
                        xml.SubElement(page, "frame", points=xml_frame.strip())
                        self.load_frames()
                        self.set_modified()

                    elif self.drawing_texts:
                        # add text-area
                        for lang in self.parent.acbf_document.languages:
                            if lang[1] == "TRUE":
                                layer_found = False
                                for layer in page.findall("text-layer"):
                                    if layer.get("lang") == lang[0]:
                                        layer_found = True
                                        area = xml.SubElement(
                                            layer,
                                            "text-area",
                                            points=xml_frame.strip(),
                                            bgcolor=str(color),
                                        )
                                        par = xml.SubElement(area, "p")
                                        par.text = "..."
                                if not layer_found:
                                    layer = xml.SubElement(page, "text-layer", lang=lang[0])
                                    area = xml.SubElement(
                                        layer,
                                        "text-area",
                                        points=xml_frame.strip(),
                                        bgcolor=str(color),
                                    )
                                    par = xml.SubElement(area, "p")
                                    par.text = "..."
                        self.load_texts()
                        self.set_modified()

            self.points = []
            # Trigger redraw
            self.drawing_area.queue_draw()

    def find_frames(self, widget: Gtk.Button | None = None) -> None:
        k = Kumiko(
            {
                "debug": False,
                "progress": False,
                "rtl": False,
                "min_panel_size_ratio": False,
                "panel_expansion": False,
            }
        )
        k.parse_image(os.path.join(self.parent.tempdir, self.selected_page))
        infos = k.get_infos()

        for i, frame in enumerate(infos[0]["panels"]):
            # [x, y, width, height]
            frame_tuple = [
                (frame[0], frame[1]),
                (frame[0] + frame[2], frame[1]),
                (frame[0] + frame[2], frame[1] + frame[3]),
                (frame[0], frame[1] + frame[3]),
            ]
            self.frame_model.splice(i, 0, [FrameItem(cords=frame_tuple, colour="")])

    def round_to(self, value: float, base: float) -> int:
        return int(base * round(float(value) / base))

    def left_anochor_for_polygon(
        self,
        polygon: list[tuple[int | float, int | float]],
    ) -> tuple[int | float, int | float]:
        min_dist: int | float = 999999999999999999999
        min_point: tuple[int | float, int | float] = (10, 10)
        for point in polygon:
            dist = ((0 - point[0]) ** 2 + (0 - point[1]) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                min_point = point
        return min_point

    def area_for_polygon(self, polygon: list[tuple[int | float, int | float]]) -> float:
        result: int | float = 0
        imax = len(polygon) - 1
        for i in range(0, imax):
            result += (polygon[i][0] * polygon[i + 1][1]) - (polygon[i + 1][0] * polygon[i][1])
        result += (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1])
        return result / 2.0

    def centroid_for_polygon(
        self,
        polygon: list[tuple[int | float, int | float]],
        border: int,
    ) -> tuple[int | float, int | float]:
        area = self.area_for_polygon(polygon)
        imax = len(polygon) - 1

        result_x: int | float = 0
        result_y: int | float = 0
        for i in range(0, imax):
            result_x += (polygon[i][0] + polygon[i + 1][0]) * (
                (polygon[i][0] * polygon[i + 1][1]) - (polygon[i + 1][0] * polygon[i][1])
            )
            result_y += (polygon[i][1] + polygon[i + 1][1]) * (
                (polygon[i][0] * polygon[i + 1][1]) - (polygon[i + 1][0] * polygon[i][1])
            )
        result_x += (polygon[imax][0] + polygon[0][0]) * (
            (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1])
        )
        result_y += (polygon[imax][1] + polygon[0][1]) * (
            (polygon[imax][0] * polygon[0][1]) - (polygon[0][0] * polygon[imax][1])
        )
        result_x /= area * 6.0
        result_y /= area * 6.0

        return (
            self.round_to(result_x, border * 25),
            self.round_to(result_y, border * 38),
        )

    def page_selection_changed(self, list_view: Gtk.ListView, selection: int) -> None:
        def switch_page() -> None:
            model: Gio.ListStore = list_view.get_model()
            item: ListItem = model.get_item(selection)

            self.set_header_title(item.label)

            if item.is_cover:
                # TODO Disable frame and text tabs
                self.selected_page = (
                    self.parent.acbf_document.bookinfo.find("coverpage/" + "image").get("href").replace("\\", "/")
                )
                self.selected_page_bgcolor = None
                color = Gdk.RGBA()
                color.parse(self.parent.acbf_document.bg_color)
            else:
                self.selected_page = item.path.replace("\\", "/")
                for p in self.parent.acbf_document.tree.findall("body/page"):
                    if p.find("image").get("href").replace("\\", "/") == self.selected_page:
                        self.selected_page_bgcolor = p.get("bgcolor")
                        break

            color = Gdk.RGBA()
            try:
                color.parse(self.selected_page_bgcolor)
            except Exception:
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

            def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any) -> None:
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
                if (
                    self.selected_page_bgcolor is not None
                    and self.selected_page_bgcolor != self.parent.acbf_document.bg_color
                ):
                    page.attrib["bgcolor"] = self.selected_page_bgcolor

                # Save page transition is it's not None
                if self.transition_dropdown.get_selected() > 1:
                    transition = self.transition_dropdown.get_selected_item().get_string()
                    active = self.transition_dropdown.get_sensitive()
                    if active:
                        page.attrib["transition"] = transition.lower().replace(" ", "_")

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
                                        if re.sub(r"[^\/]*>.*", "", word) == "":
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
                        frame_row.colour != self.selected_page_bgcolor
                        or frame_row.colour != self.parent.acbf_document.bg_color
                    ):
                        element.attrib["bgcolor"] = frame_row.colour

                    i += 1

        self.set_modified(False)
        self.parent.modified()

    def exit(self, widget: Gtk.Button) -> bool:
        def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any) -> None:
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

    def setup_list_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Label()
        entry.set_margin_start(5)
        entry.set_margin_end(5)
        list_item.set_child(entry)

    def bind_list_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item: Gtk.ListItem = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(str(item.label) or "")
        item.connect("notify::selected", self.selected_item, position)

    def setup_order_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Label()
        list_item.set_child(entry)

    def setup_move_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Button.new_from_icon_name("arrow-up-symbolic")
        list_item.set_child(entry)

    def setup_entry_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Entry()
        entry.set_editable(False)
        entry.set_can_focus(False)
        list_item.set_child(entry)

    def setup_edit_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Button.new_from_icon_name("pencil-and-paper-small-symbolic")
        list_item.set_child(entry)

    def setup_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        list_item.set_child(button)

    def setup_type_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        # entry = Gtk.Label()
        text_area_types = [
            "Speech",
            "Commentary",
            "Formal",
            "Letter",
            "Code",
            "Heading",
            "Audio",
            "Thought",
            "Sign",
        ]
        entry: Gtk.DropDown = Gtk.DropDown.new_from_strings(text_area_types)
        entry.set_tooltip_text("Text Area Type")
        list_item.set_child(entry)

    def setup_remove_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(entry)

    def bind_order_column(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str
    ) -> None:
        order = list_item.get_position() + 1
        entry = list_item.get_child()
        entry.set_text(str(order))

    def bind_move_column(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str
    ) -> None:
        item = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Button = list_item.get_child()
        entry.set_tooltip_text(str(position))
        if position == 0:
            entry.set_sensitive(False)
        else:
            entry.set_sensitive(True)
        entry.connect("clicked", self.move_button_click, item, attribute, position)

    def unbind_move_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry: Gtk.Button = list_item.get_child()
        entry.disconnect_by_func(self.move_button_click)

    def bind_entry_column(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str
    ) -> None:
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

    def unbind_entry_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.edit_texts)

    def bind_colour_column(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str
    ) -> None:
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

    def unbind_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        button: Gtk.ColorButton = list_item.get_child()
        button.disconnect_by_func(self.colour_button_set)

    def bind_type_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
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

    def unbind_type_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.type_changed)

    def bind_remove_column(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell, attribute: str
    ) -> None:
        item = list_item.get_item()
        entry: Gtk.Button = list_item.get_child()
        entry.connect("clicked", self.remove_button_clicked, item, attribute)

    def unbind_remove_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry: Gtk.Button = list_item.get_child()
        entry.disconnect_by_func(self.remove_button_clicked)

    def move_button_click(
        self, widget: Gtk.Button, item: TextLayerItem | FrameItem, attribute: str, position: int
    ) -> None:
        if attribute == "frame":
            move_item = self.frame_model.get_item(position - 1)
            self.frame_model.splice(position - 1, 2, [item, move_item])
        else:
            move_item = self.text_layer_model.get_item(position - 1)
            self.text_layer_model.splice(position - 1, 2, [item, move_item])

    def remove_button_clicked(self, button: Gtk.Button, item: FrameItem, attribute: str) -> None:
        if attribute == "frame":
            found, position = self.frame_model.find(item)
            if found:
                self.frame_model.remove(position)
        else:
            found, position = self.text_layer_model.find(item)
            if found:
                self.text_layer_model.remove(position)

    def colour_button_set(
        self, widget: Gtk.ColorButton, _pspec: GObject.GParamSpec, item: TextLayerItem | FrameItem, attribute: str
    ) -> None:
        colour = widget.get_rgba()
        item.colour = self.rgb_to_hex(colour.to_string())
        found, position = self.text_layer_model.find(item)
        if found:
            self.text_layer_model.items_changed(position, 0, 0)

    def type_changed(self, widget: Gtk.DropDown, position: int, item: TextLayerItem) -> None:
        text_type = widget.get_selected_item().get_string()
        item.type = text_type
        self.set_modified()

    def selected_item(self, widget: Gtk.Widget, position: int) -> None:
        self.page_selection_changed(self.pages_tree, position)

    def list_item_changed(self, list_model: FrameItem, position: int, removed: int, added: int) -> None:
        self.set_modified()

    def list_text_item_changed(self, list_model: TextLayerItem, position: int, removed: int, added: int) -> None:
        self.set_modified()


class ColorDialog(Gtk.ColorDialog):
    def __init__(self, window: Gtk.Window, color: str, set_transparency: bool, is_transparent: bool) -> None:
        self.parent = window
        GObject.GObject.__init__(self, "Color Selection Dialog", self, Gtk.DialogFlags.DESTROY_WITH_PARENT)
        self.get_color_selection().set_current_color(color)
        self.get_color_selection().set_has_palette(True)
        self.transparency_button = Gtk.CheckButton("Set Transparent")
        if set_transparency:
            self.get_color_selection().get_children()[0].get_children()[1].pack_start(
                self.transparency_button,
                True,
                True,
                0,
            )
            self.transparency_button.show_all()
            self.transparency_button.connect("toggled", self.change_transparency)
        self.show_all()
        if is_transparent is not None and is_transparent:
            self.transparency_button.set_active(True)

    def change_transparency(self, widget: Gtk.CheckButton) -> None:
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

        # TODO Add additional text box for another language to help translation

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
    def key_pressed(self, keyval: int, keycode: int, state: Gdk.ModifierType, user_data: Any) -> bool:
        # TODO eventcontroller
        """print dir(Gdk.KEY_"""
        if keyval == Gdk.KEY_F1:
            self.show_help()
            return True
        elif state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (Gdk.KEY_e, Gdk.KEY_E):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                        "<emphasis>",
                    )
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1],
                        "</emphasis>",
                    )
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                    )
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor("<emphasis></emphasis>")
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 11
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_s, Gdk.KEY_S):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                        "<strong>",
                    )
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1],
                        "</strong>",
                    )
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                    )
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor("<strong></strong>")
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 9
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                        "<strikethrough>",
                    )
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1],
                        "</strikethrough>",
                    )
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                    )
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor(
                        "<strikethrough></strikethrough>",
                    )
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 16
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_p, Gdk.KEY_P):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                        "<sup>",
                    )
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1],
                        "</sup>",
                    )
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                    )
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor("<sup></sup>")
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 6
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_b, Gdk.KEY_B):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                        "<sub>",
                    )
                    self.parent.text_box.get_buffer().insert(
                        self.parent.text_box.get_buffer().get_selection_bounds()[1],
                        "</sub>",
                    )
                    self.parent.text_box.get_buffer().place_cursor(
                        self.parent.text_box.get_buffer().get_selection_bounds()[0],
                    )
                else:
                    self.parent.text_box.get_buffer().insert_at_cursor("<sub></sub>")
                    cursorPosition = self.parent.text_box.get_buffer().get_property("cursor-position") - 6
                    cursorIter = self.parent.text_box.get_buffer().get_iter_at_offset(cursorPosition)
                    self.parent.text_box.get_buffer().place_cursor(cursorIter)
            elif keyval in (Gdk.KEY_u, Gdk.KEY_U):
                if len(self.parent.text_box.get_buffer().get_selection_bounds()) > 0:
                    bounds = self.parent.text_box.get_buffer().get_selection_bounds()
                    text = (
                        self.parent.text_box.get_buffer()
                        .get_text(
                            bounds[0],
                            bounds[1],
                        )
                        .decode("utf-8")
                        .upper()
                    )
                    text = text.replace("<EMPHASIS>", "<emphasis>").replace(
                        "</EMPHASIS>",
                        "</emphasis>",
                    )
                    text = text.replace("<STRONG>", "<strong>").replace(
                        "</STRONG>",
                        "</strong>",
                    )
                    text = text.replace("<STRIKETHROUGH>", "<strikethrough>").replace(
                        "</STRIKETHROUGH>",
                        "</strikethrough>",
                    )
                    text = text.replace("<SUP>", "<sup>").replace(
                        "</SUP>",
                        "</sup>",
                    )
                    text = text.replace("<SUB>", "<sub>").replace(
                        "</SUB>",
                        "</sub>",
                    )
                    self.parent.text_box.get_buffer().delete(
                        bounds[0],
                        bounds[1],
                    )
                    self.parent.text_box.get_buffer().insert(bounds[0], text)
                else:
                    bounds = self.parent.text_box.get_buffer().get_bounds()
                    text = (
                        self.parent.text_box.get_buffer()
                        .get_text(
                            bounds[0],
                            bounds[1],
                        )
                        .decode("utf-8")
                        .upper()
                    )
                    text = text.replace("<EMPHASIS>", "<emphasis>").replace(
                        "</EMPHASIS>",
                        "</emphasis>",
                    )
                    text = text.replace("<STRONG>", "<strong>").replace(
                        "</STRONG>",
                        "</strong>",
                    )
                    text = text.replace("<STRIKETHROUGH>", "<strikethrough>").replace(
                        "</STRIKETHROUGH>",
                        "</strikethrough>",
                    )
                    text = text.replace("<SUP>", "<sup>").replace(
                        "</SUP>",
                        "</sup>",
                    )
                    text = text.replace("<SUB>", "<sub>").replace(
                        "</SUB>",
                        "</sub>",
                    )
                    self.parent.text_box.get_buffer().set_text(text)
            elif keyval == Gdk.KEY_space:
                self.parent.text_box.get_buffer().insert_at_cursor(" ")
        return False

    def show_help(self, *args: Any) -> None:
        # TODO Use ui file?
        dialog: Gtk.ShortcutsWindow = Gtk.ShortcutsWindow()

        dialog.set_size_request(500, 500)

        section_one: Gtk.ShortcutsSection = Gtk.ShortcutsSection.new(
            Gtk.Orientation.HORIZONTAL,
        )
        group_one: Gtk.ShortcutsGroup = Gtk.ShortcutsGroup.new(
            Gtk.Orientation.VERTICAL,
        )
        # help_window: Gtk.ShortcutsShortcut = Gtk.ShortcutsShortcut(title="Help", accelerator=)
        # help_window.set_property()
        # help_window.set_title("Help")
        # help_window.set_subtitle("Show help window")
        # group_one.add_shortcut()
        section_one.add_group(group_one)
        dialog.add_section(section_one)

        # Shortcuts
        hbox = Gtk.HBox(False, 10)
        label = Gtk.Label()
        label.set_markup("<b>Shortcuts</b>")
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
        label.set_markup("This help window (F1)")
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_ITALIC)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Add &lt;emphasis> tags (CTRL + e)")
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_GOTO_TOP)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Add &lt;sup&gt; tags (CTRL + p)")
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_STRIKETHROUGH)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Add &lt;strikethrough&gt; tags (CTRL + r)")
        hbox.pack_start(label, False, False, 3)
        left_vbox.pack_start(hbox, False, False, 0)

        main_hbox.pack_start(left_vbox, False, False, 10)

        # right side
        right_vbox = Gtk.VBox(False, 3)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.Button(label="a..A")
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Convert text to uppercase (CTRL + u)")
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_BOLD)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Add &lt;strong&gt; tags (CTRL + s)")
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.ToolButton()
        button.set_stock_id(Gtk.STOCK_GOTO_BOTTOM)
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Add &lt;sub&gt; tags (CTRL + b)")
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        hbox = Gtk.HBox(False, 3)
        button = Gtk.Button(label="a___b")
        hbox.pack_start(button, False, False, 3)
        label = Gtk.Label()
        label.set_markup("Insert non-breaking space (CTRL + space)")
        hbox.pack_start(label, False, False, 3)
        right_vbox.pack_start(hbox, False, False, 0)

        main_hbox.pack_start(right_vbox, False, False, 10)

        dialog.vbox.pack_start(main_hbox, False, False, 0)
        dialog.get_action_area().get_children()[0].grab_focus()

        dialog.present()

    def text_rotation_change(self, widget: Gtk.Scale, text_item: TextLayerItem) -> None:
        new_rotation = widget.get_value()
        text_item.rotation = new_rotation
        self.is_modified = True

    def text_invert_change(self, widget: Gtk.CheckButton, text_item: TextLayerItem) -> None:
        checked = widget.get_active()
        text_item.is_inverted = checked
        self.is_modified = True

    def text_transparent_change(self, widget: Gtk.CheckButton, text_item: TextLayerItem) -> None:
        checked = widget.get_active()
        text_item.is_transparent = checked
        self.is_modified = True

    def text_text_change(self, widget: Gtk.TextBuffer, text_item: TextLayerItem) -> None:
        text = widget.get_text(
            widget.get_bounds()[0],
            widget.get_bounds()[1],
            False,
        )
        text_item.set_property("text", text)
        self.is_modified = True

    def exit(self, widget: Gtk.Button, position: int) -> None:
        if self.is_modified:
            self.parent.text_layer_model.items_changed(position, 0, 0)
