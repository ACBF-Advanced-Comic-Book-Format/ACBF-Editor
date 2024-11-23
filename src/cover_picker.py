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
from acbfdocument import ImageURI

import gi
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

gi.require_version("Gtk", "4.0")


class PageImage(GObject.Object):
    __gtype_name__ = "PageImage"
    image = GObject.Property(type=str)
    is_cover = GObject.Property(type=bool, default=False)

    def __init__(self, image: str = "", is_cover: bool = False):
        super().__init__()
        self.image = image
        self.is_cover = is_cover


class CoverDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        self.parent = parent
        super().__init__(title="Select Cover")
        self.set_size_request(900, 800)
        self.set_transient_for(parent)

        self.is_modified: bool = False

        self.model: Gio.ListStore = Gio.ListStore.new(item_type=PageImage)

        for file in self.parent.file_list:
            if str(file) == self.parent.acbf_document.cover_page_uri.file_path:
                self.model.append(PageImage(image=self.parent.acbf_document.cover_page_uri.file_path, is_cover=True))
            elif str(file).endswith((".jpg", ".png")):
                self.model.append(PageImage(image=file))

        selection_model = Gtk.SingleSelection(model=self.model)

        sw: Gtk.ScrolledWindow = Gtk.ScrolledWindow()

        grid_view = Gtk.GridView(model=selection_model)
        sw.set_child(grid_view)

        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_item)
        factory.connect("bind", self.bind_item)
        factory.connect("unbind", self.unbind_item)

        grid_view.set_factory(factory)

        self.connect("close-request", self.save_and_exit)
        self.set_child(sw)

    def setup_item(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        box: Gtk.Box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        checkbox: Gtk.CheckButton = Gtk.CheckButton()
        picture: Gtk.Picture = Gtk.Picture()
        picture.set_size_request(80, 150)
        picture.set_margin_top(5)
        picture.set_margin_end(5)
        picture.set_margin_start(5)
        picture.set_margin_bottom(5)
        box.append(checkbox)
        box.append(picture)
        list_item.set_child(box)

    def bind_item(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        item: PageImage = list_item.get_item()
        image = self.parent.acbf_document.load_image(ImageURI(item.image))
        box: Gtk.Box = list_item.get_child()
        checkbox: Gtk.CheckButton = box.get_first_child()
        item.bind_property("is_cover", checkbox, "active", GObject.BindingFlags.SYNC_CREATE)
        picture: Gtk.Picture = box.get_last_child()
        picture.set_pixbuf(self.parent.pil_to_pixbuf(image))
        checkbox.connect("toggled", self.check_changed, item)

    def unbind_item(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem) -> None:
        box: Gtk.Box = list_item.get_child()
        checkbox: Gtk.CheckButton = box.get_first_child()
        checkbox.disconnect_by_func(self.check_changed)

    def check_changed(self, entry: Gtk.CheckButton, item: PageImage) -> None:
        if item.is_cover and not entry.get_active():
            # Need a cover
            entry.disconnect_by_func(self.check_changed)
            entry.props.active = True
            entry.connect("toggled", self.check_changed, item)
        else:
            # Remove current marked cover. TODO Keep var of current cover instead of loop?
            i = 0
            while i < 9999:
                page: PageImage = self.model.get_item(i)
                if page is None:
                    break
                if page.is_cover:
                    page.is_cover = False
                    self.model.items_changed(i, 0, 0)
                    # Should only be one
                    break
                i = i + 1

            item.is_cover = entry.get_active()

        self.set_modified()

    def set_modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save_and_exit(self, widget: Gtk.Button) -> None:
        if self.is_modified:
            i = 0
            while i < 9999:
                page: PageImage = self.model.get_item(i)
                if page is None:
                    break
                if page.is_cover:
                    page.is_cover = True
                    self.parent.acbf_document.cover_page_uri = ImageURI(page.image)
                    self.parent.acbf_document.cover_page = self.parent.acbf_document.load_image(ImageURI(page.image))
                    break
                i = i + 1

            self.parent.cover_widget_update()
            self.parent.modified()
        self.close()
