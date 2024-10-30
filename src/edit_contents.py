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
import lxml.etree as xml
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

gi.require_version("Gtk", "4.0")


class ContentItem(GObject.Object):
    title = GObject.Property(type=str)
    page = GObject.Property(type=str)

    def __init__(self, title: str = "", page: str = ""):
        super().__init__()
        self.title = title
        self.page = page


class EditContentWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        self.parent = parent
        super().__init__(title="Edit Contents")
        self.set_transient_for(parent)

        self.is_modified: bool = False
        self.previous_lang: int = 0
        self.page_image_names: list[str] = []

        self.model: Gio.ListStore = Gio.ListStore(item_type=ContentItem)
        # Text Layers switch
        self.contents_languages: list[str] = []
        try:
            for item in parent.acbf_document.tree.findall("meta-data/book-info/languages/text-layer"):
                if item.get("lang") not in self.contents_languages:
                    self.contents_languages.append(item.get("lang"))
        except Exception:
            pass

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        new_button = Gtk.Button(label="Add")
        new_button.set_tooltip_text("Add new record")
        toolbar_header.pack_start(new_button)
        new_button.set_icon_name("list-add-symbolic")
        new_button.connect("clicked", self.add_content_item)

        self.lang_button: Gtk.DropDown = self.parent.create_lang_dropdown(
            self.parent.lang_store,
            self.lang_changed,
        )

        toolbar_header.pack_start(self.lang_button)

        selection_model = Gtk.NoSelection(model=self.model)
        Gtk.SelectionMode(0)

        column_view = Gtk.ColumnView(model=selection_model)

        title_factory = Gtk.SignalListItemFactory()
        title_factory.connect("setup", self.setup_title_column)
        title_factory.connect("bind", self.bind_title_column, "title")
        title_factory.connect("unbind", self.unbind_title_column)
        title_column = Gtk.ColumnViewColumn(
            title="Title",
            factory=title_factory,
        )
        title_column.set_expand(True)
        title_column.set_resizable(True)
        column_view.append_column(title_column)

        page_factory = Gtk.SignalListItemFactory()
        page_factory.connect("setup", self.setup_page_column)
        page_factory.connect("bind", self.bind_page_column)
        page_factory.connect("unbind", self.unbind_page_column)
        page_column = Gtk.ColumnViewColumn(title="Page", factory=page_factory)
        page_column.set_resizable(True)
        column_view.append_column(page_column)

        delete_factory = Gtk.SignalListItemFactory()
        delete_factory.connect("setup", self.setup_delete_column)
        delete_factory.connect("bind", self.bind_delete_column)
        delete_factory.connect("unbind", self.unbind_delete_column)
        delete_column = Gtk.ColumnViewColumn(
            title="Delete",
            factory=delete_factory,
        )
        column_view.append_column(delete_column)

        self.update_contents(self.lang_button.get_selected())

        self.set_size_request(800, 600)
        self.set_child(column_view)

        self.connect("close-request", self.save_and_exit)

    def setup_title_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Entry = Gtk.Entry()
        list_item.set_child(entry)

    def setup_page_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        pages: list[str] = []
        for page in self.page_image_names:
            pages.append(page)
        entry: Gtk.DropDown = Gtk.DropDown.new_from_strings(pages)
        list_item.set_child(entry)

    def setup_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        button: Gtk.Button = Gtk.Button.new_from_icon_name(
            "edit-delete-symbolic",
        )
        list_item.set_child(button)

    def bind_title_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem, attribute: str) -> None:
        item = list_item.get_item()
        entry: Gtk.Entry = list_item.get_child()
        entry.set_text(getattr(item, attribute) or "")
        entry.connect("changed", self.entry_changed)

    def unbind_title_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Entry = list_item.get_child()
        entry.disconnect_by_func(self.entry_changed)

    def bind_page_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        entry: Gtk.DropDown = list_item.get_child()
        for i, page in enumerate(self.page_image_names):
            if page == item.page:
                entry.set_selected(i)
        entry.connect("notify::selected", self.page_changed, item)

    def unbind_page_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.DropDown = list_item.get_child()
        entry.disconnect_by_func(self.page_changed)

    def bind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        position = list_item.get_position()
        button: Gtk.Button = list_item.get_child()
        button.connect("clicked", self.on_delete_button_clicked, position)

    def unbind_delete_column(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        button: Gtk.Button = list_item.get_child()
        button.disconnect_by_func(self.on_delete_button_clicked)

    def on_delete_button_clicked(self, button: Gtk.Button, position: int) -> None:
        self.model.remove(position)
        self.set_modified()

    def entry_changed(self, widget: Gtk.Entry) -> None:
        self.set_modified()

    def page_changed(self, widget: Gtk.DropDown, _pspec: GObject.GParamSpec, item: ContentItem) -> None:
        item.page = widget.get_selected_item().get_string()
        self.set_modified()

    def save_and_exit(self, widget: Gtk.Button) -> None:
        if self.is_modified:
            self.update_contents(self.previous_lang)
        self.close()

    def add_content_item(self, widget: Gtk.Button, title: str = "", page: str = "") -> None:
        new_item = ContentItem(title=title, page=page)
        self.model.append(new_item)

    def lang_changed(self, widget: Gtk.DropDown, _pspec: GObject.GParamSpec) -> None:
        def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, lang: int) -> None:
            response = dialog.choose_finish(task)
            if response == 2:
                self.previous_lang = widget.get_selected()
                self.set_modified(False)
                self.update_contents(lang)
            elif response == 1:
                self.previous_lang = widget.get_selected()
                self.save_contents(lang)
            else:
                self.lang_button.disconnect_by_func(self.lang_changed)
                self.lang_button.set_selected(self.previous_lang)
                self.lang_button.connect("notify::selected", self.lang_changed)

        if self.is_modified:
            alert = Gtk.AlertDialog()
            alert.set_message("Unsaved Changes")
            alert.set_detail("There are unsaved changes that will be lost:")
            alert.set_buttons(
                ["Cancel", "Save and Switch", "Switch (lose changes)"],
            )
            alert.set_cancel_button(0)
            alert.set_default_button(1)
            alert.choose(self, None, handle_response, widget.get_selected())
        else:
            self.previous_lang = widget.get_selected()
            self.update_contents(widget.get_selected())

    def set_modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save_contents(self, lang: int) -> None:
        for entry in self.model:
            xml_page = self.parent.acbf_document.tree.xpath(
                f"//page[image[@href='{entry.page}']]",
            )
            if len(xml_page) > 0:
                element = xml.SubElement(xml_page[0], "title")
                element.set("lang", self.contents_languages[lang])
                element.text = entry.title

    def update_contents(self, lang: int) -> None:
        # TODO set image
        """if widget is not None:
        lang = widget.get_selected()"""

        """for entry in self.model:
            xml_page = self.parent.acbf_document.tree.xpath(f"//page[image[@href='{entry.page}']]")
            if len(xml_page) > 0:
                element = xml.SubElement(xml_page[0], "title")
                element.set('lang', lang)
                element.text = entry.title"""

        self.page_image_names.clear()
        for page in self.parent.acbf_document.tree.findall("body/page"):
            self.page_image_names.append(page.find("image").get("href"))

        self.model.remove_all()

        for idx, page in enumerate(self.parent.acbf_document.tree.findall("body/page")):
            default_title = ""
            title_found = False
            for title in page.findall("title"):
                default_title = title.text
                if (title.get("lang") == self.contents_languages[lang]) or (
                    title.get(
                        "lang",
                    )
                    is None
                    and self.contents_languages[lang] == "en"
                ):
                    self.add_content_item(
                        None,
                        title.text,
                        self.page_image_names[idx],
                    )
                    title_found = True
            if not title_found and default_title != "":
                self.add_content_item(None)
