"""filechooser.py - FileChooserDialog implementation.

Copyright (C) 2011-2018 Robert Kubik
https://launchpad.net/~just-me
"""

from __future__ import annotations

from typing import Any

import fileprepare
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
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


class FileChooserDialog(Gtk.FileDialog):
    def __init__(self, parent: Gtk.Window, **properties: dict[Any, Any]):
        super().__init__(**properties)
        self.parent = parent

        # Create file filters
        comic_filter = Gtk.FileFilter()
        comic_filter.set_name("Comic files")
        comic_filter.add_pattern("*.acbf")
        comic_filter.add_pattern("*.acv")
        comic_filter.add_pattern("*.cbz")
        comic_filter.add_pattern("*.zip")
        comic_filter.add_pattern("*.cbr")

        all_files_filter = Gtk.FileFilter()
        all_files_filter.set_name("All files")
        all_files_filter.add_pattern("*")

        self.filters = Gio.ListStore.new(Gtk.FileFilter)
        self.filters.append(comic_filter)
        self.filters.append(all_files_filter)

    def open_file_dialog(self) -> None:
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_filters(self.filters)
        file_dialog.set_modal(True)
        file_dialog.set_title("Select a Comic File")
        file_dialog.open(parent=self.parent, callback=self.open_filename)

    def save_file_dialog(self) -> None:
        file_dialog = Gtk.FileDialog.new()
        file_dialog.set_filters(self.filters)
        file_dialog.set_modal(True)
        file_dialog.set_title("Save Comic File")
        file_dialog.save(parent=self.parent, callback=self.save_filename)

    def open_filename(self, dialog: Gtk.Window, response: Gio.Task) -> None:
        try:
            file = dialog.open_finish(response)
            # print(file.get_path())
            if file:
                prepared_file: fileprepare.FilePrepare = fileprepare.FilePrepare(
                    self,
                    file.get_path(),
                    self.parent.tempdir,
                    True,
                )
                self.parent.filename = prepared_file.filename
                self.parent.original_filename = file.get_path()
                self.parent.opened_file()
            else:
                self.destroy()
                # TODO Fail alert
        except GLib.Error as e:
            # TODO fail alert dialogue
            print("Error:", e)

    def save_filename(self, dialog: Gtk.Window, response: Gio.Task) -> None:
        try:
            file = dialog.save_finish(response)
            # print(file.get_path())
            if file:
                # prepared_file = fileprepare.FilePrepare(self, file.get_path(), self.parent.tempdir, True)
                # self.parent.filename = prepared_file.filename
                # self.parent.original_filename = file.get_path()
                self.parent.saved_file(file.get_path())
            else:
                self.destroy()
                # TODO Fail alert
        except GLib.Error as e:
            # TODO fail alert dialogue
            print("Error:", e)
