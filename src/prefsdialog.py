"""prefsdialog.py - Preferences Dialog.

Copyright (C) 2011-2018 Robert Kubik
https://github.com/GeoRW/ACBF-Editor
"""
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

import constants
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk


class PrefsDialog(Gtk.Window):
    def __init__(self, parent: Gtk.Window):
        self.parent = parent
        super().__init__(title="Preferences")
        self.set_size_request(600, 400)
        self.connect("close-request", self.exit)

        toolbar = Gtk.HeaderBar.new()
        self.set_titlebar(toolbar)

        stack = Gtk.Stack()

        general = Gtk.Grid()
        general.set_margin_top(10)
        general.set_margin_start(10)
        general.set_margin_end(10)
        general.set_row_spacing(5)
        general.set_column_spacing(5)

        general.attach(Gtk.Label.new("Default Language"), 0, 0, 1, 1)
        gtk_lang_list = Gtk.StringList.new(constants.LANGUAGES)
        self.default_language = Gtk.DropDown()
        self.default_language.set_model(gtk_lang_list)
        self.default_language.set_enable_search(True)
        expression = Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
        self.default_language.set_expression(expression)
        self.default_language.connect("notify::selected", self.set_default_language,)

        general.attach(self.default_language, 1, 0, 1, 1)

        general.attach(Gtk.Label.new("Temporary directory"), 0, 1, 1, 1)
        self.tmpfs_button = Gtk.Switch()
        self.tmpfs_button.set_tooltip_text(
            "Directory where comic archives are unpacked. Use /dev/shm for temporary file storage filesystem (tmpfs) instead of default system temp directory to store in RAM.",
        )
        self.tmpfs_button.connect("notify::active", self.set_tmpfs)
        general.attach(self.tmpfs_button, 3, 1, 1, 1)

        self.tmpfs_entry = Gtk.Entry()
        self.tmpfs_entry.set_text(self.parent.preferences.get_value("tmpfs_dir"))
        general.attach(self.tmpfs_entry, 1, 1, 1, 1)

        if self.parent.preferences.get_value("tmpfs") == "True":
            self.tmpfs_button.set_active(True)
            self.tmpfs_entry.set_sensitive(True)
        else:
            self.tmpfs_button.set_active(False)
            self.tmpfs_entry.set_sensitive(False)

        doc_info = Gtk.Grid()
        doc_info.set_hexpand(True)
        doc_info.set_margin_top(10)
        doc_info.set_margin_end(10)
        doc_info.set_margin_start(10)
        doc_info.set_margin_start(5)
        doc_info.set_row_spacing(5)
        doc_info.set_column_spacing(5)

        # Author info section
        title = Gtk.Label()
        title.set_halign(Gtk.Align.START)
        title.set_markup("<b><big>Default Document Author</big></b>")
        sep: Gtk.Separator = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(5)
        sep.set_margin_bottom(5)
        doc_info.attach(title, 0, 0, 2, 1)
        doc_info.attach(sep, 0, 1, 2, 1)

        # Individual entry boxes for first, middle, last, and nicknames
        label: Gtk.Label = Gtk.Label()
        label.set_markup("<b>First Name</b>")

        label.set_halign(Gtk.Align.END)
        doc_info.attach(label, 0, 2, 1, 1)
        self.first = Gtk.Entry()
        self.first.set_hexpand(True)
        label = Gtk.Label.new("Middle Name")
        label.set_halign(Gtk.Align.END)
        doc_info.attach(self.first, 1, 2, 1, 1)
        doc_info.attach(label, 0, 3, 1, 1)
        self.middle = Gtk.Entry()
        label = Gtk.Label.new("Last Name")
        label.set_halign(Gtk.Align.END)
        doc_info.attach(self.middle, 1, 3, 1, 1)
        doc_info.attach(label, 0, 4, 1, 1)
        self.last = Gtk.Entry()
        label = Gtk.Label.new("Nickname")
        label.set_halign(Gtk.Align.END)
        doc_info.attach(self.last, 1, 4, 1, 1)
        doc_info.attach(label, 0, 5, 1, 1)
        self.nick = Gtk.Entry()
        doc_info.attach(self.nick, 1, 5, 1, 1)

        frames = Gtk.Grid()

        frames.set_margin_top(5)
        frames.set_margin_start(5)
        frames.set_row_spacing(5)
        frames.set_column_spacing(5)

        frames.attach(Gtk.Label.new("Frame Colour"), 0, 0, 1, 1)
        color = Gdk.RGBA()
        color.parse(self.parent.preferences.get_value("frames_color"))
        self.frames_color_button = Gtk.ColorDialogButton()
        self.frames_color_button.set_dialog(Gtk.ColorDialog())
        self.frames_color_button.set_rgba(color)
        self.frames_color_button.connect("notify::dialog", self.set_frames_color)
        frames.attach(self.frames_color_button, 1, 0, 1, 1)

        frames.attach(Gtk.Label.new("Text Layers Colour"), 0, 1, 1, 1)
        color = Gdk.RGBA()
        color.parse(self.parent.preferences.get_value("text_layers_color"))
        self.text_color_button = Gtk.ColorDialogButton()
        self.text_color_button.set_dialog(Gtk.ColorDialog())
        self.text_color_button.set_rgba(color)
        self.text_color_button.connect("notify::dialog", self.set_text_layers_color)
        frames.attach(self.text_color_button, 1, 1, 1, 1)

        self.snap_to_border = Gtk.CheckButton.new_with_label("Snap to Image Border")
        self.snap_to_border.set_tooltip_text("Snap polygon points to image border when close to it")
        self.snap_to_border.connect("toggled", self.set_snap)
        frames.attach(self.snap_to_border, 1, 2, 1, 1)

        stack.add_titled(general, "general", "General")
        stack.add_titled(doc_info, "doc_info", "Document Information")
        stack.add_titled(frames, "frames", "Frames")

        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(stack)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.append(stack_switcher)
        vbox.append(stack)

        self.set_child(vbox)

        stack.set_visible_child_name("general")

        # Initialise values
        self.default_language.set_selected(
            constants.LANGUAGES.index(self.parent.preferences.get_value("default_language")),
        )
        if self.parent.preferences.get_value("tmpfs") == "True":
            self.tmpfs_button.set_active(True)
            self.tmpfs_entry.set_text(self.parent.preferences.get_value("tmpfs_dir"))
        if self.parent.preferences.get_value("snap") == "True":
            self.snap_to_border.set_active(True)
        if self.parent.preferences.get_value("first_name") != "":
            self.first.set_text(self.parent.preferences.get_value("first_name"))
        if self.parent.preferences.get_value("middle_name") != "":
            self.middle.set_text(self.parent.preferences.get_value("middle_name"))
        if self.parent.preferences.get_value("last_name") != "":
            self.last.set_text(self.parent.preferences.get_value("last_name"))
        if self.parent.preferences.get_value("nickname") != "":
            self.nick.set_text(self.parent.preferences.get_value("nickname"))
        if self.parent.preferences.get_value("frames_color") != "":
            color = Gdk.RGBA()
            color.parse(self.parent.preferences.get_value("frames_color"))
            self.frames_color_button.set_rgba(color)
        if self.parent.preferences.get_value("text_layers_color") != "":
            color = Gdk.RGBA()
            color.parse(self.parent.preferences.get_value("text_layers_color"))
            self.text_color_button.set_rgba(color)

    def set_snap(self, widget: Gtk.CheckButton) -> None:
        if widget.get_active():
            self.parent.preferences.set_value("snap", "True")
        else:
            self.parent.preferences.set_value("snap", "False")
        self.parent.preferences.save_preferences()

    def set_text_layers_color(self, widget: Gtk.ColorDialogButton, _pspec: GObject.GParamSpec) -> None:
        self.parent.preferences.set_value("text_layers_color", widget.get_rgba().to_string())
        self.parent.preferences.save_preferences()

    def set_frames_color(self, widget: Gtk.ColorDialogButton, _pspec: GObject.GParamSpec) -> None:
        self.parent.preferences.set_value("frames_color", widget.get_rgba().to_string())
        self.parent.preferences.save_preferences()

    def set_default_language(self, widget: Gtk.DropDown, _pspec: GObject.GParamSpec) -> None:
        self.parent.preferences.set_value("default_language", constants.LANGUAGES[widget.props.selected])

    def set_tmpfs(self, widget: Gtk.Button, _pspec: GObject.GParamSpec) -> None:
        if widget.get_active():
            self.tmpfs_entry.set_sensitive(True)
        else:
            self.tmpfs_entry.set_sensitive(False)

    def save(self) -> None:
        if self.snap_to_border.get_active():
            self.parent.preferences.set_value("snap", "True")
        else:
            self.parent.preferences.set_value("snap", "False")
        if self.tmpfs_button.get_active():
            self.parent.preferences.set_value("tmpfs", "True")
            self.parent.preferences.set_value("tmpfs_dir", self.tmpfs_entry.get_text())
        else:
            self.parent.preferences.set_value("tmpfs", "False")
        self.parent.preferences.set_value("text_layers_color", self.text_color_button.get_rgba().to_string())
        self.parent.preferences.set_value("frames_color", self.frames_color_button.get_rgba().to_string())
        self.parent.preferences.set_value("first_name", self.first.get_text())
        self.parent.preferences.set_value("middle_name", self.middle.get_text())
        self.parent.preferences.set_value("last_name", self.last.get_text())
        self.parent.preferences.set_value("nickname", self.nick.get_text())

        self.parent.preferences.save_preferences()

    def exit(self, widget: Gtk.Button) -> None:
        self.save()
        self.close()
