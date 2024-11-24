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

import gi
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

gi.require_version("Gtk", "4.0")


class Rating(GObject.Object):
    name = GObject.Property(type=str)
    type = GObject.Property(type=str)

    def __init__(self, name: str = "", type: str = ""):
        super().__init__()
        self.name = name
        self.type = type


class ContentRatingsDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        self.parent = parent
        super().__init__(title="Edit Content Ratings")
        self.set_size_request(600, 400)
        self.set_transient_for(parent)

        self.is_modified: bool = False

        self.connect("close-request", self.save_and_exit)

        self.model: Gio.ListStore = Gio.ListStore.new(item_type=Rating)

        for rating in self.parent.acbf_document.content_ratings:
            self.model.append(Rating(name=rating[1], type=rating[0]))

        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        column_view = Gtk.ColumnView(model=selection_model)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new rating")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect("clicked", self.add_rating)

        name_factory = Gtk.SignalListItemFactory()
        name_factory.connect("setup", self.setup_name_column)
        name_factory.connect("bind", self.bind_type_column, "type")
        name_column = Gtk.ColumnViewColumn(
            title="Rating Type",
            factory=name_factory,
        )
        name_column.set_expand(True)
        name_column.set_resizable(True)
        column_view.append_column(name_column)

        type_factory = Gtk.SignalListItemFactory()
        type_factory.connect("setup", self.setup_type_column)
        type_factory.connect("bind", self.bind_type_column, "name")
        type_factory.connect("unbind", self.unbind_type_column)
        type_column = Gtk.ColumnViewColumn(title="Content Rating", factory=type_factory)
        type_column.set_resizable(True)
        column_view.append_column(type_column)

        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(title="Delete", factory=delete_factory)
        column_view.append_column(delete_column)

        self.set_child(column_view)

    def setup_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Entry = Gtk.Entry()
        list_item.set_child(entry)

    def setup_type_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Entry = Gtk.Entry()
        entry.set_width_chars(5)
        entry.set_alignment(1)
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        button: Gtk.Button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(button)

    def bind_type_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem, attribute: str) -> None:
        item = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(getattr(item, attribute) or "")
        entry.connect("changed", self.text_changed, item, attribute)

    def unbind_type_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.text_changed)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        position = list_item.get_position()
        button: Gtk.Button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, position)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        button: Gtk.Button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def text_changed(self, entry: Gtk.Entry, item: Rating, attribute: str) -> None:
        # Do not trigger a model updated otherwise the text will highlight
        setattr(item, attribute, entry.get_text())
        self.set_modified()

    def on_delete_button_clicked(self, button: Gtk.Button, position: int) -> None:
        self.model.remove(position)
        self.set_modified()

    def add_rating(self, button: Gtk.Button) -> None:
        blank = Rating()
        self.model.append(blank)
        self.set_modified()

    def set_modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save(self) -> None:
        self.parent.acbf_document.content_ratings.clear()
        i = 0
        while i < 1000:
            row: Rating = self.model.get_item(i)
            if row is None:
                break

            self.parent.acbf_document.content_ratings.append(
                (row.type, row.name),
            )
            i = i + 1

        self.parent.modified()

    def save_and_exit(self, widget: Gtk.Button) -> None:
        if self.is_modified:
            self.save()
            self.parent.modified()
            self.parent.rating_widget_update()
        self.close()
