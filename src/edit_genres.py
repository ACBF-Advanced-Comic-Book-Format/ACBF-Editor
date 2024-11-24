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

import constants
import gi
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

gi.require_version("Gtk", "4.0")


class Genre(GObject.Object):
    name = GObject.Property(type=str)
    active = GObject.Property(type=bool, default=False)
    match = GObject.Property(type=int)

    def __init__(self, name: str, active: bool, match: int):
        super().__init__()
        self.name = name
        self.active = active
        self.match = match

    def __str__(self) -> str:
        return self.name


def sort_genres(genre1: Genre, genre2: Genre) -> int:
    # First compare by 'active' property (False before True)
    if genre1.get_property("active") != genre2.get_property("active"):
        return -1 if genre1.get_property("active") else 1
    # If 'active' is the same, compare by 'name' property
    return (genre1.get_property("name") > genre2.get_property("name")) - (
        genre1.get_property("name") < genre2.get_property("name")
    )


class GenresDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        self.parent = parent
        super().__init__(title="Genres Editor")
        self.set_transient_for(parent)
        self.set_size_request(600, 400)

        self.is_modified: bool = False

        self.connect("close-request", self.save_and_exit)
        self.model: Gio.ListStore = Gio.ListStore(item_type=Genre)

        for genre in sorted(constants.GENRES_LIST):
            name: str = genre.replace("_", " ").capitalize()
            active: bool = False
            match: int = 0
            # Get any set values
            for g in self.parent.acbf_document.genres:
                if g[0] == genre:
                    active = True
                    match = g[1]

            self.model.append(Genre(name=name, active=active, match=match))

        self.model.sort(sort_genres)
        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        column_view = Gtk.ColumnView(model=selection_model)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        active_factory = Gtk.SignalListItemFactory()
        active_factory.connect("setup", self.setup_active_column)
        active_factory.connect("bind", self.bind_active_column)
        active_factory.connect("unbind", self.unbind_active_column)
        active_column = Gtk.ColumnViewColumn(title="Active", factory=active_factory)
        active_column.set_resizable(True)
        column_view.append_column(active_column)

        name_factory = Gtk.SignalListItemFactory()
        name_factory.connect("setup", self.setup_name_column)
        name_factory.connect("bind", self.bind_name_column)
        name_factory.connect("unbind", self.unbind_name_column)
        name_column = Gtk.ColumnViewColumn(title="Genre", factory=name_factory)
        name_column.set_expand(True)
        name_column.set_resizable(True)
        column_view.append_column(name_column)

        match_factory = Gtk.SignalListItemFactory()
        match_factory.connect("setup", self.setup_match_column)
        match_factory.connect("bind", self.bind_match_column)
        match_factory.connect("unbind", self.unbind_match_column)
        match_column = Gtk.ColumnViewColumn(title="Match Quantity", factory=match_factory)
        match_column.set_resizable(True)
        column_view.append_column(match_column)

        self.set_child(column_view)

    def setup_active_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.CheckButton = Gtk.CheckButton()
        entry.set_halign(Gtk.Align.CENTER)
        list_item.set_child(entry)

    def setup_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Label = Gtk.Label()
        entry.set_halign(Gtk.Align.START)
        entry.set_margin_start(3)
        list_item.set_child(entry)

    def setup_match_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.SpinButton = Gtk.SpinButton()
        entry.set_range(0, 100)
        entry.set_increments(1, 10)
        entry.set_width_chars(5)
        entry.set_alignment(1)
        list_item.set_child(entry)

    def bind_active_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        item: Genre = list_item.get_item()
        entry: Gtk.CheckButton = list_item.get_child()
        entry.set_active(item.active)
        entry.connect("toggled", self.genre_activate, item)

    def unbind_active_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.CheckButton = list_item.get_child()
        entry.disconnect_by_func(self.genre_activate)

    def bind_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        item: Genre = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Label = list_item.get_child()
        checkbox: Gtk.CheckButton = entry.get_parent().get_prev_sibling().get_first_child()
        entry.set_text(item.name or "")

        click_controller = Gtk.GestureClick()
        click_controller.set_button(1)
        click_controller.connect("pressed", self.label_clicked, item, position, checkbox)
        entry.add_controller(click_controller)

    def unbind_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ColumnViewCell) -> None:
        # TODO Unbind click
        item: Genre = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Label = list_item.get_child()
        checkbox: Gtk.CheckButton = entry.get_parent().get_prev_sibling().get_first_child()

        click_controller = Gtk.GestureClick()
        click_controller.set_button(1)
        click_controller.connect("pressed", self.label_clicked, item, position, checkbox)
        entry.add_controller(click_controller)

    def bind_match_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        item: Genre = list_item.get_item()
        entry: Gtk.SpinButton = list_item.get_child()
        entry.set_value(item.match)
        entry.connect("value-changed", self.match_change, item)

    def unbind_match_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.SpinButton = list_item.get_child()
        entry.disconnect_by_func(self.match_change)

    def genre_activate(self, widget: Gtk.CheckButton, item: Genre) -> None:
        active = widget.get_active()
        item.active = active
        self.model.sort(sort_genres)
        self.is_modified = True

    def match_change(self, widget: Gtk.SpinButton, item: Genre) -> None:
        match = widget.get_value()
        item.match = match
        self.is_modified = True

    def label_clicked(
        self,
        gesture: Gtk.GestureClick,
        presses: int,
        x: int,
        y: int,
        item: Genre,
        position: int,
        checkbox: Gtk.CheckButton,
    ) -> None:
        active = True
        if item.active:
            active = False

        item.active = active
        checkbox.set_active(active)
        found, position = self.model.find(item)
        if found:
            self.model.items_changed(position, 0, 0)
            self.is_modified = True

    def set_modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save(self) -> None:
        self.parent.acbf_document.genres.clear()
        i = 0
        while i < 1000:
            row: Genre = self.model.get_item(i)
            if row is None:
                break
            if row.active:
                self.parent.acbf_document.genres.append(
                    (row.name.lower().replace(" ", "_"), row.match),
                )
            i = i + 1

        self.parent.modified()

    def save_and_exit(self, widget: Gtk.Button) -> None:
        if self.is_modified:
            self.save()
            self.parent.genre_widget_update()
            self.parent.modified()
        self.close()
