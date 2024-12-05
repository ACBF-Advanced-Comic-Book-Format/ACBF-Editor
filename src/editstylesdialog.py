"""editstylesdialog.py - Edit Styles Dialog.

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

import os
import shutil

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Gdk

try:
  from . import constants
  from . import fontselectiondialog
except:
  import constants
  import fontselectiondialog

class EditStylesDialog(gtk.Dialog):
    
    """Edit Styles dialog."""
    
    def __init__(self, window):
        self._window = window
        self.acbf_document = self._window.acbf_document
        self.tempdir = self._window.tempdir
        
        gtk.Dialog.__init__(self, 'Edit Styles/Fonts Definitions', window, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                                  (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
                                  
        self.set_resizable(True)
        self.set_border_width(8)

        # Create Font list
        self.fonts_dir = os.path.join(self.tempdir, 'Fonts')
        for root, dirs, files in os.walk(self.fonts_dir):
          for f in files:
            is_duplicate = False
            if f.upper()[-4:] == '.TTF' or f.upper()[-4:] == '.OTF':
              for font in constants.FONTS_LIST:
                if f.upper() == font[0].upper():
                  is_duplicate = True
              if not is_duplicate:
                constants.FONTS_LIST.append((f.replace('.ttf', '').replace('.TTF', '').replace('.otf', '').replace('.OTF', ''), os.path.join(root, f)))

        # Font Styles
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        ## Speech
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Speech (default): </tt>')
        hbox.pack_start(label, True, False, 0)
        
        self.speech_font = gtk.Button()
        self.speech_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["normal"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["normal"]):
            self.speech_font.font_idx = idx
            break
        self.speech_font.set_label(constants.FONTS_LIST[self.speech_font.font_idx][0])

        hbox.pack_start(self.speech_font, True, True, 0)
        self.speech_font.connect("clicked", self.set_speech_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["speech"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'speech')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Emphasis
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Emphasis:         </tt>')
        hbox.pack_start(label, True, False, 0)

        self.emphasis_font = gtk.Button()
        self.emphasis_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["emphasis"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["emphasis"]):
            self.emphasis_font.font_idx = idx
            break
        self.emphasis_font.set_label(constants.FONTS_LIST[self.emphasis_font.font_idx][0])

        hbox.pack_start(self.emphasis_font, True, True, 0)
        self.emphasis_font.connect("clicked", self.set_emphasis_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, "#999999")
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_sensitive(False)
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Strong
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Strong:           </tt>')
        hbox.pack_start(label, True, False, 0)

        self.strong_font = gtk.Button()
        self.strong_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["strong"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["strong"]):
            self.strong_font.font_idx = idx
            break
        self.strong_font.set_label(constants.FONTS_LIST[self.strong_font.font_idx][0])

        hbox.pack_start(self.strong_font, True, True, 0)
        self.strong_font.connect("clicked", self.set_strong_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, "#999999")
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_sensitive(False)
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Commentary
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Commentary:       </tt>')
        hbox.pack_start(label, True, False, 0)

        self.commentary_font = gtk.Button()
        self.commentary_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["commentary"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["commentary"]):
            self.commentary_font.font_idx = idx
            break
        self.commentary_font.set_label(constants.FONTS_LIST[self.commentary_font.font_idx][0])

        hbox.pack_start(self.commentary_font, True, True, 0)
        self.commentary_font.connect("clicked", self.set_commentary_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["commentary"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'commentary')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Code
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Code:             </tt>')
        hbox.pack_start(label, True, False, 0)

        self.code_font = gtk.Button()
        self.code_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["code"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["code"]):
            self.code_font.font_idx = idx
            break
        self.code_font.set_label(constants.FONTS_LIST[self.code_font.font_idx][0])

        hbox.pack_start(self.code_font, True, True, 0)
        self.code_font.connect("clicked", self.set_code_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["code"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'code')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Formal
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Formal:           </tt>')
        hbox.pack_start(label, True, False, 0)

        self.formal_font = gtk.Button()
        self.formal_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["formal"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["formal"]):
            self.formal_font.font_idx = idx
            break
        self.formal_font.set_label(constants.FONTS_LIST[self.formal_font.font_idx][0])

        hbox.pack_start(self.formal_font, True, True, 0)
        self.formal_font.connect("clicked", self.set_formal_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["formal"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'formal')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Letter
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Letter:           </tt>')
        hbox.pack_start(label, True, False, 0)

        self.letter_font = gtk.Button()
        self.letter_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["letter"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["letter"]):
            self.letter_font.font_idx = idx
            break
        self.letter_font.set_label(constants.FONTS_LIST[self.letter_font.font_idx][0])

        hbox.pack_start(self.letter_font, True, True, 0)
        self.letter_font.connect("clicked", self.set_letter_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["letter"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'letter')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Heading
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Heading:          </tt>')
        hbox.pack_start(label, True, False, 0)

        self.heading_font = gtk.Button()
        self.heading_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["heading"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["heading"]):
            self.heading_font.font_idx = idx
            break
        self.heading_font.set_label(constants.FONTS_LIST[self.heading_font.font_idx][0])

        hbox.pack_start(self.heading_font, True, True, 0)
        self.heading_font.connect("clicked", self.set_heading_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["heading"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'heading')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Audio
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Audio:            </tt>')
        hbox.pack_start(label, True, False, 0)

        self.audio_font = gtk.Button()
        self.audio_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["audio"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["audio"]):
            self.audio_font.font_idx = idx
            break
        self.audio_font.set_label(constants.FONTS_LIST[self.audio_font.font_idx][0])

        hbox.pack_start(self.audio_font, True, True, 0)
        self.audio_font.connect("clicked", self.set_audio_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["audio"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'audio')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Thought
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Thought:          </tt>')
        hbox.pack_start(label, True, False, 0)

        self.thought_font = gtk.Button()
        self.thought_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["thought"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["thought"]):
            self.thought_font.font_idx = idx
            break
        self.thought_font.set_label(constants.FONTS_LIST[self.thought_font.font_idx][0])

        hbox.pack_start(self.thought_font, True, True, 0)
        self.thought_font.connect("clicked", self.set_thought_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["thought"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'thought')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)

        ## Sign
        hbox = gtk.HBox(True, 0)
        
        label = gtk.Label()
        label.set_markup('<tt>Sign:             </tt>')
        hbox.pack_start(label, True, False, 0)

        self.sign_font = gtk.Button()
        self.sign_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start = 0):
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["sign"]))[0] or font[0] == os.path.basename(self.acbf_document.font_styles["sign"]):
            self.sign_font.font_idx = idx
            break
        self.sign_font.set_label(constants.FONTS_LIST[self.sign_font.font_idx][0])

        hbox.pack_start(self.sign_font, True, True, 0)
        self.sign_font.connect("clicked", self.set_sign_font)

        color = Gdk.RGBA()
        Gdk.RGBA.parse(color, self.acbf_document.font_colors["sign"])
        color_button = gtk.ColorButton()
        color_button.set_rgba(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'sign')
        hbox.pack_start(color_button, False, False, 0)

        hbox.show_all()
        entries_box.pack_start(hbox, True, False, 0)
        
        # show it
        self.vbox.pack_start(entries_box, True, False, 0)
        self.show_all()

    def save_styles(self, *args):
          style = ''

          if self.speech_font.font_idx > 0:
            self.acbf_document.font_styles["normal"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.speech_font.font_idx][1]))
            style = 'text-area {font-family: "' + os.path.basename(self.acbf_document.font_styles["normal"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.speech_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.speech_font.font_idx][1], self.acbf_document.font_styles["normal"])
            style = style + 'color: "' + self.acbf_document.font_colors["speech"] + '";}\n'
          if self.emphasis_font.font_idx > 0:
            self.acbf_document.font_styles["emphasis"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.emphasis_font.font_idx][1]))
            style = style + 'emphasis {font-family: "' + os.path.basename(self.acbf_document.font_styles["emphasis"]) + '";}\n'
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.emphasis_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.emphasis_font.font_idx][1], self.acbf_document.font_styles["emphasis"])
          if self.strong_font.font_idx > 0:
            self.acbf_document.font_styles["strong"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.strong_font.font_idx][1]))
            style = style + 'strong {font-family: "' + os.path.basename(self.acbf_document.font_styles["strong"]) + '";}\n'
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.strong_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.strong_font.font_idx][1], self.acbf_document.font_styles["strong"])
          if self.commentary_font.font_idx > 0:
            self.acbf_document.font_styles["commentary"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.commentary_font.font_idx][1]))
            style = style + 'text-area[type=commentary] {font-family: "' + os.path.basename(self.acbf_document.font_styles["commentary"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.commentary_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.commentary_font.font_idx][1], self.acbf_document.font_styles["commentary"])
            style = style + 'color: "' + self.acbf_document.font_colors["commentary"] + '";}\n'
          if self.code_font.font_idx > 0:
            self.acbf_document.font_styles["code"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.code_font.font_idx][1]))
            style = style + 'text-area[type=code] {font-family: "' + os.path.basename(self.acbf_document.font_styles["code"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.code_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.code_font.font_idx][1], self.acbf_document.font_styles["code"])
            style = style + 'color: "' + self.acbf_document.font_colors["code"] + '";}\n'
          if self.formal_font.font_idx > 0:
            self.acbf_document.font_styles["formal"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.formal_font.font_idx][1]))
            style = style + 'text-area[type=formal] {font-family: "' + os.path.basename(self.acbf_document.font_styles["formal"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.formal_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.formal_font.font_idx][1], self.acbf_document.font_styles["formal"])
            style = style + 'color: "' + self.acbf_document.font_colors["formal"] + '";}\n'
          if self.letter_font.font_idx > 0:
            self.acbf_document.font_styles["letter"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.letter_font.font_idx][1]))
            style = style + 'text-area[type=letter] {font-family: "' + os.path.basename(self.acbf_document.font_styles["letter"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.letter_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.letter_font.font_idx][1], self.acbf_document.font_styles["letter"])
            style = style + 'color: "' + self.acbf_document.font_colors["letter"] + '";}\n'
          if self.heading_font.font_idx > 0:
            self.acbf_document.font_styles["heading"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.heading_font.font_idx][1]))
            style = style + 'text-area[type=heading] {font-family: "' + os.path.basename(self.acbf_document.font_styles["heading"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.heading_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.heading_font.font_idx][1], self.acbf_document.font_styles["heading"])
            style = style + 'color: "' + self.acbf_document.font_colors["heading"] + '";}\n'
          if self.audio_font.font_idx > 0:
            self.acbf_document.font_styles["audio"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.audio_font.font_idx][1]))
            style = style + 'text-area[type=audio] {font-family: "' + os.path.basename(self.acbf_document.font_styles["audio"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.audio_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.audio_font.font_idx][1], self.acbf_document.font_styles["audio"])
            style = style + 'color: "' + self.acbf_document.font_colors["audio"] + '";}\n'
          if self.thought_font.font_idx > 0:
            self.acbf_document.font_styles["thought"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.thought_font.font_idx][1]))
            style = style + 'text-area[type=thought] {font-family: "' + os.path.basename(self.acbf_document.font_styles["thought"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.thought_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.thought_font.font_idx][1], self.acbf_document.font_styles["thought"])
            style = style + 'color: "' + self.acbf_document.font_colors["thought"] + '";}\n'
          if self.sign_font.font_idx > 0:
            self.acbf_document.font_styles["sign"] = os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.sign_font.font_idx][1]))
            style = style + 'text-area[type=sign] {font-family: "' + os.path.basename(self.acbf_document.font_styles["sign"]) + '"; '
            if not os.path.isfile(os.path.join(self.fonts_dir, os.path.basename(constants.FONTS_LIST[self.sign_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.sign_font.font_idx][1], self.acbf_document.font_styles["sign"])
            style = style + 'color: "' + self.acbf_document.font_colors["sign"] + '";}\n'

          #print(style)
          if style != '':
            try:
              self.acbf_document.tree.find("style").text = style
            except:
              element = xml.SubElement(self.acbf_document.tree.getroot(), "style", type="text/css")
              element.text = str(style)

          # delete unused files
          for root, dirs, files in os.walk(self.fonts_dir):
            for f in files:
              if f.upper()[-4:] == '.TTF' or f.upper()[-4:] == '.OTF':
                if os.path.join(root, f) not in self.acbf_document.font_styles.values():
                  os.remove(os.path.join(root, f))
          
    def set_font_color(self, widget, style):
        font_color = widget.get_color().to_string()
        if len(font_color) == 13:
          font_color = '#' + font_color[1:3] + font_color[5:7] + font_color[9:11]
        self.acbf_document.font_colors[style] = font_color
        self.isChanged = True
        return True

    def set_speech_font(self, widget):
        self.font_idx = self.speech_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Speech Font", self.speech_font.font_idx)
        self.speech_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.speech_font.font_idx = self.font_idx
        return True

    def set_commentary_font(self, widget):
        self.font_idx = self.commentary_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Commentary Font", self.commentary_font.font_idx)
        self.commentary_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.commentary_font.font_idx = self.font_idx
        return True

    def set_code_font(self, widget):
        self.font_idx = self.code_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Code Font", self.code_font.font_idx)
        self.code_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.code_font.font_idx = self.font_idx
        return True

    def set_formal_font(self, widget):
        self.font_idx = self.formal_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Formal Font", self.formal_font.font_idx)
        self.formal_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.formal_font.font_idx = self.font_idx
        return True

    def set_letter_font(self, widget):
        self.font_idx = self.letter_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Formal Font", self.letter_font.font_idx)
        self.letter_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.letter_font.font_idx = self.font_idx
        return True

    def set_heading_font(self, widget):
        self.font_idx = self.heading_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Heading Font", self.heading_font.font_idx)
        self.heading_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.heading_font.font_idx = self.font_idx
        return True

    def set_audio_font(self, widget):
        self.font_idx = self.audio_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Audio Font", self.audio_font.font_idx)
        self.audio_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.audio_font.font_idx = self.font_idx
        return True

    def set_thought_font(self, widget):
        self.font_idx = self.thought_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Thought Font", self.thought_font.font_idx)
        self.thought_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.thought_font.font_idx = self.font_idx
        return True

    def set_sign_font(self, widget):
        self.font_idx = self.sign_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Sign Font", self.sign_font.font_idx)
        self.sign_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.sign_font.font_idx = self.font_idx
        return True

    def set_emphasis_font(self, widget):
        self.font_idx = self.emphasis_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Emphasis Font", self.emphasis_font.font_idx)
        self.emphasis_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.emphasis_font.font_idx = self.font_idx
        return True

    def set_strong_font(self, widget):
        self.font_idx = self.strong_font.font_idx
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Strong Font", self.strong_font.font_idx)
        self.strong_font.set_label(constants.FONTS_LIST[self.font_idx][0])
        self.strong_font.font_idx = self.font_idx
        return True
