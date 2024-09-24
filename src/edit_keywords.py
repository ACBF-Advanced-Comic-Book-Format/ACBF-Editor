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
from gi.repository import Gtk, Gio, GObject


class Keyword(GObject.Object):
    __gtype_name__ = "Keyword"
    keyword = GObject.Property(type=str)

    def __init__(self, keyword: str = ""):
        super().__init__()
        self.keyword = keyword


class KeywordsDialog(Gtk.Window):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(title="Edit Keywords")
        self.set_size_request(600, 400)
        self.set_transient_for(parent)

        self.is_modified: bool = False

        self.model: Gio.ListStore = Gio.ListStore.new(item_type=Keyword)

        for keyword in self.parent.acbf_document.keywords:
            if keyword:
                self.model.append(Keyword(keyword=keyword))

        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        column_view = Gtk.ColumnView(model=selection_model)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new keyword")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect('clicked', self.add_keyword)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_keyword_column)
        factory.connect("bind", self.bind_keyword_column)
        factory.connect("unbind", self.unbind_keyword_column)
        column = Gtk.ColumnViewColumn(title="Keyword", factory=factory)
        column.set_expand(True)
        column.set_resizable(True)
        column_view.append_column(column)

        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(title="Delete", factory=delete_factory)
        column_view.append_column(delete_column)

        self.connect("close-request", self.save_and_exit)
        self.set_child(column_view)

    def setup_keyword_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.Entry = Gtk.Entry()
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button: Gtk.Button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(button)

    def bind_keyword_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Keyword = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(item.keyword)
        entry.connect("changed", self.text_changed, item)

    def unbind_keyword_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.text_changed)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        position = list_item.get_position()
        button: Gtk.Button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, position)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button: Gtk.Button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def text_changed(self, entry: Gtk.Entry, item: Keyword):
        item.keyword = entry.get_text()
        self.set_modified()

    def on_delete_button_clicked(self, button: Gtk.Button, position: int):
        self.model.remove(position)
        self.set_modified()

    def add_keyword(self, button):
        self.model.append(Keyword())
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
            self.parent.acbf_document.keywords.clear()
            i = 0
            while i < 9999:
                keyword: Keyword = self.model.get_item(i)
                if keyword is None:
                    break
                word = keyword.keyword
                self.parent.acbf_document.keywords.append(word)
                i = i + 1

            self.parent.keywords_widget_update()
            self.parent.modified()
        self.close()
