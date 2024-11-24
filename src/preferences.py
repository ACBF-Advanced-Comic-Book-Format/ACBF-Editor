"""preferences.py - viewer preferences (CONFIG_DIR/preferences.xml).

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

import os.path

import constants
import lxml.etree as xml


class Preferences:
    def __init__(self) -> None:
        self.prefs_file_path: str = os.path.join(constants.CONFIG_DIR, "preferences.xml")
        self.tree: xml.Element = None
        self.load_preferences()

    def create_new_tree(self) -> None:
        self.tree = xml.Element("preferences")

        version: xml.Element = xml.SubElement(self.tree, "version")
        version.text = constants.VERSION

        self.check_elements()

    def load_preferences(self) -> None:
        try:
            self.tree = xml.parse(source=self.prefs_file_path).getroot()
            self.set_value("version", constants.VERSION)
            self.check_elements()
            self.save_preferences()
        except Exception:
            self.create_new_tree()
            with open(self.prefs_file_path, "w") as f:
                f.write(xml.tostring(self.tree, encoding="unicode", pretty_print=True))

    def save_preferences(self) -> None:
        with open(self.prefs_file_path, "w") as f:
            f.write(xml.tostring(self.tree, encoding="unicode", pretty_print=True))

    def get_value(self, element: str) -> str:
        if self.tree.find(element) is not None:
            value = self.tree.find(element).text
            if value is None:
                value = ""
            return value
        else:
            self.set_default_value(element)
            return self.tree.find(element).text

    def set_value(self, element: xml.Element, value: str) -> None:
        self.tree.find(element).text = value

    def check_elements(self) -> None:
        for element in [
            "default_language",
            "tmpfs",
            "tmpfs_dir",
            "first_name",
            "middle_name",
            "last_name",
            "nickname",
            "unrar_location",
            "frames_color",
            "text_layers_color",
            "hidpi",
            "snap",
        ]:
            if self.tree.find(element) is None:
                self.set_default_value(element)

    def set_default_value(self, element: str) -> None:
        if element == "default_language":
            default_language = xml.SubElement(self.tree, "default_language")
            default_language.text = "en"
        elif element == "tmpfs":
            """Custom temp directory to be used instead of default system defined temp dir (when set to 'False').
            Can be set to /dev/shm for example to use tmpfs (temporary file storage filesystem, if supported by linux distribution),
            that uses RAM for temporary files storage. This may speed up opening and loading CBZ files and reduce disk I/Os
            but may fill in RAM and swap space quickly if large comicbook files are opened. So use with caution.
            To use this option, you need to edit the ~/.config/acbfv/preferences.xml file directly.
            ACBF Viewer creates acbfv directory here (e.g. /dev/shm/acbfv) where temporary files are stored. Anything inside
            acbfv directory is deleted when new CBZ file is opened, a CBZ file is added into library or ACBF Viewer is shut down properly.
            """
            tmpfs = xml.SubElement(self.tree, "tmpfs")
            tmpfs.text = "False"
        elif element == "tmpfs_dir":
            tmpfs_dir = xml.SubElement(self.tree, "tmpfs_dir")
            tmpfs_dir.text = "/dev/shm"
        elif element == "first_name":
            first_name = xml.SubElement(self.tree, "first_name")
            first_name.text = ""
        elif element == "middle_name":
            middle_name = xml.SubElement(self.tree, "middle_name")
            middle_name.text = ""
        elif element == "last_name":
            last_name = xml.SubElement(self.tree, "last_name")
            last_name.text = ""
        elif element == "nickname":
            nickname = xml.SubElement(self.tree, "nickname")
            nickname.text = ""
        elif element == "unrar_location":
            crop_border = xml.SubElement(self.tree, "unrar_location")
            if constants.PLATFORM == "win32":
                crop_border.text = '"C:\\Program Files\\Unrar\\unrar" x'
            else:
                crop_border.text = "unrar x"
        elif element == "frames_color":
            font_color_default = xml.SubElement(self.tree, "frames_color")
            font_color_default.text = "#000000"
        elif element == "text_layers_color":
            font_color_default = xml.SubElement(self.tree, "text_layers_color")
            font_color_default.text = "#FF0000"
        elif element == "hidpi":
            hidpi = xml.SubElement(self.tree, "hidpi")
            hidpi.text = "False"
        elif element == "snap":
            hidpi = xml.SubElement(self.tree, "snap")
            hidpi.text = "True"
