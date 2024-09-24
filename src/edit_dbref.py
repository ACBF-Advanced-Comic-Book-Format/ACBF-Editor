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


class DBRef(GObject.Object):
    dbname = GObject.Property(type=str)
    dbtype = GObject.Property(type=str)
    value = GObject.Property(type=str)

    def __init__(self, dbname: str = "", dbtype: str = "", value: str = ""):
        super().__init__()
        self.dbname = dbname
        self.dbtype = dbtype
        self.value = value

    def _dict(self) -> dict[str, str]:
        return {"dbname": self.dbname, "dbtype": self.dbtype, "value": self.value}


class DBRefDialog(Gtk.Window):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(title='Database Reference Editor')
        self.set_transient_for(parent)
        self.set_size_request(600, 400)

        self.is_modified: bool = False

        self.connect("close-request", self.save_and_exit)

        self.model = Gio.ListStore.new(item_type=DBRef)

        for ref in self.parent.acbf_document.databaseref:
            self.model.append(DBRef(ref["dbname"], ref["dbtype"], ref["value"]))

        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        self.model.connect("items_changed", self.model_change)

        column_view = Gtk.ColumnView(model=selection_model)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new reference")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect('clicked', self.add_ref)

        text_columns = [
            ("Name", "dbname"),
            ("Value", "value"),
        ]

        for title, attribute in text_columns:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self.setup_text_column)
            factory.connect("bind", self.bind_text_column, attribute)
            factory.connect("unbind", self.unbind_text_column)
            column = Gtk.ColumnViewColumn(title=title, factory=factory)
            column.set_resizable(True)
            column.set_expand(True)
            column_view.append_column(column)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_type_column)
        factory.connect("bind", self.bind_type_column)
        factory.connect("unbind", self.unbind_type_column)
        column = Gtk.ColumnViewColumn(title="Type", factory=factory)
        column.set_resizable(True)
        column_view.append_column(column)

        # Add delete button column
        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(title="Delete", factory=delete_factory)
        column_view.append_column(delete_column)

        self.set_child(column_view)

    def setup_text_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.Entry = Gtk.Entry()
        list_item.set_child(entry)

    def setup_type_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.DropDown = Gtk.DropDown.new_from_strings(["", "URL", "IssueID", "SeriesID", "Other"])
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(button)

    def bind_text_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem, attribute: str):
        item: DBRef = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(getattr(item, attribute) or "")
        entry.connect("changed", self.text_changed, item, attribute)

    def unbind_text_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.text_changed)

    def bind_type_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: DBRef = list_item.get_item()
        entry: Gtk.DropDown = list_item.get_child()
        dd_model: Gtk.StringList = entry.get_model()
        position = 0
        i = 0
        while i < 999:
            dbtype = dd_model.get_item(i)
            if dbtype is None:
                break
            if dbtype.get_string() == item.dbtype:
                position = i
                break
            i = i + 1

        entry.set_selected(position)
        entry.connect("notify::selected", self.type_changed, item)

    def unbind_type_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.type_changed)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        position = list_item.get_position()
        button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, position)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button: Gtk.Button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def text_changed(self, entry: Gtk.Entry, item: DBRef, attribute: str):
        # Do not trigger a model updated otherwise the text will highlight
        setattr(item, attribute, entry.get_text())
        self.set_modified()

    def type_changed(self, entry: Gtk.DropDown, _pspec, item: DBRef):
        item.dbtype = entry.get_selected_item().get_string()
        self.set_modified()

    def on_delete_button_clicked(self, button: Gtk.Button, position: int):
        self.model.remove(position)

    def add_ref(self, button):
        self.model.append(DBRef())

    def model_change(self, list_model: Gio.ListStore, position: int, removed: int, added: int):
        self.set_modified()

    def set_modified(self, modified: bool = True):
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save(self) -> None:
        self.parent.acbf_document.databaseref.clear()
        i = 0
        while i < 1000:
            row: DBRef = self.model.get_item(i)
            if row is None:
                break

            self.parent.acbf_document.databaseref.append(row._dict())
            i = i + 1

        self.parent.modified()

    def save_and_exit(self, widget: Gtk.Button):
        if self.is_modified:
            self.save()
            self.parent.dbref_widget_update()
        self.close()
