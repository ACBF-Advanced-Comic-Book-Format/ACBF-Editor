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
import constants
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GObject
from edit_languages import Language


class Author(GObject.Object):
    activity = GObject.Property(type=str)
    language = GObject.Property(type=str)
    first_name = GObject.Property(type=str)
    middle_name = GObject.Property(type=str)
    last_name = GObject.Property(type=str)
    nickname = GObject.Property(type=str)
    home_page = GObject.Property(type=str)
    email = GObject.Property(type=str)

    def __init__(self, activity, language, first_name, middle_name, last_name, nickname, home_page, email):
        super().__init__()
        self.activity = activity
        self.language = language
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.nickname = nickname
        self.home_page = home_page
        self.email = email

    def __str__(self):
        if self.first_name and self.last_name:
            return self.first_name + " " + self.last_name
        elif self.nickname:
            return self.nickname
        else:
            return self.first_name or self.last_name or ""

    def _dict(self) -> dict[str, str]:
        return {"activity": self.activity, "language": self.language, "first_name": self.first_name,
                "middle_name": self.middle_name, "last_name": self.last_name, "nickname": self.nickname,
                "home_page": self.home_page, "email": self.email}


class AuthorsDialog(Gtk.Window):
    def __init__(self, parent, doc_auth: bool = False):
        self.parent = parent
        super().__init__()
        self.set_transient_for(parent)
        self.set_size_request(600, 400)

        self.is_modified: bool = False

        self.connect("close-request", self.save_and_exit)

        self.model = Gio.ListStore.new(item_type=Author)

        self.authors = self.parent.acbf_document.doc_authors if doc_auth else self.parent.acbf_document.authors

        for author in self.authors:
            author_record = Author(activity=author.get("activity"), language=author.get("language"),
                                   first_name=author.get("first_name"), middle_name=author.get("middle_name"),
                                   last_name=author.get("last_name"),
                                   nickname=author.get("nickname"), home_page=author.get("home_page"),
                                   email=author.get("email"))
            self.model.append(author_record)
    
        selection_model = Gtk.NoSelection(model=self.model)

        column_view = Gtk.ColumnView(model=selection_model)
        #column_view_row_factory: Gtk.ListItemFactory = column_view.get_row_factory()
        #column_view_row_factory
        column_view.set_show_column_separators(True)
        column_view.set_show_row_separators(True)

        toolbar_header = Gtk.HeaderBar()
        self.set_title("Edit Author(s)")

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new record")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect('clicked', self.add_author)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_activity_column)
        factory.connect("bind", self.bind_activity_column, "activity")
        factory.connect("unbind", self.unbind_activity_column)
        column = Gtk.ColumnViewColumn(title="Activity", factory=factory)
    
        column_view.append_column(column)
    
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_language_column)
        factory.connect("bind", self.bind_language_column)
        factory.connect("unbind", self.unbind_language_column)
        column = Gtk.ColumnViewColumn(title="Language", factory=factory)
        column_view.append_column(column)
    
        text_columns = [
            ("First Name", "first_name"),
            ("Middle Name", "middle_name"),
            ("Last Name", "last_name"),
            ("Nickname", "nickname"),
            ("Home Page", "home_page"),
            ("Email", "email")
        ]
    
        for title, attribute in text_columns:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self.setup_editable_column)
            factory.connect("bind", self.bind_editable_column, attribute)
            factory.connect("unbind", self.unbind_editable_column)
            column = Gtk.ColumnViewColumn(title=title, factory=factory)
            column.set_resizable(True)
            column_view.append_column(column)

        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(title="Delete", factory=delete_factory)
        column_view.append_column(delete_column)

        self.set_titlebar(toolbar_header)
        self.set_child(column_view)
        self.set_size_request(1000, 600)

    def setup_editable_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry = Gtk.Entry()
        list_item.set_child(entry)

    def setup_activity_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        gtk_lang_list = Gtk.StringList.new(constants.AUTHORS_LIST)
        entry = Gtk.DropDown()
        entry.set_show_arrow(True)
        entry.set_model(gtk_lang_list)
        entry.set_enable_search(True)
        expression = Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
        entry.set_expression(expression)
        list_item.set_child(entry)

    def setup_language_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry = Gtk.DropDown()
        entry.set_model(self.parent.all_langs)
        entry.set_enable_search(True)
        expression = Gtk.PropertyExpression.new(Language, None, "lang")
        entry.set_expression(expression)
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(button)
    
    def bind_editable_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem, attribute):
        item: Author = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(getattr(item, attribute) or "")
        entry.connect("changed", self.text_changed, item, attribute)

    def unbind_editable_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.text_changed)

    def bind_activity_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem, attribute):
        item: Author = list_item.get_item()
        entry: Gtk.DropDown = list_item.get_child()
        entry.set_selected(constants.AUTHORS_LIST.index(getattr(item, attribute) or constants.AUTHORS_LIST[0]))
    
        entry.connect("notify::selected", self.activity_change, item)

    def unbind_activity_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.activity_change)

    def bind_language_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Author = list_item.get_item()
        entry: Gtk.DropDown = list_item.get_child()
        entry.set_sensitive(False)
        position = self.compare_lang(item, entry.get_model())
        entry.set_selected(position)
        if item.activity == "Translator":
            entry.set_sensitive(True)
        entry.connect("notify::selected", self.lang_change, item)

    def unbind_language_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.lang_change)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Author = list_item.get_item()
        button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, item)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def on_delete_button_clicked(self, button, item):
        found, position = self.model.find(item)
        if found:
            self.model.remove(position)
            self.set_modified()
    
    def add_author(self, button):
        blank = Author(activity="Writer", language="", first_name="", middle_name="", last_name="", nickname="", home_page="", email="")
        self.model.append(blank)

    def text_changed(self, entry: Gtk.Entry, item: Author, attribute: str):
        # Do not trigger a model updated otherwise the text will highlight
        setattr(item, attribute, entry.get_text())
        self.set_modified()

    def lang_change(self, button: Gtk.DropDown, _pspec,  item: Author):
        item.language = button.get_selected_item().lang_iso
        self.set_modified()

    def activity_change(self, button: Gtk.DropDown, _pspec,  item: Author):
        # Don't trigger model change
        item.activity = button.get_selected_item().get_string().capitalize()
        self.set_modified()

    def compare_lang(self, item: Author, model: Gio.ListStore):
        lang_iso = item.language
        if lang_iso is None:
            # If not the translator for a language, use currently set language
            lang_iso = self.parent.lang_button.get_selected_item().lang_iso
        position = 0
        i = 0
        while i < 999:
            author = model.get_item(i)
            if author is None:
                break
            if lang_iso == author.lang_iso:
                position = i
                break
            i = i + 1

        return position

    def set_modified(self, modified: bool = True):
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save(self) -> None:
        self.authors.clear()
        i = 0
        while i < 1000:
            row: Author = self.model.get_item(i)
            if row is None:
                break

            self.authors.append(row._dict())
            i = i + 1

        self.parent.modified()

    def save_and_exit(self, widget: Gtk.Button):
        if self.is_modified:
            self.save()
            self.parent.authors_widget_update()
            self.parent.doc_authors_widget_update()
            self.parent.modified()
        self.close()
        return False
