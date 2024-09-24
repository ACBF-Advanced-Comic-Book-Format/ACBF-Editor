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

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gio


class Character(GObject.Object):
    __gtype_name__ = "Character"
    name = GObject.Property(type=str)

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name


class CharacterDialog(Gtk.Window):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(title="Edit Characters")
        self.set_size_request(600, 400)
        self.set_transient_for(parent)

        self.is_modified: bool = False

        # Create a ListStore model rather than StringList for easier updating etc.
        self.model: Gio.ListStore = Gio.ListStore.new(item_type=Character)

        for char in self.parent.acbf_document.characters:
            if char:
                self.model.append(Character(name=char))

        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        column_view = Gtk.ColumnView(model=selection_model)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new character")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect('clicked', self.add_character)

        name_factory = Gtk.SignalListItemFactory()
        name_factory.connect("setup", self.setup_name_column)
        name_factory.connect("bind", self.bind_name_column)
        name_factory.connect("unbind", self.unbind_name_column)
        name_column = Gtk.ColumnViewColumn(title="Name", factory=name_factory)
        name_column.set_expand(True)
        name_column.set_resizable(True)
        column_view.append_column(name_column)

        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(title="Delete", factory=delete_factory)
        column_view.append_column(delete_column)

        self.connect("close-request", self.save_and_exit)
        self.set_child(column_view)

    def setup_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry = Gtk.Entry()
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(button)

    def bind_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Gtk.StringList = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(item.name)
        entry.connect("changed", self.text_changed, item)

    def unbind_name_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.text_changed)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        position = list_item.get_position()
        button: Gtk.Button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, position)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button: Gtk.Button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def text_changed(self, entry: Gtk.Entry, item: Character):
        item.name = entry.get_text()
        self.set_modified()

    def on_delete_button_clicked(self, button: Gtk.Button, position: int):
        self.model.remove(position)
        self.set_modified()

    def add_character(self, button):
        self.model.append(Character())
        self.set_modified()

    def set_modified(self, modified: bool = True):
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save_and_exit(self, widget):
        if self.is_modified:
            self.parent.acbf_document.characters.clear()
            i = 0
            while i < 9999:
                char: Character = self.model.get_item(i)
                if char is None:
                    break
                name = char.name
                self.parent.acbf_document.characters.append(name)
                i = i + 1

            self.parent.char_widget_update()
            self.parent.modified()
        self.close()
