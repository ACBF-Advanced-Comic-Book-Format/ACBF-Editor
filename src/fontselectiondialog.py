"""fontselectiondialog.py - Miscellaneous constants.

Copyright (C) 2011-2018 Robert Kubik
https://launchpad.net/~just-me
"""
import logging
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


import os

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango, PangoCairo, GObject, Gio
import io
import cairo
from PIL import Image, ImageDraw, ImageFont

import constants

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FontItem(GObject.Object):
    label = GObject.Property(type=str)
    style = GObject.Property(type=str)
    name = GObject.Property(type=str)
    path = GObject.Property(type=str)

    def __init__(self, label: str, style: str, name: str, path: str):
        super().__init__()
        self.label = label
        self.style = style
        self.name = name
        self.path = path


class CustomFontChooserDialog(Gtk.Dialog):
    def __init__(self, font_directory):
        super().__init__(title="Select Font", modal=True)
        self.font_directory = font_directory
        self.selected_font = None

        self.set_default_size(400, 300)
        self.set_resizable(True)

        self.box = self.get_content_area()
        self.font_list_store: Gtk.ListStore = Gio.ListStore.new(item_type=FontItem)

        self.load_fonts()
        self.create_widgets()

    def load_fonts(self):
        for font_file in os.listdir(self.font_directory):
            if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                font_path = os.path.join(self.font_directory, font_file)
                self.font_list_store.append(FontItem(label=font_file, name=font_file, path=font_path))

    def create_widgets(self):
        self.font_treeview = Gtk.TreeView(model=self.font_list_store)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Font Files", renderer, text=0)
        self.font_treeview.append_column(column)

        self.font_treeview.connect("cursor-changed", self.on_font_selected)
        self.box.append(self.font_treeview)

        self.preview_area = Gtk.DrawingArea()
        self.preview_area.set_content_width(300)
        self.preview_area.set_content_height(100)
        self.preview_area.set_draw_func(self.on_draw_preview)
        self.box.append(self.preview_area)

        self.show_all()

    def on_font_selected(self, treeview):
        selection = treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            self.selected_font = model[treeiter][1]
            self.preview_area.queue_draw()

    def on_draw_preview(self, drawing_area, context, width, height):
        if not self.selected_font:
            return

        # Create Pango layout for rendering text
        layout = PangoCairo.create_layout(context)
        font_description = Pango.FontDescription()
        font_description.set_family("Sans")
        font_description.set_absolute_size(20 * Pango.SCALE)
        layout.set_font_description(font_description)
        layout.set_text("Sample Text", -1)

        # Render the text
        context.move_to(10, 50)
        PangoCairo.update_layout(context, layout)
        PangoCairo.show_layout(context, layout)

        # Load and use the selected font for preview
        face = cairo.ToyFontFace("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_face(face)
        context.set_font_size(20)
        context.move_to(10, 100)
        context.show_text("Sample Text")


class FontSelectionDialog(Gtk.FontDialog):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        # self.font_type = font_type

        # self.choose_font()

    def create_model(self):
        store = Gtk.ListStore(str)
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            store.append([font[0].replace('.ttf', '').replace('.TTF', '').replace('.otf', '').replace('.OTF', '')])
        return store

    def create_columns(self, treeView):
        rendererText = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Font Name", rendererText, text=0)
        column.set_sort_column_id(0)
        treeView.append_column(column)

    def on_cursor_changed(self, widget, *args):
        self._window.font_idx = widget.get_cursor()[0][0]
        self.get_font_preview(constants.FONTS_LIST[widget.get_cursor()[0][0]][1])

    def on_activated(self, widget, *args):
        self._window.font_idx = widget.get_cursor()[0][0]
        Gtk.Widget.destroy(self)

    def get_font_preview(self, font_path):
        font_image = Image.new("RGB", (200, 50), "#fff")
        draw = ImageDraw.Draw(font_image)
        font = ImageFont.truetype(font_path, 20)
        draw.text((10, 10), "AaBbCc DdEeFf", font=font, fill="#000")


        pixbuf_image = pil_to_pixbuf(font_image, "#000")
        self.font_image.set_from_pixbuf(pixbuf_image)


class FontSelectionOldDialog(Gtk.Window):
    """Font Selection dialog."""
    def __init__(self, parent, font_dir, selected_font):
        super().__init__(title="Font Selection")
        self.set_transient_for(parent)
        self.parent = parent
        self.font_directory = font_dir
        self.set_size_request(350, 500)

        content: Gtk.Box = Gtk.Box.new(Gtk.Orientation.VERTICAL, spacing=0)

        # list of available fonts
        sw = Gtk.ScrolledWindow()
        sw.set_size_request(250, 200)

        content.append(sw)

        self.treestore = Gio.ListStore.new(item_type=FontItem)

        font_list_factory = Gtk.SignalListItemFactory()
        font_list_factory.connect("setup", self.setup_font_item)
        font_list_factory.connect("bind", self.bind_font_item)

        selection_model: Gtk.SingleSelection = Gtk.SingleSelection.new(self.treestore)

        font_view: Gtk.ListView = Gtk.ListView.new(selection_model, font_list_factory)
        font_view.set_single_click_activate(True)
        font_view.connect("activate", self.tree_item_selected)

        for font_file in os.listdir(self.font_directory):
            if font_file.lower().endswith(".ttf") or font_file.lower().endswith(".otf"):
                try:
                    font_path = os.path.join(self.font_directory, font_file)
                    font = ImageFont.truetype(font_path)
                    label = font.getname()
                    self.treestore.append(FontItem(label=label[0], style=label[1], name=font_file, path=font_path))
                except OSError as e:
                    logging.error(f"Failed to read font file: {font_file} error: {e}")
                except Exception as e:
                    logging.error(f"Failed to load font file: {font_file} error: {e}")


        sw.set_child(font_view)

        # font drawing
        #font_preview: Gtk.Box = Gtk.Box.new(Gtk.Orientation.VERTICAL, spacing=0)

        #label = Gtk.Label.new("Font Preview:")
        #font_preview.append(label)

        self.font_image = Gtk.Picture()

        #font_preview.append(self.font_image)
        content.append(self.font_image)

        self.set_child(content)

    def setup_font_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ColumnViewCell):
        entry = Gtk.Label()
        #entry.set_hexpand(True)
        #entry.set_halign(Gtk.Align.FILL)
        entry.set_margin_start(5)
        entry.set_margin_end(5)
        list_item.set_child(entry)

    def bind_font_item(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
        item: FontItem = list_item.get_item()
        position = list_item.get_position()
        entry: Gtk.Entry = list_item.get_child()
        label = f"{item.label} ({item.style})"
        entry.set_text(label)

    def tree_item_selected(self, list_view: Gtk.ListView, selection: int):
        item: FontItem = self.treestore.get_item(selection)
        self.gen_font_preview(item.path)

    def gen_font_preview(self, font_path):
        font_image = Image.new("RGB", (550, 45), "#fff")
        draw = ImageDraw.Draw(font_image)
        font = ImageFont.truetype(font_path, 20)
        draw.text((10, 10), "The Quick Brown Fox Jumped Over The Lazy Dog", font=font, fill="#000")

        pixbuf_image = self.pil_to_pixbuf(font_image)
        self.font_image.set_pixbuf(pixbuf_image)

    def pil_to_pixbuf(self, PILImage):
        """Return a pixbuf created from the PIL <image>."""
        try:
            PILImage = PILImage.convert("RGBA")

            # https://gist.github.com/mozbugbox/10cd35b2872628246140
            data = PILImage.tobytes()
            w, h = PILImage.size
            data = GLib.Bytes.new(data)
            pix = GdkPixbuf.Pixbuf.new_from_bytes(data, GdkPixbuf.Colorspace.RGB,  True, 8, w, h, w * 4)
            return pix
        except Exception as e:
            print("failed to create pixbuf with alpha: ", e)
            bg = Image.new("RGBA", (550, 200), (0, 0, 0, 0))

            dummy_file = io.BytesIO()
            bg.save(dummy_file, "ppm")
            dummy_file.seek(0)
            contents = dummy_file.read()
            dummy_file.close()

            loader = GdkPixbuf.PixbufLoader.new_with_type('pnm')
            loader.write(contents)
            loader.close()
            pixbuf = loader.get_pixbuf()
            return pixbuf