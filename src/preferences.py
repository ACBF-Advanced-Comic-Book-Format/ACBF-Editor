"""preferences.py - viewer preferences (CONFIG_DIR/preferences.xml).

Copyright (C) 2011-2024 Robert Kubik
https://github.com/ACBF-Advanced-Comic-Book-Format
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

import os.path
import lxml.etree as xml

try:
  from . import constants
except:
  import constants
  
class Preferences():

  def __init__(self):
      self.prefs_file_path = os.path.join(constants.CONFIG_DIR, 'preferences.xml');
      self.load_preferences()

  def create_new_tree(self):
      self.tree = xml.Element("preferences")

      version = xml.SubElement(self.tree, "version")
      version.text = constants.VERSION

      self.check_elements()

      #print(self.tree.find("bg_color_override").text)
      #print(xml.tostring(self.tree, encoding='unicode', pretty_print=True))

  def load_preferences(self):
      if os.path.isfile(self.prefs_file_path):
        self.tree = xml.parse(source = self.prefs_file_path).getroot()
        self.set_value('version', constants.VERSION)
        self.check_elements()
        self.save_preferences()
      else:
        self.create_new_tree()
        f = open(self.prefs_file_path, 'w')
        f.write(xml.tostring(self.tree, encoding='unicode', pretty_print=True))
        f.close()

  def save_preferences(self):
      f = open(self.prefs_file_path, 'w')
      f.write(xml.tostring(self.tree, encoding='unicode', pretty_print=True))
      f.close()

  def get_value(self, element):
      if self.tree.find(element) != None:
        return self.tree.find(element).text
      else:
        self.set_default_value(element)
        return self.tree.find(element).text

  def set_value(self, element, value):
      self.tree.find(element).text = value
      return

  def check_elements(self, *args):
      for element in ["default_language", "tmpfs", "tmpfs_dir", "comics_dir", "first_name", "middle_name", "last_name", "nickname", "unrar_location",
                      "frames_color", "text_layers_color", "hidpi", "snap"]:
        if self.tree.find(element) == None:
          self.set_default_value(element)

  def set_default_value(self, element):
      if element == 'default_language':
        default_language = xml.SubElement(self.tree, "default_language")
        default_language.text = "en"
      elif element == 'tmpfs':
        """ Custom temp directory to be used instead of default system defined temp dir (when set to 'False').
            Can be set to /dev/shm for example to use tmpfs (temporary file storage filesystem, if supported by linux distribution),
            that uses RAM for temporary files storage. This may speed up opening and loading CBZ files and reduce disk I/Os
            but may fill in RAM and swap space quickly if large comicbook files are opened. So use with caution.
            To use this option, you need to edit the ~/.config/acbfv/preferences.xml file directly.
            ACBF Viewer creates acbfv directory here (e.g. /dev/shm/acbfv) where temporary files are stored. Anything inside
            acbfv directory is deleted when new CBZ file is opened, a CBZ file is added into library or ACBF Viewer is shut down properly.
        """
        tmpfs = xml.SubElement(self.tree, "tmpfs")
        tmpfs.text = "False"
      elif element == 'tmpfs_dir':
        tmpfs_dir = xml.SubElement(self.tree, "tmpfs_dir")
        tmpfs_dir.text = "/dev/shm"
      elif element == 'comics_dir':
        comics_dir = xml.SubElement(self.tree, "comics_dir")
        comics_dir.text = "."
      elif element == 'first_name':
        first_name = xml.SubElement(self.tree, "first_name")
      elif element == 'middle_name':
        middle_name = xml.SubElement(self.tree, "middle_name")
      elif element == 'last_name':
        last_name = xml.SubElement(self.tree, "last_name")
      elif element == 'nickname':
        nickname = xml.SubElement(self.tree, "nickname")
      elif element == 'unrar_location':
        crop_border = xml.SubElement(self.tree, "unrar_location")
        if constants.PLATFORM == 'win32':
          crop_border.text = '"C:\\Program Files\\Unrar\\unrar" x'
        else:
          crop_border.text = 'unrar x'
      elif element == 'frames_color':
        font_color_default = xml.SubElement(self.tree, "frames_color")
        font_color_default.text = "#0000FF"
      elif element == 'text_layers_color':
        font_color_default = xml.SubElement(self.tree, "text_layers_color")
        font_color_default.text = "#FF0000"
      elif element == 'hidpi':
        hidpi = xml.SubElement(self.tree, "hidpi")
        hidpi.text = "False"
      elif element == 'snap':
        hidpi = xml.SubElement(self.tree, "snap")
        hidpi.text = "True"

