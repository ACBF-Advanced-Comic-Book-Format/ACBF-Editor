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

import pathlib

import fontselectiondialog
import gi
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

gi.require_version("Gtk", "4.0")


class FontItem(GObject.Object):
    sematic = GObject.Property(type=str)
    font = GObject.Property(type=str)
    font_families = GObject.Property(type=str)
    colour = GObject.Property(type=str)

    def __init__(self, sematic: str, font: str, font_families: str, colour: str):
        super().__init__()
        self.sematic = sematic
        self.font = font
        self.font_families = font_families
        self.colour = colour


class EditStylesWindow(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        super().__init__(title="Edit Styles/Font Definitions")
        self.parent = parent
        self.is_modified: bool = False
        toolbar_header = Gtk.HeaderBar()
        self.set_titlebar(toolbar_header)

        self.model: Gio.ListStore = Gio.ListStore(item_type=FontItem)

        for k, v in self.parent.acbf_document.font_styles.items():
            font_path = pathlib.Path(v)
            font = font_path.stem.split("-")[0]
            font_familes = self.parent.acbf_document.font_families[k]
            colour = self.parent.acbf_document.font_colors.get(k, "#000000")
            self.model.append(
                FontItem(
                    sematic=k,
                    font=font,
                    font_families=font_familes,
                    colour=colour,
                ),
            )

        selection_model = Gtk.NoSelection(model=self.model)

        # Gtk.SelectionMode(0)

        # Create the ColumnView
        column_view = Gtk.ColumnView(model=selection_model)

        sematic_factory = Gtk.SignalListItemFactory()
        sematic_factory.connect("setup", self.setup_sematic_column)
        sematic_factory.connect("bind", self.bind_sematic_column)
        sematic_column = Gtk.ColumnViewColumn(
            title="Title",
            factory=sematic_factory,
        )
        # sematic_column.set_expand(True)
        sematic_column.set_resizable(True)
        column_view.append_column(sematic_column)

        font_factory = Gtk.SignalListItemFactory()
        font_factory.connect("setup", self.setup_font_column)
        font_factory.connect("bind", self.bind_font_column)
        font_factory = Gtk.ColumnViewColumn(title="Font", factory=font_factory)
        font_factory.set_resizable(True)
        font_factory.set_expand(True)
        column_view.append_column(font_factory)

        # Add delete button column
        colour_factory = Gtk.SignalListItemFactory()
        colour_factory.connect("setup", self.setup_colour_column)
        colour_factory.connect("bind", self.bind_colour_column)
        colour_factory = Gtk.ColumnViewColumn(
            title="Colour",
            factory=colour_factory,
        )
        column_view.append_column(colour_factory)

        # Add the ColumnView to a ScrolledWindow
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_child(column_view)

        # Add the ScrolledWindow to the main window
        # content.append(scrolled_window)

        """okay_button = Gtk.Button.new_with_label("Save and Close")
        okay_button.connect("clicked", self.save_and_exit)

        toolbar_bottom.pack_start(okay_button)
        toolbar.add_bottom_bar(toolbar_bottom)"""

        self.set_size_request(500, 600)
        self.set_child(scrolled_window)

        # Create Font list
        """context = self.create_pango_context()
        for font in context.list_families():
            font_name = font.get_name()"""

        """fonts_dir = os.path.join(self.tempdir, 'Fonts')
        for root, dirs, files in os.walk(fonts_dir):
            for f in files:
                is_duplicate = False
                if f.upper()[-4:] == '.TTF' or f.upper()[-4:] == '.OTF':
                    for font in constants.FONTS_LIST:
                        if f.upper() == font[0].upper():
                            is_duplicate = True
                    if not is_duplicate:
                        constants.FONTS_LIST.append((f.replace('.ttf', '').replace('.TTF', '').replace('.otf',
                                                                                                       '').replace(
                            '.OTF', ''), os.path.join(root, f)))


        if response == Gtk.ResponseType.OK:
            self.is_modified = True
            style = ''

            if self.speech_font.font_idx > 0:
                self.acbf_document.font_styles["normal"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.speech_font.font_idx][1]))
                style = 'text-area {font-family: "' + os.path.basename(self.acbf_document.font_styles["normal"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.speech_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.speech_font.font_idx][1],
                                    self.acbf_document.font_styles["normal"])
                style = style + 'color: "' + self.acbf_document.font_colors["speech"] + '";}\n'
            if self.emphasis_font.font_idx > 0:
                self.acbf_document.font_styles["emphasis"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.emphasis_font.font_idx][1]))
                style = style + 'emphasis {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["emphasis"]) + '";}\n'
                if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(
                        constants.FONTS_LIST[self.emphasis_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.emphasis_font.font_idx][1],
                                    self.acbf_document.font_styles["emphasis"])
            if self.strong_font.font_idx > 0:
                self.acbf_document.font_styles["strong"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.strong_font.font_idx][1]))
                style = style + 'strong {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["strong"]) + '";}\n'
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.strong_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.strong_font.font_idx][1],
                                    self.acbf_document.font_styles["strong"])
            if self.commentary_font.font_idx > 0:
                self.acbf_document.font_styles["commentary"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.commentary_font.font_idx][1]))
                style = style + 'text-area[type=commentary] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["commentary"]) + '"; '
                if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(
                        constants.FONTS_LIST[self.commentary_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.commentary_font.font_idx][1],
                                    self.acbf_document.font_styles["commentary"])
                style = style + 'color: "' + self.acbf_document.font_colors["commentary"] + '";}\n'
            if self.code_font.font_idx > 0:
                self.acbf_document.font_styles["code"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.code_font.font_idx][1]))
                style = style + 'text-area[type=code] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["code"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.code_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.code_font.font_idx][1],
                                    self.acbf_document.font_styles["code"])
                style = style + 'color: "' + self.acbf_document.font_colors["code"] + '";}\n'
            if self.formal_font.font_idx > 0:
                self.acbf_document.font_styles["formal"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.formal_font.font_idx][1]))
                style = style + 'text-area[type=formal] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["formal"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.formal_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.formal_font.font_idx][1],
                                    self.acbf_document.font_styles["formal"])
                style = style + 'color: "' + self.acbf_document.font_colors["formal"] + '";}\n'
            if self.letter_font.font_idx > 0:
                self.acbf_document.font_styles["letter"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.letter_font.font_idx][1]))
                style = style + 'text-area[type=letter] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["letter"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.letter_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.letter_font.font_idx][1],
                                    self.acbf_document.font_styles["letter"])
                style = style + 'color: "' + self.acbf_document.font_colors["letter"] + '";}\n'
            if self.heading_font.font_idx > 0:
                self.acbf_document.font_styles["heading"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.heading_font.font_idx][1]))
                style = style + 'text-area[type=heading] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["heading"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.heading_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.heading_font.font_idx][1],
                                    self.acbf_document.font_styles["heading"])
                style = style + 'color: "' + self.acbf_document.font_colors["heading"] + '";}\n'
            if self.audio_font.font_idx > 0:
                self.acbf_document.font_styles["audio"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.audio_font.font_idx][1]))
                style = style + 'text-area[type=audio] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["audio"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.audio_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.audio_font.font_idx][1],
                                    self.acbf_document.font_styles["audio"])
                style = style + 'color: "' + self.acbf_document.font_colors["audio"] + '";}\n'
            if self.thought_font.font_idx > 0:
                self.acbf_document.font_styles["thought"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.thought_font.font_idx][1]))
                style = style + 'text-area[type=thought] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["thought"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.thought_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.thought_font.font_idx][1],
                                    self.acbf_document.font_styles["thought"])
                style = style + 'color: "' + self.acbf_document.font_colors["thought"] + '";}\n'
            if self.sign_font.font_idx > 0:
                self.acbf_document.font_styles["sign"] = os.path.join(fonts_dir, os.path.basename(
                    constants.FONTS_LIST[self.sign_font.font_idx][1]))
                style = style + 'text-area[type=sign] {font-family: "' + os.path.basename(
                    self.acbf_document.font_styles["sign"]) + '"; '
                if not os.path.isfile(
                        os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.sign_font.font_idx][1]))):
                    shutil.copyfile(constants.FONTS_LIST[self.sign_font.font_idx][1],
                                    self.acbf_document.font_styles["sign"])
                style = style + 'color: "' + self.acbf_document.font_colors["sign"] + '";}\n'

            # print style
            if style != '':
                try:
                    self.acbf_document.tree.find("style").text = style
                except:
                    element = xml.SubElement(self.acbf_document.tree.getroot(), "style", type="text/css")
                    element.text = str(style)

            # delete unused files
            for root, dirs, files in os.walk(fonts_dir):
                for f in files:
                    if f.upper()[-4:] == '.TTF' or f.upper()[-4:] == '.OTF':
                        if os.path.join(root, f) not in list(self.acbf_document.font_styles.values()):
                            os.remove(os.path.join(root, f))

        dialog.destroy()
        return"""

    def setup_sematic_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Label = Gtk.Label()
        entry.set_margin_start(5)
        entry.set_margin_end(5)
        entry.set_margin_top(5)
        entry.set_margin_bottom(5)
        list_item.set_child(entry)

    def setup_font_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        entry: Gtk.Button = Gtk.Button()
        # entry = Gtk.FontDialogButton()
        # entry.set_dialog(Gtk.FontDialog())
        # entry.set_use_font(True)
        list_item.set_child(entry)

    def setup_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        button = Gtk.ColorDialogButton.new(Gtk.ColorDialog())
        list_item.set_child(button)

    def bind_sematic_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        entry = list_item.get_child()
        entry.set_text(item.sematic.capitalize() or "")

    def bind_font_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        entry: Gtk.FontDialogButton = list_item.get_child()
        entry.set_label(item.font)
        entry.connect("clicked", self.font_button_click, item)
        # initial_font = Pango.FontDescription.from_string(f"{item.font} 12")
        # print(item.font_families)
        # test = Pango.FontDescription.from_string(item.font_families.split(",")[0])
        # print(test.to_string())
        # entry.set_font_desc(test)
        # entry.set_level(Gtk.FontLevel.FAMILY)

    def bind_colour_column(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        button = list_item.get_child()
        colour = Gdk.RGBA()
        colour.parse(item.colour)
        button.set_rgba(colour)

    def font_button_click(self, widget: Gtk.Button, item: FontItem) -> None:
        # chooser = fontselectiondialog.CustomFontChooserDialog(self.parent.acbf_document.fonts_dir)
        chooser = fontselectiondialog.FontSelectionOldDialog(
            self,
            self.parent.acbf_document.fonts_dir,
            item,
        )
        chooser.present()

    def set_modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            title = self.get_title()
            if modified:
                title += "*"
            self.set_title(title)

    def save_and_exit(self, widget: Gtk.Button) -> None:
        self.close()
