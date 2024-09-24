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
import isocodes


class Language(GObject.Object):
    # lang_iso ISO 639-1
    lang = GObject.Property(type=str)
    lang_iso = GObject.Property(type=str)
    show = GObject.Property(type=bool, default=False)

    def __init__(self, lang: str = "English", lang_iso: str = "en", show: bool = False):
        super().__init__()
        self.lang = lang
        self.lang_iso = lang_iso
        self.show = show


class LanguageDialog(Gtk.Window):
    def __init__(self, parent):
        self.parent = parent
        super().__init__(title='Language Editor')
        self.set_transient_for(parent)
        self.set_size_request(600, 400)

        self.connect("close-request", self.save_and_exit)

        self.is_modified: bool = False

        self.model: Gio.ListStore = Gio.ListStore.new(item_type=Language)

        for lang in self.parent.acbf_document.languages:
            lang_info = isocodes.languages.get(alpha_2=lang[0])
            self.model.append(Language(lang_iso=lang[0], lang=lang_info.get("name"), show=lang[1]))

        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        column_view = Gtk.ColumnView(model=selection_model)
        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new language")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect('clicked', self.add_lang)

        active_factory = Gtk.SignalListItemFactory()
        active_factory.connect("setup", self.setup_active_column)
        active_factory.connect("bind", self.bind_active_column)
        active_factory.connect("unbind", self.unbind_active_column)
        active_column = Gtk.ColumnViewColumn(title="Active", factory=active_factory)
        active_column.set_resizable(True)
        column_view.append_column(active_column)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_lang_iso_column)
        factory.connect("bind", self.bind_lang_iso_column)
        factory.connect("unbind", self.unbind_lang_iso_column)
        column = Gtk.ColumnViewColumn(title="ISO Language", factory=factory)
        column_view.append_column(column)

        lang_factory = Gtk.SignalListItemFactory()
        lang_factory.connect("setup", self.setup_lang_column)
        lang_factory.connect("bind", self.bind_lang_column)
        lang_column = Gtk.ColumnViewColumn(title="Language", factory=lang_factory)
        lang_column.set_expand(True)
        lang_column.set_resizable(True)
        column_view.append_column(lang_column)

        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(title="Delete", factory=delete_factory)
        column_view.append_column(delete_column)

        self.set_child(column_view)

    def setup_active_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry = Gtk.CheckButton()
        entry.set_halign(Gtk.Align.CENTER)
        list_item.set_child(entry)

    def setup_lang_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry = Gtk.Label()
        entry.set_halign(Gtk.Align.START)
        entry.set_margin_start(3)
        list_item.set_child(entry)

    def setup_lang_iso_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry = Gtk.DropDown()
        entry.set_model(self.parent.all_langs)
        entry.set_enable_search(True)
        expression = Gtk.PropertyExpression.new(Language, None, "lang_iso")
        entry.set_expression(expression)
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
        list_item.set_child(button)

    def bind_active_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Language = list_item.get_item()
        entry: Gtk.CheckButton = list_item.get_child()
        entry.set_active(item.show)
        entry.connect("toggled", self.active_toggle, item)

    def unbind_active_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.CheckButton = list_item.get_child()
        entry.disconnect_by_func(self.active_toggle)

    def bind_lang_iso_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Language = list_item.get_item()
        entry: Gtk.DropDown = list_item.get_child()
        position = self.compare_lang(item, entry.get_model())
        entry.set_selected(position)
        entry.connect("notify::selected", self.lang_iso_change, item)

    def unbind_lang_iso_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.lang_iso_change)

    def bind_lang_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        item.bind_property("lang", entry, "label", GObject.BindingFlags.SYNC_CREATE)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        position = list_item.get_position()
        button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, position)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        button: Gtk.Button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def active_toggle(self, widget: Gtk. CheckButton, item):
        item.show = widget.get_active()
        self.set_modified()

    def on_delete_button_clicked(self, button: Gtk.Button, position: int):
        self.model.remove(position)
        self.set_modified()

    def add_lang(self, button):
        self.model.append(Language())
        self.set_modified()

    def lang_iso_change(self, widget: Gtk.DropDown, _pspec, item: Language):
        item.lang_iso = widget.get_selected_item().lang_iso
        lang_info = isocodes.languages.get(alpha_2=item.lang_iso)
        item.lang = lang_info.get("name")
        position = widget.get_selected()
        self.model.items_changed(position, 0, 0)

    def compare_lang(self, item: GObject, model: Gio.ListStore):
        lang_iso = item.lang_iso
        if lang_iso is None:
            # Use currently set language
            lang_iso = self.parent.lang_button.get_selected_item().lang_iso
        position = 0
        i = 0
        while i < 999:
            lang = model.get_item(i)
            if lang is None:
                break
            if lang_iso == lang.lang_iso:
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

    def save_and_exit(self, widget: Gtk.Button):
        # The whole "only one of language" thing wasn't followed by creator, so we won't enforce it for now
        if self.is_modified:
            self.parent.acbf_document.languages.clear()
            i = 0
            while i < 9999:
                lang: Language = self.model.get_item(i)
                if lang is None:
                    break

                self.parent.acbf_document.languages.append((lang.lang_iso, lang.show))
                i = i + 1

            self.parent.lang_widget_update()
            self.parent.modified()
        self.close()
