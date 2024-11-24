"""fontselectiondialog.py - Miscellaneous constants.

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

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from typing import Any
# from edit_styles import FontItem  # circular import atm

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class FontFileItem(GObject.Object):
    label = GObject.Property(type=str)
    style = GObject.Property(type=str)
    name = GObject.Property(type=str)
    path = GObject.Property(type=str)

    def __init__(self, label: str, style: str, name: str, path: str):
        super().__init__()
        self.label = label
        self.style = style
        self.name = name
        self.path = path


class FontSelectionOldDialog(Gtk.Window):
    """Font Selection dialog."""

    # TODO Integrate system font picker (somehow)
    def __init__(self, parent: Gtk.Window, font_dir: str, selected_font: Any):
        super().__init__(title="Font Selection (comic 'Fonts' directory)")
        self.set_transient_for(parent)
        self.parent = parent
        self.font_directory = font_dir
        self.selected_font = selected_font
        self.selected_item: int = -1
        self.set_default_size(350, 400)

        content: Gtk.Box = Gtk.Box.new(Gtk.Orientation.VERTICAL, spacing=0)

        # list of available fonts
        sw = Gtk.ScrolledWindow()
        sw.set_size_request(250, 200)

        content.append(sw)

        self.font_image = Gtk.Picture()
        self.font_image.set_size_request(-1, 40)

        content.append(self.font_image)

        action_bar = Gtk.ActionBar()
        okay_button: Gtk.Button = Gtk.Button.new_with_label("Okay")
        cancel_button: Gtk.Button = Gtk.Button.new_with_label("Cancel")

        okay_button.connect("clicked", self.okay_clicked)
        cancel_button.connect("clicked", self.cancel_clicked)

        action_bar.pack_start(okay_button)
        action_bar.pack_end(cancel_button)

        content.append(action_bar)

        self.treestore: Gio.ListStore = Gio.ListStore.new(item_type=FontFileItem)

        font_list_factory = Gtk.SignalListItemFactory()
        font_list_factory.connect("setup", self.setup_font_item)
        font_list_factory.connect("bind", self.bind_font_item)

        selection_model: Gtk.SingleSelection = Gtk.SingleSelection.new(self.treestore)

        font_view: Gtk.ListView = Gtk.ListView.new(selection_model, font_list_factory)
        font_view.set_single_click_activate(True)
        font_view.connect("activate", self.tree_item_selected)

        for font_file in os.listdir(self.font_directory):
            if font_file.lower().endswith(".ttf") or font_file.lower().endswith(".otf"):
                try:
                    font_path = os.path.join(self.font_directory, font_file)
                    font = ImageFont.truetype(font_path)
                    label = font.getname()
                    self.treestore.append(
                        FontFileItem(
                            label=label[0],
                            style=label[1],
                            name=font_file,
                            path=font_path,
                        ),
                    )
                except OSError as e:
                    logging.error(f"Failed to read font file: {font_file} error: {e}")
                except Exception as e:
                    logging.error(f"Failed to load font file: {font_file} error: {e}")

        sw.set_child(font_view)

        # Find current font in list and select
        i = 0
        while i < 999:
            font_item: FontFileItem = self.treestore.get_item(i)
            if font_item is None:
                break

            if font_item.path == selected_font.path:
                font_view.scroll_to(i, Gtk.ListScrollFlags.SELECT)
                break
            i = i + 1

        self.set_child(content)

    def setup_font_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        entry = Gtk.Label()
        entry.set_margin_start(5)
        entry.set_margin_end(5)
        list_item.set_child(entry)

    def bind_font_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item: FontFileItem = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        label = f"{item.label} ({item.style})"
        entry.set_text(label)

    def tree_item_selected(self, list_view: Gtk.ListView, selection: int) -> None:
        item: FontFileItem = self.treestore.get_item(selection)
        self.selected_item = selection
        self.gen_font_preview(item.path)

    def gen_font_preview(self, font_path: str) -> None:
        font_image = Image.new("RGB", (550, 45), "#fff")
        draw = ImageDraw.Draw(font_image)
        font = ImageFont.truetype(font_path, 20)
        draw.text(
            (10, 10),
            "The Quick Brown Fox Jumped Over The Lazy Dog",
            font=font,
            fill="#000",
        )

        pixbuf_image = self.parent.parent.pil_to_pixbuf(font_image)
        self.font_image.set_pixbuf(pixbuf_image)

    def okay_clicked(self, widget: Gtk.Button) -> None:
        if self.selected_item > -1:
            font: FontFileItem = self.treestore.get_item(self.selected_item)
            self.parent.parent.acbf_document.font_styles[self.selected_font.sematic] = font.path
            model: Gio.ListStore = self.parent.model
            found, position = model.find(self.selected_font)
            if found:
                item = model.get_item(position)
                # TODO Keep fallback and only replace first item rather than acbfdocument.savetree?
                item.font = font.label
            self.parent.set_modified()
        self.close()

    def cancel_clicked(self, widget: Gtk.Button) -> None:
        self.close()
