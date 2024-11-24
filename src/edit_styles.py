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

import pathlib

import fontselectiondialog
import gi
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from PIL import ImageFont

gi.require_version("Gtk", "4.0")


class FontItem(GObject.Object):
    sematic = GObject.Property(type=str)
    font = GObject.Property(type=str)
    font_filename = GObject.Property(type=str)
    font_families = GObject.Property(type=str)
    colour = GObject.Property(type=str)
    path = GObject.Property(type=str)

    def __init__(self, sematic: str, font: str, font_filename: str, font_families: str, colour: str, path: str):
        super().__init__()
        self.sematic = sematic
        self.font = font
        self.font_filename = font_filename
        self.font_families = font_families
        self.colour = colour
        self.path = path


class EditStylesWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        super().__init__(title="Edit Styles/Font Definitions")
        self.parent = parent
        self.is_modified: bool = False
        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        self.model: Gio.ListStore = Gio.ListStore(item_type=FontItem)

        for k, v in self.parent.acbf_document.font_styles.items():
            font_path = pathlib.Path(v)
            font = ImageFont.truetype(font_path)
            font_name = font.getname()
            font_name = f"{font_name[0]} ({font_name[1]})"
            # font = font_path.stem.split("-")[0]
            font_familes = self.parent.acbf_document.font_families[k]
            colour = self.parent.acbf_document.font_colors.get(k, "#000000")
            self.model.append(
                FontItem(
                    sematic=k,
                    font=font_name,
                    font_filename=font_path.stem.split("/")[0],
                    font_families=font_familes,
                    colour=colour,
                    path=v,
                ),
            )

        selection_model = Gtk.NoSelection(model=self.model)

        column_view = Gtk.ColumnView(model=selection_model)

        sematic_factory = Gtk.SignalListItemFactory()
        sematic_factory.connect("setup", self.setup_sematic_column)
        sematic_factory.connect("bind", self.bind_sematic_column)
        sematic_column = Gtk.ColumnViewColumn(title="Title", factory=sematic_factory)
        sematic_column.set_resizable(True)
        column_view.append_column(sematic_column)

        font_factory = Gtk.SignalListItemFactory()
        font_factory.connect("setup", self.setup_font_column)
        font_factory.connect("bind", self.bind_font_column)
        font_factory = Gtk.ColumnViewColumn(title="Font", factory=font_factory)
        font_factory.set_resizable(True)
        font_factory.set_expand(True)
        column_view.append_column(font_factory)

        colour_factory = Gtk.SignalListItemFactory()
        colour_factory.connect("setup", self.setup_colour_column)
        colour_factory.connect("bind", self.bind_colour_column)
        colour_factory = Gtk.ColumnViewColumn(title="Colour", factory=colour_factory)
        column_view.append_column(colour_factory)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_child(column_view)

        self.set_size_request(500, 600)
        self.set_child(scrolled_window)

    def setup_sematic_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Label = Gtk.Label()
        entry.set_margin_start(5)
        entry.set_margin_end(5)
        entry.set_margin_top(5)
        entry.set_margin_bottom(5)
        list_item.set_child(entry)

    def setup_font_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Button = Gtk.Button()
        list_item.set_child(entry)

    def setup_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        list_item.set_child(button)

    def bind_sematic_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        entry = list_item.get_child()
        entry.set_text(item.sematic.capitalize() or "")

    def bind_font_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item: FontItem = list_item.get_item()
        entry: Gtk.FontDialogButton = list_item.get_child()
        entry.connect("clicked", self.font_button_click, item)
        item.bind_property("font", entry, "label", GObject.BindingFlags.SYNC_CREATE)

    def unbind_font_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.FontDialogButton = list_item.get_child()
        entry.disconnect_by_func(self.font_button_click)

    def bind_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        button = list_item.get_child()
        colour = Gdk.RGBA()
        colour.parse(item.colour)
        button.set_rgba(colour)
        button.connect("notify::rgba", self.set_font_color, item)

    def unbind_colour_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.ColorDialogButton = list_item.get_child()
        entry.disconnect_by_func(self.set_font_color)

    def font_button_click(self, widget: Gtk.Button, item: FontItem) -> None:
        chooser = fontselectiondialog.FontSelectionOldDialog(self, self.parent.acbf_document.fonts_dir, item)
        chooser.present()

    def set_font_color(self, widget: Gtk.ColorDialogButton, _pspec: GObject.GParamSpec, item: FontItem) -> None:
        font_type = item.sematic
        if font_type == "normal":
            font_type = "speech"

        self.parent.acbf_document.font_colors[font_type] = widget.get_rgba().to_string()
        self.set_modified()

    def set_modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)
            self.parent.modified()

    def save_and_exit(self, widget: Gtk.Button) -> None:
        self.close()
