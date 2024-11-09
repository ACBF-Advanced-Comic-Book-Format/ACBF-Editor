"""main.py - Main window.

Copyright (C) 2011-2024 Robert Kubik
https://github.com/GeoRW/ACBF
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

import sys
import os
import random

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf

from PIL import Image
import io
import lxml.etree as xml
from copy import deepcopy
import zipfile
import shutil
import time
from xml.sax.saxutils import escape, unescape
import re

try:
  from . import constants
  from . import toolbar
  from . import acbfdocument
  from . import filechooser
  from . import fileprepare
  from . import preferences
  from . import prefsdialog
  from . import frames_editor
  from . import fontselectiondialog
  from . import text_layer as tl
except Exception:
  import constants
  import toolbar
  import acbfdocument
  import filechooser
  import fileprepare
  import preferences
  import prefsdialog
  import frames_editor
  import fontselectiondialog
  import text_layer as tl

class MainWindow(gtk.Window):

    """The ACBF main window"""

    def __init__(self, open_path=None, output_file=None, cmd_options=None):
        # Preferences
        self.preferences = preferences.Preferences()
        self._window = self
        self.font_idx = 0

        # Start variables
        self.is_modified = False
        if self.preferences.get_value("hidpi") == 'True':
          self.ui_scale_factor = 2
        else:
          self.ui_scale_factor = 1
        
        # check if custom temp dir is defined
        self.tempdir_root = str(os.path.join(self.preferences.get_value("tmpfs_dir"), 'acbfe'))
        if self.preferences.get_value("tmpfs") != 'False':
          print("Temporary directory override set to: " + self.tempdir_root)
        else:
          self.tempdir_root = constants.DATA_DIR
        self.tempdir =  str(os.path.join(self.tempdir_root, ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for i in range(10))))

        if not os.path.exists(self.tempdir):
          os.makedirs(self.tempdir, 0o700)

        self.filename = open_path
        if self.filename == None:
          self.filename = "/home/whale/Work/ACBF/trunk/xSample Comic Book/Doctorow, Cory - Craphound.acbf"
          self.original_filename = self.filename
        else:
          if output_file == None:
            prepared_file = fileprepare.FilePrepare(self, open_path, self.tempdir, True)
          else:
            prepared_file = fileprepare.FilePrepare(self, open_path, self.tempdir, False)
          self.filename = prepared_file.filename
          self.original_filename = open_path

        try:
          self.original_file_size = round(float(os.path.getsize(open_path))/1024/1024, 2)
        except:
          self.original_file_size = 1

        self.acbf_document = acbfdocument.ACBFDocument(self, self.filename)
        self.annotation_list = self.acbf_document.annotation
        self.book_title_list = self.acbf_document.book_title
        for lang in self.acbf_document.languages:
          if lang[0] != '??':
            if not lang[0] in self.annotation_list:
              self.annotation_list[lang[0]] = ''
            if not lang[0] in self.book_title_list:
              self.book_title_list[lang[0]] = ''

        # Command line processing
        self.is_cmd_line = False
        if output_file != None:
          self.is_cmd_line = True
          convert_format = None
          convert_quality = None
          resize_geometry = None
          resize_filter = None
          text_layer = None
          for opt, value in cmd_options:
            if opt in ('-f', '--format'):
              formats_supported = ('JPG', 'PNG', 'GIF', 'WEBP', 'BMP')
              if value.upper() not in formats_supported:
                print('Error: Unrecognized image format:', value + '. Use one of following: ' + str(formats_supported).replace('(', '').replace(')', '').replace('\'', ''))
                self.exit_program()
              else:
                convert_format = value
            if opt in ('-q', '--quality'):
              try:
                if int(value) > 0 and int(value) < 101:
                  convert_quality = int(value)
                else:
                  raise ValueError('Image quality must be an integer between 0 and 100.')
              except:
                print('')
                print('Error: Image quality must be an integer between 0 and 100.')
                self.exit_program()
            if opt in ('-r', '--resize'):
              if re.match('[0-9]*x[0-9]*[<>]', value) != None:
                resize_geometry = value
              else:
                print('')
                print('Error: Image geometry must be in format [width]x[height][flag].')
                print('[width] and [height] defines target image size as integer.')
                print('[flag] defines wheather to shrink (>) or enlarge (<) target image.')
                self.exit_program()
            if opt in ('-l', '--filter'):
              if value.upper() not in ('NEAREST', 'BILINEAR', 'BICUBIC', 'ANTIALIAS'):
                print('Error: Unrecognized resize filter:', value + '. Use one of following: NEAREST, BILINEAR, BICUBIC, ANTIALIAS.')
                self.exit_program()
              else:
                resize_filter = value
            if opt in ('-t', '--text_layer'):
              lang_found = False
              for idx, lang in enumerate(self.acbf_document.languages):
                if lang[0] == value and lang[1] == 'TRUE':
                  lang_found = True
                  text_layer = idx
              if not lang_found:
                print('Error: Language layer', value, 'is not defined in comic book.')
                self.exit_program()
              else:
                for item in self.acbf_document.tree.findall("meta-data/book-info/languages/text-layer"):
                  if item.get("show").upper() == 'FALSE':
                    item.attrib['lang'] = value

          if convert_format != None or resize_geometry != None or text_layer != None:
            self.convert_images(convert_format, convert_quality, resize_geometry, resize_filter, text_layer)
          self.write_file(output_file)
          self.exit_program()

        # Window properties
        gtk.Window.__init__(self, gtk.WindowType.TOPLEVEL)
        self.set_title('ACBF Editor')
        self.set_size_request(1200 * self.ui_scale_factor, 800 * self.ui_scale_factor)
        self.isFullscreen = False
        self.PixBufImage_width = self.PixBufImage_height = 0
        book_title = ''
        if self.acbf_document.valid:
          try:
            book_title = unescape(self.acbf_document.book_title[self.toolbar.language.get_active_text()])
          except:
            book_title = unescape(self.acbf_document.book_title[list(self.acbf_document.book_title.items())[0][0]])

        self.set_title('%s - ACBF Editor' % book_title)

        # Toolbar
        vbox = gtk.VBox(False, 0)
        self.toolbar = toolbar.Toolbar(self)
        self.toolbar.show_all()
        vbox.pack_start(self.toolbar, False, False, 0)

        self.main_box = gtk.HBox(False, 0)
        vbox.pack_start(self.main_box, True, True, 0)
        self.prior_language = self.toolbar.language.get_active_text()

        # Coverpage box
        left_box = gtk.VBox(False, 0)
        self.coverpage = gtk.Image()
        self.coverpage.set_from_pixbuf(self.pil_to_pixbuf(self.acbf_document.cover_thumb, '#000'))
        self.coverpage.set_alignment(0.5, 0)
        left_box.pack_start(self.coverpage, False, True, 10)
        left_box.set_border_width(5)

        self.main_box.pack_start(left_box, False, True, 5)

        # Edit box
        notebook = gtk.Notebook()
        notebook.set_border_width(3)

        # book-info
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        tab = gtk.VBox(False, 0)
        tab.set_border_width(5)
        scrolled.add_with_viewport(tab)

        ## Title
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Title</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.book_title = gtk.Entry()
        self.book_title.show()
        hbox.pack_start(self.book_title, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Authors
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Author(s)</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.authors = gtk.Entry()
        self.authors.set_has_frame(False)
        self.authors.set_editable(False)
        self.authors.set_can_focus(False)
        hbox.pack_start(self.authors, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_authors)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Series
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Serie(s)</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.series = gtk.Entry()
        self.series.set_has_frame(False)
        self.series.set_editable(False)
        self.series.set_can_focus(False)
        hbox.pack_start(self.series, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_series)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Genres
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Genre(s)</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.genres = gtk.Entry()
        self.genres.set_has_frame(False)
        self.genres.set_editable(False)
        self.genres.set_can_focus(False)
        hbox.pack_start(self.genres, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_genres)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Characters
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Characters</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.characters = gtk.Entry()
        self.characters.set_has_frame(False)
        self.characters.set_editable(False)
        self.characters.set_can_focus(False)
        hbox.pack_start(self.characters, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_characters)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Annotation
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Annotation</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.annotation = gtk.TextView()
        self.annotation.set_wrap_mode(gtk.WrapMode.WORD)
        self.annotation.show()
        hbox.pack_start(self.annotation, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Keywords
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Keywords</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.keywords = gtk.Entry()
        self.keywords.show()
        hbox.pack_start(self.keywords, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Languages
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Languages</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.languages = gtk.Entry()
        self.languages.set_has_frame(False)
        self.languages.set_editable(False)
        self.languages.set_can_focus(False)
        self.languages.show()
        hbox.pack_start(self.languages, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_languages)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        ## databaseref
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Database Reference</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.databaseref = gtk.Entry()
        self.databaseref.set_has_frame(False)
        self.databaseref.set_editable(False)
        self.databaseref.set_can_focus(False)
        self.databaseref.show()
        hbox.pack_start(self.databaseref, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_databaseref)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)


        notebook.insert_page(scrolled, gtk.Label('Book-Info'), -1)

        # publish-info
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        tab = gtk.VBox(False, 0)
        tab.set_border_width(5)
        scrolled.add_with_viewport(tab)

        ## Publisher
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Publisher</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.publisher = gtk.Entry()
        self.publisher.show()
        hbox.pack_start(self.publisher, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Publish Date
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Publish Date</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.publish_date = gtk.Entry()
        self.publish_date.set_has_frame(False)
        self.publish_date.set_editable(False)
        self.publish_date.set_can_focus(False)
        self.publish_date.show()
        hbox.pack_start(self.publish_date, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_publish_date)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        ## City
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>City</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.city = gtk.Entry()
        self.city.show()
        hbox.pack_start(self.city, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## ISBN
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>ISBN</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.isbn = gtk.Entry()
        self.isbn.show()
        hbox.pack_start(self.isbn, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## License
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>License</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.license = gtk.Entry()
        self.license.show()
        hbox.pack_start(self.license, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        #
        notebook.insert_page(scrolled, gtk.Label('Publish-Info'), -1)

        # document-info
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
        tab = gtk.VBox(False, 0)
        tab.set_border_width(5)
        scrolled.add_with_viewport(tab)

        ## Doc ID
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Document ID</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.doc_id = gtk.Entry()
        self.doc_id.set_has_frame(False)
        self.doc_id.set_editable(False)
        self.doc_id.set_can_focus(False)
        self.doc_id.set_tooltip_text('Unique document ID (UUID)')
        hbox.pack_start(self.doc_id, True, True, 0)

        tab.pack_start(hbox, False, False, 0)

        ## Author
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        label = gtk.Label()
        label.set_markup('<b>Author(s)</b>: ')
        hbox.pack_start(label, False, False, 0)

        self.doc_author = gtk.Entry()
        self.doc_author.set_has_frame(False)
        self.doc_author.set_editable(False)
        self.doc_author.set_can_focus(False)
        hbox.pack_start(self.doc_author, True, True, 0)

        button =  gtk.Button('...')
        button.connect('clicked', self.edit_doc_authors)
        hbox.pack_start(button, False, False, 0)

        tab.pack_start(hbox, False, False, 0)

        #
        notebook.insert_page(scrolled, gtk.Label('Document-Info'), -1)

        #
        self.update_forms(True)
        self.main_box.pack_start(notebook, True, True, 0)
        self.add(vbox)

        # Events
        self.connect('delete_event', self.terminate_program)

        if not self.acbf_document.valid:
          set_sensitivity(self.main_box, False, 0)
          self.toolbar.save_button.set_sensitive(False)
          self.toolbar.frames_button.set_sensitive(False)
          self.toolbar.font_button.set_sensitive(False)

        # show
        self.show_all()

    def convert_images(self, im_format, im_quality, im_geometry, im_filter, im_text_layer):
      #print('Format:', im_format, 'Quality:', im_quality, 'Resize:', im_geometry, 'Filter:', im_filter, 'Text-layer', im_text_layer)
      resize_filters = {'NEAREST': 0, 'BILINEAR': 2, 'BICUBIC': 3, 'ANTIALIAS': 1}
      if im_filter == None:
        im_filter = 'ANTIALIAS'

      for idx, page in enumerate(self.acbf_document.pages, start = 1):
        in_path = os.path.join(self.tempdir, page.find("image").get("href").replace("\\", "/"))
        in_path_short = in_path[len(self.tempdir) + 1:]
        if im_format == None:
          im_format = os.path.splitext(in_path)[1][1:]
        out_path = os.path.splitext(in_path)[0] + '.' + im_format.lower()
        out_path_short = out_path[len(self.tempdir) + 1:]
        page.find("image").attrib['href'] = out_path_short
        perc_done = str(int(round(float(idx)/float(self.acbf_document.pages_total) * 100, 0))).rjust(4) + '%'
        print(perc_done, in_path_short, '->', out_path_short)

        #convert image
        if in_path != out_path or im_geometry != None or im_text_layer != None:
          if im_text_layer != None and idx > 0:
            xx = tl.TextLayer(in_path, idx + 1, self.acbf_document, im_text_layer, self.acbf_document.font_styles['normal'],
                              self.acbf_document.font_styles['strong'], self.acbf_document.font_styles['emphasis'],
                              self.acbf_document.font_styles['code'], self.acbf_document.font_styles['commentary'],
                              self.acbf_document.font_styles['sign'], self.acbf_document.font_styles['formal'],
                              self.acbf_document.font_styles['heading'], self.acbf_document.font_styles['letter'],
                              self.acbf_document.font_styles['audio'], self.acbf_document.font_styles['thought'])
            im = xx.PILBackgroundImage
          else:
            im = Image.open(in_path).convert('RGB')        

          # resize
          if im_geometry != None:
            geometry_flag = im_geometry[-1:]
            geometry_x = int(im_geometry[0:im_geometry.find('x')])
            geometry_y = int(im_geometry[im_geometry.find('x') + 1:-1])
            ratio_x = geometry_x / float(im.size[0])
            ratio_y = geometry_y / float(im.size[1])
            ratio = min(ratio_x, ratio_y)

            if ((geometry_flag == '>' and (im.size[0] > geometry_x or im.size[1] > geometry_y)) or
                (geometry_flag == '<' and (im.size[0] < geometry_x and im.size[1] < geometry_y))
                ):
              # scale image
              im = im.resize([int(ratio * s) for s in im.size], resize_filters[im_filter])
              # scale frames
              for frame in page.findall("frame"):
                new_coord = ''
                for coord in frame.get("points").split(' '):
                  new_point = (round(int(coord.split(',')[0])*ratio, 0), round(int(coord.split(',')[1])*ratio, 0))
                  new_coord = new_coord + str(int(new_point[0])) + ',' + str(int(new_point[1])) + ' '

                frame.attrib['points'] = new_coord.strip()
              # scale text-layers
              for text_layer in page.findall("text-layer"):
                for text_area in text_layer.findall("text-area"):
                  new_coord = ''
                  for coord in text_area.get("points").split(' '):
                    new_point = (round(int(coord.split(',')[0])*ratio, 0), round(int(coord.split(',')[1])*ratio, 0))
                    new_coord = new_coord + str(int(new_point[0])) + ',' + str(int(new_point[1])) + ' '

                  text_area.attrib['points'] = new_coord.strip()

          # save
          if im_quality != None:
            im.save(out_path, quality=im_quality)
          else:
            im.save(out_path)

        # delete original image
        if in_path != out_path:
          os.remove(in_path)

    def open_preferences(self, *args):
      self.prefs_dialog = prefsdialog.PrefsDialog(self)
      if self.prefs_dialog.isChanged:
        self.preferences.save_preferences()
        self.prefs_dialog.destroy()
      else:
        self.prefs_dialog.destroy()
      return

    def edit_styles(self, *args):
        dialog = gtk.Dialog('Edit Styles/Fonts Definitions', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)

        # Create Font list
        fonts_dir = os.path.join(self.tempdir, 'Fonts')
        for root, dirs, files in os.walk(fonts_dir):
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["normal"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["emphasis"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["strong"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["commentary"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["code"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["formal"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["letter"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["heading"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["audio"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["thought"]))[0]:
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
          if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["sign"]))[0]:
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
        dialog.vbox.pack_start(entries_box, True, False, 0)
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True
          style = ''

          if self.speech_font.font_idx > 0:
            self.acbf_document.font_styles["normal"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.speech_font.font_idx][1]))
            style = 'text-area {font-family: "' + os.path.basename(self.acbf_document.font_styles["normal"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.speech_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.speech_font.font_idx][1], self.acbf_document.font_styles["normal"])
            style = style + 'color: "' + self.acbf_document.font_colors["speech"] + '";}\n'
          if self.emphasis_font.font_idx > 0:
            self.acbf_document.font_styles["emphasis"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.emphasis_font.font_idx][1]))
            style = style + 'emphasis {font-family: "' + os.path.basename(self.acbf_document.font_styles["emphasis"]) + '";}\n'
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.emphasis_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.emphasis_font.font_idx][1], self.acbf_document.font_styles["emphasis"])
          if self.strong_font.font_idx > 0:
            self.acbf_document.font_styles["strong"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.strong_font.font_idx][1]))
            style = style + 'strong {font-family: "' + os.path.basename(self.acbf_document.font_styles["strong"]) + '";}\n'
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.strong_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.strong_font.font_idx][1], self.acbf_document.font_styles["strong"])
          if self.commentary_font.font_idx > 0:
            self.acbf_document.font_styles["commentary"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.commentary_font.font_idx][1]))
            style = style + 'text-area[type=commentary] {font-family: "' + os.path.basename(self.acbf_document.font_styles["commentary"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.commentary_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.commentary_font.font_idx][1], self.acbf_document.font_styles["commentary"])
            style = style + 'color: "' + self.acbf_document.font_colors["commentary"] + '";}\n'
          if self.code_font.font_idx > 0:
            self.acbf_document.font_styles["code"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.code_font.font_idx][1]))
            style = style + 'text-area[type=code] {font-family: "' + os.path.basename(self.acbf_document.font_styles["code"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.code_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.code_font.font_idx][1], self.acbf_document.font_styles["code"])
            style = style + 'color: "' + self.acbf_document.font_colors["code"] + '";}\n'
          if self.formal_font.font_idx > 0:
            self.acbf_document.font_styles["formal"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.formal_font.font_idx][1]))
            style = style + 'text-area[type=formal] {font-family: "' + os.path.basename(self.acbf_document.font_styles["formal"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.formal_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.formal_font.font_idx][1], self.acbf_document.font_styles["formal"])
            style = style + 'color: "' + self.acbf_document.font_colors["formal"] + '";}\n'
          if self.letter_font.font_idx > 0:
            self.acbf_document.font_styles["letter"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.letter_font.font_idx][1]))
            style = style + 'text-area[type=letter] {font-family: "' + os.path.basename(self.acbf_document.font_styles["letter"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.letter_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.letter_font.font_idx][1], self.acbf_document.font_styles["letter"])
            style = style + 'color: "' + self.acbf_document.font_colors["letter"] + '";}\n'
          if self.heading_font.font_idx > 0:
            self.acbf_document.font_styles["heading"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.heading_font.font_idx][1]))
            style = style + 'text-area[type=heading] {font-family: "' + os.path.basename(self.acbf_document.font_styles["heading"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.heading_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.heading_font.font_idx][1], self.acbf_document.font_styles["heading"])
            style = style + 'color: "' + self.acbf_document.font_colors["heading"] + '";}\n'
          if self.audio_font.font_idx > 0:
            self.acbf_document.font_styles["audio"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.audio_font.font_idx][1]))
            style = style + 'text-area[type=audio] {font-family: "' + os.path.basename(self.acbf_document.font_styles["audio"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.audio_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.audio_font.font_idx][1], self.acbf_document.font_styles["audio"])
            style = style + 'color: "' + self.acbf_document.font_colors["audio"] + '";}\n'
          if self.thought_font.font_idx > 0:
            self.acbf_document.font_styles["thought"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.thought_font.font_idx][1]))
            style = style + 'text-area[type=thought] {font-family: "' + os.path.basename(self.acbf_document.font_styles["thought"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.thought_font.font_idx][1]))):
              shutil.copyfile(constants.FONTS_LIST[self.thought_font.font_idx][1], self.acbf_document.font_styles["thought"])
            style = style + 'color: "' + self.acbf_document.font_colors["thought"] + '";}\n'
          if self.sign_font.font_idx > 0:
            self.acbf_document.font_styles["sign"] = os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.sign_font.font_idx][1]))
            style = style + 'text-area[type=sign] {font-family: "' + os.path.basename(self.acbf_document.font_styles["sign"]) + '"; '
            if not os.path.isfile(os.path.join(fonts_dir, os.path.basename(constants.FONTS_LIST[self.sign_font.font_idx][1]))):
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
          for root, dirs, files in os.walk(fonts_dir):
            for f in files:
              if f.upper()[-4:] == '.TTF' or f.upper()[-4:] == '.OTF':
                if os.path.join(root, f) not in self.acbf_document.font_styles.values():
                  os.remove(os.path.join(root, f))
          
        dialog.destroy()
        return

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
    
    def edit_doc_authors(self, *args):
        dialog = gtk.Dialog('Edit Document Authors', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)

        # Authors Dropdowns
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        for i in self.acbf_document.tree.findall("meta-data/document-info/author"):
          first_name = middle_name = last_name = ''
          if i.find("first-name") is not None:
             first_name = i.find("first-name").text
          if i.find("middle-name") is not None:
             middle_name = i.find("middle-name").text
          if i.find("last-name") is not None:
             last_name = i.find("last-name").text
          if i.find("nickname") is not None:
             nickname = i.find("nickname").text
          self.add_doc_authors_hbox(None, entries_box, first_name, middle_name, last_name, nickname)

        dialog.vbox.pack_start(entries_box, False, False, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_doc_authors_hbox, entries_box, '', '', '', '')
        hbox.pack_start(button, False, False, 0)

        dialog.vbox.pack_start(hbox, False, False, 0)

        # show it
        dialog.show_all()
        response = dialog.run()

        # save
        if response == gtk.ResponseType.OK:
          self.is_modified = True
          for item in self.acbf_document.tree.findall("meta-data/document-info/author"):
            self.acbf_document.tree.find("meta-data/document-info").remove(item)

          for i in entries_box.get_children():
            activity = ''
            for j in i.get_children():
              if j.get_name() == 'GtkEntry':
                if j.type == 'first_name':
                  first_name = j.get_text()
                if j.type == 'middle_name':
                  middle_name = j.get_text()
                if j.type == 'last_name':
                  last_name = j.get_text()
                if j.type == 'nickname':
                  nickname = j.get_text()

            element = xml.SubElement(self.acbf_document.tree.find("meta-data/document-info"), "author")
            self.add_element(element, "first-name", first_name)
            self.add_element(element, "middle-name", middle_name)
            self.add_element(element, "last-name", last_name)
            self.add_element(element, "nickname", nickname)

          self.acbf_document.load_metadata()
          self.update_forms(False)

        dialog.destroy()
        return

    def add_doc_authors_hbox(self, widget, entries_box, first_name, middle_name, last_name, nickname):
      hbox = gtk.HBox(False, 0)

      entry = gtk.Entry()
      entry.set_text(first_name)
      entry.type = 'first_name'
      entry.set_tooltip_text('first_name')
      hbox.pack_start(entry, True, True, 0)

      entry = gtk.Entry()
      entry.set_text(middle_name)
      entry.type = 'middle_name'
      entry.set_tooltip_text('middle_name')
      hbox.pack_start(entry, True, True, 0)

      entry = gtk.Entry()
      entry.set_text(last_name)
      entry.type = 'last_name'
      entry.set_tooltip_text('last_name')
      hbox.pack_start(entry, True, True, 0)

      entry = gtk.Entry()
      entry.set_text(nickname)
      entry.type = 'nickname'
      entry.set_tooltip_text('nickname')
      hbox.pack_start(entry, True, True, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      return

    def edit_authors(self, *args):
        dialog = gtk.Dialog('Edit Authors', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)

        # Authors Dropdowns
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        hbox = gtk.HBox(False, 0)
        label = gtk.Label()
        label.set_markup('<b>Activity             </b>')
        hbox.pack_start(label, False, True, 0)

        label = gtk.Label()
        label.set_markup('<b>Lang</b>')
        hbox.pack_start(label, False, True, 0)

        label = gtk.Label()
        label.set_markup('<b>First Name</b>')
        hbox.pack_start(label, True, True, 0)

        label = gtk.Label()
        label.set_markup('<b>Middle Name</b>')
        hbox.pack_start(label, True, True, 0)

        label = gtk.Label()
        label.set_markup('<b>Last Name</b>')
        label.set_alignment(0, 0)
        hbox.pack_start(label, True, True, 0)

        entries_box.pack_start(hbox, False, False, 0)

        for i in self.acbf_document.tree.findall("meta-data/book-info/author"):
          first_name = middle_name = last_name = ''
          if i.find("first-name") is not None:
             first_name = i.find("first-name").text
          if i.find("middle-name") is not None:
            if i.find("middle-name").text is not None:
               middle_name = i.find("middle-name").text
          if i.find("last-name") is not None:
             last_name = i.find("last-name").text
          self.add_authors_hbox(None, entries_box, i.get("activity"), i.get("lang"), first_name, middle_name, last_name)

        if len(self.acbf_document.tree.findall("meta-data/book-info/author")) == 0:
          self.add_authors_hbox(None, entries_box, "Writer", self.toolbar.language.get_active_text(), "", "", "")
          self.add_authors_hbox(None, entries_box, "Penciller", self.toolbar.language.get_active_text(), "", "", "")
          self.add_authors_hbox(None, entries_box, "Inker", self.toolbar.language.get_active_text(), "", "", "")
          self.add_authors_hbox(None, entries_box, "Letterer", self.toolbar.language.get_active_text(), "", "", "")
          self.add_authors_hbox(None, entries_box, "Colorist", self.toolbar.language.get_active_text(), "", "", "")
          self.add_authors_hbox(None, entries_box, "CoverArtist", self.toolbar.language.get_active_text(), "", "", "")

        dialog.vbox.pack_start(entries_box, False, False, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_authors_hbox, entries_box, 'Translator', self.preferences.get_value("default_language"), '', '', '')
        hbox.pack_start(button, False, False, 0)

        dialog.vbox.pack_start(hbox, False, False, 0)

        # show it
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True
          for item in self.acbf_document.tree.findall("meta-data/book-info/author"):
            self.acbf_document.tree.find("meta-data/book-info").remove(item)

          for i in entries_box.get_children():
            if i.get_children()[0].get_name() == 'GtkLabel':
                continue
            activity = ''
            for j in i.get_children():
              if j.get_name() == 'GtkComboBox':
                if j.type == 'activity':
                  activity = str(constants.AUTHORS_LIST[j.get_active()])
                if j.type == 'lang':
                  lang = str(constants.LANGUAGES[j.get_active()])
              if j.get_name() == 'GtkEntry':
                if j.type == 'first_name':
                  first_name = j.get_text()
                if j.type == 'middle_name':
                  middle_name = j.get_text()
                if j.type == 'last_name':
                  last_name = j.get_text()
                
            if (first_name != None and first_name != '' and last_name != None and last_name != ''):
              if activity == 'Translator':
                element = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "author", activity=activity, lang=lang)
              else:
                element = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "author", activity=activity)
              self.add_element(element, "first-name", first_name)
              self.add_element(element, "middle-name", middle_name)
              self.add_element(element, "last-name", last_name)

          self.acbf_document.load_metadata()
          self.update_forms(False)

        dialog.destroy()
        return

    def change_activity(self, widget, hbox):
      for i in hbox.get_children():
        if i.get_name() == 'GtkComboBox':
          if i.type == 'lang' and str(constants.AUTHORS_LIST[widget.get_active()]) == 'Translator':
            i.set_sensitive(True)
          elif i.type == 'lang':
            i.set_sensitive(False)

    def add_authors_hbox(self, widget, entries_box, activity, lang, first_name, middle_name, last_name):
      hbox = gtk.HBox(False, 0)
      dropdown = gtk.ComboBoxText()
      dropdown.type = 'activity'
      dropdown.set_tooltip_text('activity')
      active_dropdown = 0
      for idx, item in enumerate(constants.AUTHORS_LIST):
        dropdown.append_text(item)
        if item == activity:
          active_dropdown = idx
      dropdown.set_active(active_dropdown)
      dropdown.connect('changed', self.change_activity, hbox)
      hbox.pack_start(dropdown, False, True, 0)

      dropdown = gtk.ComboBoxText()
      dropdown.type = 'lang'
      dropdown.set_tooltip_text('lang')
      active_dropdown = 0
      for idx, item in enumerate(constants.LANGUAGES):
        dropdown.append_text(item)
        if item == lang:
          active_dropdown = idx
      dropdown.set_active(active_dropdown)
      if activity != 'Translator':
        dropdown.set_sensitive(False)
      hbox.pack_start(dropdown, False, True, 0)

      entry = gtk.Entry()
      entry.set_text(first_name)
      entry.type = 'first_name'
      entry.set_tooltip_text('first_name')
      hbox.pack_start(entry, True, True, 0)

      entry = gtk.Entry()
      entry.set_text(middle_name)
      entry.type = 'middle_name'
      entry.set_tooltip_text('middle_name')
      hbox.pack_start(entry, True, True, 0)

      entry = gtk.Entry()
      entry.set_text(last_name)
      entry.type = 'last_name'
      entry.set_tooltip_text('last_name')
      hbox.pack_start(entry, True, True, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      return

    def edit_series(self, *args):
        dialog = gtk.Dialog('Edit Series', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)


        # Series Entries
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        hbox = gtk.HBox(False, 0)
        label = gtk.Label()
        label.set_markup('<b>Series Title</b>')
        label.set_alignment(0, 0)
        hbox.pack_start(label, True, True, 0)

        label = gtk.Label()
        label.set_markup('<b>Number       </b>')
        label.set_alignment(0, 0)
        hbox.pack_start(label, False, False, 0)

        entries_box.pack_start(hbox, False, False, 0)

        for item in self.acbf_document.tree.findall("meta-data/book-info/sequence"):
          self.add_series_hbox(None, entries_box, item.text, item.get("title"))

        dialog.vbox.pack_start(entries_box, False, False, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_series_hbox, entries_box, '', '')
        hbox.pack_start(button, False, False, 0)

        dialog.vbox.pack_start(hbox, False, False, 0)

        # show it
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True
          for item in self.acbf_document.tree.findall("meta-data/book-info/sequence"):
            self.acbf_document.tree.find("meta-data/book-info").remove(item)

          for i in entries_box.get_children():
            if i.get_children()[0].get_name() == 'GtkLabel':
              continue
            for j in i.get_children():
              if j.get_name() == 'GtkEntry':
                if j.type == 'title':
                  title = str(j.get_text())
                elif j.type == 'text':
                  text = str(j.get_text())

            element = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "sequence", title=title)
            element.text = text

          self.acbf_document.load_metadata()
          self.update_forms(False)

        dialog.destroy()
        return

    def add_series_hbox(self, widget, entries_box, text, title):
      hbox = gtk.HBox(False, 0)
      entry = gtk.Entry()
      if title != None:
        entry.set_text(title)
      entry.type = 'title'
      entry.set_width_chars(20)
      entry.set_tooltip_text('Series Title')
      hbox.pack_start(entry, True, True, 0)

      entry = gtk.Entry()
      if text != None:
        entry.set_text(text)
      entry.type = 'text'
      entry.set_width_chars(4)
      entry.set_tooltip_text('Sequence Number')
      hbox.pack_start(entry, False, False, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      entry.grab_focus()
      return

    def edit_genres(self, *args):
        dialog = gtk.Dialog('Edit Genres', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)

        # Genre Dropdowns
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        hbox = gtk.HBox(False, 0)
        label = gtk.Label()
        label.set_markup('<b>Genres</b>')
        hbox.pack_start(label, False, True, 0)

        entries_box.pack_start(hbox, False, False, 0)

        for item in self.acbf_document.tree.findall("meta-data/book-info/genre"):
          self.add_genres_hbox(None, entries_box, item.text)

        dialog.vbox.pack_start(entries_box, False, False, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_genres_hbox, entries_box, '')
        hbox.pack_start(button, False, False, 0)

        dialog.vbox.pack_start(hbox, False, False, 0)

        # show it
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True
          for item in self.acbf_document.tree.findall("meta-data/book-info/genre"):
            self.acbf_document.tree.find("meta-data/book-info").remove(item)

          for i in entries_box.get_children():
            for j in i.get_children():
              if j.get_name() == 'GtkComboBox':
                self.add_element(self.acbf_document.tree.find("meta-data/book-info"), "genre", constants.GENRES_LIST[j.get_active()])

          self.acbf_document.load_metadata()
          self.update_forms(False)

        dialog.destroy()
        return

    def add_genres_hbox(self, widget, entries_box, genre):
      hbox = gtk.HBox(False, 0)
      dropdown = gtk.ComboBoxText()
      active_dropdown = 0
      for idx, item in enumerate(constants.GENRES_LIST):
        dropdown.append_text(item)
        if item == genre:
          active_dropdown = idx

      dropdown.set_active(active_dropdown)
      hbox.pack_start(dropdown, True, True, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      return

    def edit_characters(self, *args):
        dialog = gtk.Dialog('Edit Characters', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)

        # Character Entries
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        hbox = gtk.HBox(False, 0)
        label = gtk.Label()
        label.set_markup('<b>Characters</b>')
        hbox.pack_start(label, False, True, 0)

        entries_box.pack_start(hbox, False, False, 0)

        for item in self.acbf_document.tree.findall("meta-data/book-info/characters/name"):
          self.add_characters_hbox(None, entries_box, item.text)

        dialog.vbox.pack_start(entries_box, False, False, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_characters_hbox, entries_box, '')
        hbox.pack_start(button, False, False, 0)

        dialog.vbox.pack_start(hbox, False, False, 0)

        # show it
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True
          to_remove = self.acbf_document.tree.find("meta-data/book-info/characters")
          if to_remove != None:
            self.acbf_document.tree.find("meta-data/book-info").remove(to_remove)
          self.modify_element("meta-data/book-info/characters", '')

          for i in entries_box.get_children():
            for j in i.get_children():
              if j.get_name() == 'GtkEntry':
                self.add_element(self.acbf_document.tree.find("meta-data/book-info/characters"), "name", j.get_text())

          self.acbf_document.load_metadata()
          self.update_forms(False)

        dialog.destroy()
        return

    def add_characters_hbox(self, widget, entries_box, text):
      hbox = gtk.HBox(False, 0)
      entry = gtk.Entry()
      entry.set_width_chars(20)
      entry.set_text(text)
      hbox.pack_start(entry, True, True, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      entry.grab_focus()
      return

    def edit_languages(self, *args):
        dialog = gtk.Dialog('Edit Languages', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_border_width(8)

        # Languages Dropdowns
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        hbox = gtk.HBox(False, 0)
        label = gtk.Label()
        label.set_markup('<b>Languages</b>')
        hbox.pack_start(label, False, True, 0)

        label = gtk.Label()
        label.set_markup('<b>Show   </b>')
        hbox.pack_start(label, True, True, 0)

        entries_box.pack_start(hbox, False, False, 0)

        for item in self.acbf_document.tree.findall("meta-data/book-info/languages/text-layer"):
          self.add_languages_hbox(None, entries_box, item.get("lang"), item.get("show"))

        dialog.vbox.pack_start(entries_box, False, False, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_languages_hbox, entries_box, self.preferences.get_value("default_language"), 'False')
        hbox.pack_start(button, False, False, 0)

        dialog.vbox.pack_start(hbox, False, False, 0)

        # show it
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True
          for item in self.acbf_document.tree.findall("meta-data/book-info/languages"):
            self.acbf_document.tree.find("meta-data/book-info").remove(item)
          element = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "languages")

          for i in entries_box.get_children():
            if i.get_children()[0].get_name() == 'GtkLabel':
              continue
            for j in i.get_children():
              if j.get_name() == 'GtkComboBox':
                lang = str(constants.LANGUAGES[j.get_active()])
              if j.get_name() == 'GtkCheckButton':
                if j.get_active():
                  show = 'true'
                else:
                  show = 'false'
            element = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info/languages"), "text-layer", lang=lang, show=show)

          self.acbf_document.load_metadata()
          for lang in self.acbf_document.languages:
            if not lang[0] in self.annotation_list:
              self.annotation_list[lang[0]] = ''
            if not lang[0] in self.book_title_list:
              self.book_title_list[lang[0]] = ''

          lang_list = []
          for lang in self.acbf_document.languages:
            if lang[1] not in lang_list:
              lang_list.append(lang[0])

          for i in self.annotation_list.items():
            if i[0] not in lang_list:
              try:
                del self.annotation_list[i[0]]
              except:
                print(i[0], ' not found.')
              try:
                del self.book_title_list[i[0]]
              except:
                print(i[0], ' not found.')
              self.toolbar.language.set_active(0)

          self.update_forms(False)
          self.toolbar.update()

        dialog.destroy()
        return

    def add_languages_hbox(self, widget, entries_box, lang, show):
      hbox = gtk.HBox(False, 0)
      dropdown = gtk.ComboBoxText()
      dropdown.set_tooltip_text('lang')
      active_dropdown = 0
      for idx, item in enumerate(constants.LANGUAGES):
        dropdown.append_text(item)
        if item == lang:
          active_dropdown = idx

      dropdown.set_active(active_dropdown)
      hbox.pack_start(dropdown, True, True, 0)

      check_button = gtk.CheckButton()
      check_button.set_tooltip_text('show (if ticked text layer will overlap underlying image)')
      if show.upper() == 'TRUE':
        check_button.set_active(True)
      hbox.pack_start(check_button, True, True, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      return

    def edit_databaseref(self, *args):
      return

    def edit_publish_date(self, *args):
      dialog = gtk.Dialog('Edit Publish Date', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
      dialog.set_resizable(True)
      dialog.set_border_width(8)

      # calendar
      self.calendar = gtk.Calendar()
      if self.publish_date.get_text() != '':
        calendar_date = self.publish_date.get_text()
      else:
        calendar_date = time.strftime("%Y-%m-%d")
      year = calendar_date[0:4]
      month = calendar_date[5:7]
      day = calendar_date[8:10]
      self.calendar.select_month(int(month) - 1, int(year))
      self.calendar.select_day(int(day))
      self.calendar.connect('month-changed', self.update_publish_date_entry)
      self.calendar.connect('day-selected', self.update_publish_date_entry)

      dialog.vbox.pack_start(self.calendar, False, False, 0)

      # manual entry
      hbox = gtk.HBox(False, 0)
      hbox.set_border_width(5)

      label = gtk.Label()
      label.set_markup('<b>(YYYY-MM-DD)</b>: ')
      hbox.pack_start(label, False, False, 0)

      self.publish_date_entry = gtk.Entry(10)
      self.publish_date_entry.set_width_chars(10)
      self.publish_date_entry.set_text(self.publish_date.get_text())
      self.publish_date_entry.connect('changed', self.update_calendar)
      self.publish_date_entry.show()
      hbox.pack_start(self.publish_date_entry, False, True, 0)

      dialog.vbox.pack_start(hbox, False, False, 0)

      # show it
      dialog.show_all()
      response = dialog.run()

      if response == gtk.ResponseType.OK:
        self.is_modified = True

        element = self.acbf_document.tree.find("meta-data/publish-info/publish-date")
        if element == None:
          element = xml.SubElement(self.acbf_document.tree.find("meta-data/publish-info"), "publish-date")
        element.text = str(self.publish_date_entry.get_text()[0:4])
        element.set('value', self.publish_date_entry.get_text())

        self.acbf_document.load_metadata()
        self.update_forms(False)

      dialog.destroy()
      return

    def update_publish_date_entry(self, widget):
      publish_date = self.calendar.get_date()
      self.publish_date_entry.set_text(str(publish_date[0]) + '-' + str(publish_date[1] + 1).zfill(2) + '-' + str(publish_date[2]).zfill(2))
      return

    def update_calendar(self, widget):
      year = self.publish_date_entry.get_text()[0:4]
      month = self.publish_date_entry.get_text()[5:7]
      day = self.publish_date_entry.get_text()[8:10]

      if year.isdigit() and month.isdigit() and day.isdigit() and len(day) == 2:
        try:
          self.calendar.select_month(int(month) - 1, int(year))
          self.calendar.select_day(int(day))
        except:
          print("Not a valid date")
      return


    def remove_hbox(self, widget, hbox):
      hbox.destroy()
      return

    def update_forms(self, is_new):
      if is_new:
        self.coverpage.set_from_pixbuf(self.pil_to_pixbuf(self.acbf_document.cover_thumb, '#000'))
        book_title = ''
        if self.acbf_document.valid:
          try:
            book_title = unescape(self.book_title_list[self.toolbar.language.get_active_text()])
          except:
            try:
              book_title = unescape(self.book_title_list['en'])
            except:
              book_title = ''

        try:
          self.annotation.get_buffer().set_text(unescape(self.annotation_list[self.toolbar.language.get_active_text()]))
        except:
          self.annotation.get_buffer().set_text('')
        self.set_title('%s - ACBF Editor' % book_title)
        self.book_title.set_text(book_title)
        self.keywords.set_text(self.acbf_document.keywords)
        self.publisher.set_text(unescape(self.acbf_document.publisher))
        self.city.set_text(self.acbf_document.city)
        self.isbn.set_text(self.acbf_document.isbn)
        self.license.set_text(self.acbf_document.license)

      self.authors.set_text(self.acbf_document.authors)

      if self.acbf_document.doc_authors == '' and self.acbf_document.valid:
        for item in self.acbf_document.tree.findall("meta-data/document-info/author"):
          self.acbf_document.tree.find("meta-data/document-info").remove(item)

        element = xml.SubElement(self.acbf_document.tree.find("meta-data/document-info"), "author")
        for author in ['first-name', 'middle-name', 'nickname', 'last-name']:
          name = self.preferences.get_value(author.replace('-', '_'))
          if name != None:
            element_fn = xml.SubElement(element, author)
            element_fn.text = str(name)

        self.acbf_document.load_metadata()
      self.doc_author.set_text(self.acbf_document.doc_authors)
      self.doc_id.set_text(self.acbf_document.id)

      sequences = ''
      for sequence in self.acbf_document.sequences:
        sequences = sequences + unescape(sequence[0]) + ' (' + sequence[1] + '), '
      sequences = sequences[:-2]
      self.series.set_text(sequences)
      self.genres.set_text(self.acbf_document.genres)
      self.characters.set_text(self.acbf_document.characters)
      languages = ''
      for language in self.acbf_document.languages:
        if language[1] == 'FALSE':
          languages = languages + language[0] + '(no text layer), '
        else:
          languages = languages + language[0] + ', '
      languages = languages[:-2]
      self.languages.set_text(languages)
      self.databaseref.set_text(self.acbf_document.databaseref)
      self.publish_date.set_text(self.acbf_document.publish_date_value)

      if len(self.acbf_document.languages) > 1 or self.acbf_document.languages[0][0] != '??':
        self.toolbar.contents_button.set_sensitive(True)
      else:
        self.toolbar.contents_button.set_sensitive(False)

      return

    # toolbar actions
    def open_file(self, *args):
      filename_before = self.filename
      self.filechooser = filechooser.FileChooserDialog(self)
      if filename_before != self.filename:
        self.acbf_document = acbfdocument.ACBFDocument(self, self.filename)
        self.annotation_list = self.acbf_document.annotation
        self.book_title_list = self.acbf_document.book_title
        for lang in self.acbf_document.languages:
          if lang[0] != '??':
            if not lang[0] in self.annotation_list:
              self.annotation_list[lang[0]] = ''
            if not lang[0] in self.book_title_list:
              self.book_title_list[lang[0]] = ''

        self.toolbar.update()
        self.update_forms(True)
        self.prior_language = self.toolbar.language.get_active_text()
      if self.acbf_document.valid:
        set_sensitivity(self.main_box, True, 0)
        self.toolbar.save_button.set_sensitive(True)
        self.toolbar.frames_button.set_sensitive(True)
        self.toolbar.font_button.set_sensitive(True)
        self.is_modified = False
      else:
        set_sensitivity(self.main_box, False, 0)
        self.toolbar.save_button.set_sensitive(False)
        self.toolbar.frames_button.set_sensitive(False)
        self.toolbar.font_button.set_sensitive(False)
      return True

    def show_about_window(self, *args):
      dialog = gtk.Dialog('About', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CLOSE, gtk.ResponseType.CLOSE))
      dialog.set_resizable(False)
      dialog.set_border_width(8)

      hbox = gtk.HBox(False, 10)

      # logo
      pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(os.path.join(constants.ICON_PATH, 'acbfe.png'), 64 * self.ui_scale_factor, 64 * self.ui_scale_factor)
      icon = gtk.Image()
      icon.set_from_pixbuf(pixbuf)
      hbox.pack_start(icon, False, False, 0)

      # labels
      label = gtk.Label()
      label.set_markup('<big><big><b><span foreground="#333333" style="italic">ACBF</span>' +
                       '<span foreground="#33ee00" style="oblique"> Editor</span></b></big></big>\n' +
                      _('Version: ') + constants.VERSION)
      hbox.pack_start(label, False, False, 0)
      dialog.vbox.pack_start(hbox, False, False, 0)

      hbox = gtk.HBox(False, 10)
      info = gtk.Label()
      info.set_markup(_('\n<span>ACBF Editor is editor for comic books files in ACBF format.') + '\n' +
                      _('ACBF Editor is licensed under the GNU General Public License.') + '\n\n' +
                       '<small>Copyright 2013-2024 Robert Kubik\n' +
                       'https://launchpad.net/acbf</small></span>\n')
      label.set_line_wrap(True)
      info.set_justify(gtk.Justification.CENTER)
      hbox.pack_start(info, False, False, 0)
      dialog.vbox.pack_start(hbox, False, False, 0)

      # show it
      dialog.show_all()
      dialog.run()
      dialog.destroy()
      return

    def set_titlepage(self, widget, event, hbox):
      for i in hbox.get_children():
        if i.get_name() == "GtkComboBox":
          page_image, bg_color = self.acbf_document.load_page_image(i.get_active() + 2)
          page_image.thumbnail((200 * self.ui_scale_factor, 200 * self.ui_scale_factor), Image.NEAREST)
          self.titlepage.set_from_pixbuf(self.pil_to_pixbuf(page_image, '#000'))
      return

    def change_language(self, *args):
      # save prior language data
      if self.prior_language in self.annotation_list:
        self.annotation_list[self.prior_language] = self.annotation.get_buffer().get_text(self.annotation.get_buffer().get_bounds()[0], self.annotation.get_buffer().get_bounds()[1], True)
      if self.prior_language in self.book_title_list:
        self.book_title_list[self.prior_language] = self.book_title.get_text()
      self.update_forms(True)
      self.prior_language = self.toolbar.language.get_active_text()
      return

    def add_contents_hbox(self, widget, entries_box, title, page):
      hbox = gtk.HBox(False, 0)

      # title entry
      entry = gtk.Entry()
      entry.set_text(title)
      entry.connect("focus-in-event", self.set_titlepage, hbox)
      hbox.pack_start(entry, True, True, 0)

      # pages dropdown
      dropdown = gtk.ComboBoxText()
      for idx, item in enumerate(self.page_image_names):
        dropdown.append_text(item)
      dropdown.set_active(page)

      hbox.pack_start(dropdown, False, True, 0)

      remove_button = gtk.ToolButton(gtk.STOCK_REMOVE)
      remove_button.connect("clicked", self.remove_hbox, hbox)
      hbox.pack_start(remove_button, False, False, 0)

      hbox.show_all()

      entries_box.pack_start(hbox, False, False, 0)
      return

    def update_contents_box(self, widget, lang):
        # save old
        if widget != None:
          for page in self.acbf_document.tree.findall("body/page"):
            for title in page.findall("title"):
              if (title.get("lang") == self.old_contents_dropdown) or (title.get("lang") == None and self.old_contents_dropdown == 'en'):
                page.remove(title)
            for entry in self.contents_box.get_children():
              image_name = None
              for i in entry.get_children():
                for j in i.get_children():
                  if j.get_name() == "GtkEntry":
                    chapter_name = j.get_text()
                  if j.get_name() == "GtkComboBox":
                    image_name = self.page_image_names[j.get_active()]
                if page.find("image").get("href") == image_name:
                  element = xml.SubElement(page, "title")
                  element.set('lang', self.old_contents_dropdown)
                  element.text = str(chapter_name)

        # activate new
        if widget != None:
          lang = widget.get_active()
        for i in self.contents_box.get_children():
          self.remove_hbox(None, i)

        # Table of Contents entries
        entries_box = gtk.VBox(False, 0)
        entries_box.set_border_width(5)

        self.page_image_names = []
        for page in self.acbf_document.tree.findall("body/page"):
          self.page_image_names.append(page.find("image").get("href"))

        for idx, page in enumerate(self.acbf_document.tree.findall("body/page")):
          default_title = ''
          title_found = False
          for title in page.findall("title"):
            default_title = title.text
            if (title.get("lang") == self.contents_languages[lang]) or (title.get("lang") == None and self.contents_languages[lang] == 'en'):
              self.add_contents_hbox(None, entries_box, title.text, idx)
              title_found = True
          if not title_found and default_title != '':
            self.add_contents_hbox(None, entries_box, ' ', idx)

        entries_box.show_all()
        self.contents_box.pack_start(entries_box, True, True, 0)

        # Add button hbox
        hbox = gtk.HBox(False, 0)
        hbox.set_border_width(5)

        button = gtk.ToolButton(gtk.STOCK_ADD)
        button.connect('clicked', self.add_contents_hbox, entries_box, '', 0)
        hbox.pack_start(button, False, False, 0)
        hbox.show_all()

        self.contents_box.pack_start(hbox, True, False, 0)

        if widget != None:
          self.old_contents_dropdown = widget.get_active_text()
          while gtk.events_pending():
            gtk.main_iteration()
          self.acbf_document.load_metadata()

    def edit_contents(self, *args):
        dialog = gtk.Dialog('Table of Contents', self, gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT,
                          (gtk.STOCK_CANCEL, gtk.ResponseType.CANCEL, gtk.STOCK_OK, gtk.ResponseType.OK))
        dialog.set_resizable(True)
        dialog.set_size_request(600 * self.ui_scale_factor, -1)
        dialog.set_border_width(8)

        # Text Layers switch
        self.contents_languages = []
        for item in self.acbf_document.tree.findall("meta-data/book-info/languages/text-layer"):
          if item.get("lang") not in self.contents_languages:
            self.contents_languages.append(item.get("lang"))
        
        hbox = gtk.HBox(False, 0)
        dropdown = gtk.ComboBoxText()
        dropdown.set_tooltip_text('lang')
        for idx, item in enumerate(self.contents_languages):
          dropdown.append_text(item)
        dropdown.set_active(0)
 
        dropdown.connect("changed", self.update_contents_box, 0)
        self.old_contents_dropdown = dropdown.get_active_text()

        hbox.pack_start(dropdown, False, False, 0)
        hbox.show_all()
        dialog.vbox.pack_start(hbox, False, False, 0)

        main_hbox = gtk.HBox(False, 0)

        left_box = gtk.VBox(False, 0)
        self.titlepage = gtk.Image()
        self.titlepage.set_from_pixbuf(self.pil_to_pixbuf(self.acbf_document.cover_thumb, '#000'))
        self.titlepage.set_alignment(0.5, 0)
        left_box.pack_start(self.titlepage, False, False, 10)
        left_box.set_border_width(5)

        main_hbox.pack_start(left_box, False, False, 5)

        # Table of Contents entries
        self.contents_box = gtk.VBox(False, 0)
        self.contents_box.set_border_width(5)

        self.update_contents_box(None, 0)

        main_hbox.pack_start(self.contents_box, True, True, 0)

        dialog.vbox.pack_start(main_hbox, True, True, 0)

        # show it
        if len(self.contents_box.get_children()[0].get_children()) > 0:
          self.contents_box.get_children()[0].get_children()[0].get_children()[0].grab_focus()
        dialog.show_all()
        response = dialog.run()

        if response == gtk.ResponseType.OK:
          self.is_modified = True

          for page in self.acbf_document.tree.findall("body/page"):
            for title in page.findall("title"):
              if (title.get("lang") == self.contents_languages[dropdown.get_active()]) or (title.get("lang") == None and self.contents_languages[dropdown.get_active()] == 'en'):
                page.remove(title)
            for entry in self.contents_box.get_children():
              image_name = None
              for i in entry.get_children():
                for j in i.get_children():
                  if j.get_name() == "GtkEntry":
                    chapter_name = j.get_text()
                  if j.get_name() == "GtkComboBox":
                    image_name = self.page_image_names[j.get_active()]
                if page.find("image").get("href") == image_name:
                  element = xml.SubElement(page, "title")
                  element.set('lang', self.contents_languages[dropdown.get_active()])
                  element.text = str(chapter_name)

          self.acbf_document.load_metadata()
          self.update_forms(False)

        dialog.destroy()
        return


    def edit_frames(self, *args):
      self.frames_dialog = frames_editor.FramesEditorDialog(self)
      self.frames_dialog.destroy()
      return

    def save_file(self, *args):
      filechooser = gtk.FileChooserDialog(title='Save File ...', action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                buttons=(gtk.STOCK_CANCEL,gtk.ResponseType.CANCEL,gtk.STOCK_SAVE,gtk.ResponseType.OK))

      filechooser.set_current_folder(os.path.dirname(self.original_filename))
      filechooser.set_current_name(os.path.splitext(os.path.basename(self.original_filename))[0] + '.cbz')
      filechooser.set_do_overwrite_confirmation(True)

      filter = gtk.FileFilter()
      filter.set_name("Comicbook files")
      filter.add_pattern("*.acbf")
      filter.add_pattern("*.acv")
      filter.add_pattern("*.cbz")
      filechooser.add_filter(filter)

      filter = gtk.FileFilter()
      filter.set_name("All files")
      filter.add_pattern("*")
      filechooser.add_filter(filter)

      response = filechooser.run()
      if response != gtk.ResponseType.OK:
        filechooser.destroy()
        return

      self.is_modified = False
      return_filename = str(filechooser.get_filename())
      filechooser.destroy()

      to_remove = self.acbf_document.tree.findall("meta-data/book-info/book-title")
      for i in to_remove:
        self.acbf_document.tree.find("meta-data/book-info").remove(i)

      if self.toolbar.language.get_active_text() in self.book_title_list:
        self.book_title_list[self.toolbar.language.get_active_text()] = self.book_title.get_text()

      for title in self.book_title_list.items():
        if title[0] != '??' and title[1] != None and title[1] != '':
          new_title = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "book-title", lang=title[0])
          new_title.text = unescape(str(title[1]))
        elif title[0] == '??':
          new_title = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "book-title")
          new_title.text = unescape(str(title[1]))

      self.modify_element("meta-data/book-info/keywords", self.keywords.get_text())

      to_remove = self.acbf_document.tree.findall("meta-data/book-info/annotation")
      for i in to_remove:
        self.acbf_document.tree.find("meta-data/book-info").remove(i)
      
      if self.toolbar.language.get_active_text() in self.annotation_list:
        self.annotation_list[self.toolbar.language.get_active_text()] = self.annotation.get_buffer().get_text(self.annotation.get_buffer().get_bounds()[0], self.annotation.get_buffer().get_bounds()[1], True)
      elif self.toolbar.language.get_active_text() == '??':
        self.annotation_list['??'] = self.annotation.get_buffer().get_text(self.annotation.get_buffer().get_bounds()[0], self.annotation.get_buffer().get_bounds()[1], True)

      for anno in self.annotation_list.items():
        if anno[0] == '??' and anno[1] != None and anno[1] != '':
          new_anno = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "annotation")
          for line in anno[1].split('\n'):
            new_line = xml.SubElement(new_anno, "p")
            new_line.text = str(line)
        elif anno[1] != None and anno[1] != '':
          new_anno = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "annotation", lang=anno[0])
          for line in anno[1].split('\n'):
            new_line = xml.SubElement(new_anno, "p")
            new_line.text = str(line)

      self.modify_element("meta-data/publish-info/publisher", self.publisher.get_text())
      self.modify_element("meta-data/publish-info/city", self.city.get_text())
      self.modify_element("meta-data/publish-info/isbn", self.isbn.get_text())
      self.modify_element("meta-data/publish-info/license", self.license.get_text())

      self.write_file(return_filename)
      return

    def write_file(self, output_file):
      if not self.is_cmd_line:
        progress_dialog = gtk.Dialog('Saving file ...', parent=self, flags=gtk.DialogFlags.MODAL | gtk.DialogFlags.DESTROY_WITH_PARENT, buttons=None)
        progress_dialog.set_resizable(False)
        progress_dialog.set_border_width(8)
        progress_dialog.set_geometry_hints(min_height=100 * self.ui_scale_factor, min_width=400 * self.ui_scale_factor)
        progress_bar = gtk.ProgressBar()
        progress_bar.set_size_request(-1,13 * self.ui_scale_factor)
        progress_dialog.vbox.pack_start(progress_bar, False, False, 5)
        progress_title = gtk.Label()
        progress_title.set_markup('Saving file ...')
        progress_dialog.vbox.pack_start(progress_title, False, True, 0)
        progress_dialog.show_all()
        while gtk.events_pending():
          gtk.main_iteration()

      print("Saving file ...", output_file)

      try:
        # create tree with namespace
        tree = xml.Element("ACBF", xmlns="http://www.acbf.info/xml/acbf/1.1")
        for element in self.acbf_document.tree.getroot():
          tree.append(deepcopy(element))

        f = open(os.path.join(self.tempdir, os.path.basename(self.filename)), 'w')
        f.write(xml.tostring(tree, pretty_print=True, encoding='utf-8', xml_declaration=True))
        f.close()

        tree = None

        # create CBZ file
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zip:
          total_files = 0
          processed_files = 0
          for root, dirs, files in os.walk(self.tempdir):
            for f in files:
              total_files = total_files + 1
          for root, dirs, files in os.walk(self.tempdir):
            for f in files:
              processed_files = processed_files + 1
              fraction = float(processed_files)/total_files
              if not self.is_cmd_line:
                progress_bar.set_fraction(fraction)
                while gtk.events_pending():
                  gtk.main_iteration()
              filename = os.path.join(root, f)
              if os.path.isfile(filename): # regular files only
                arcname = os.path.join(os.path.relpath(root, self.tempdir), f)
                zip.write(filename, arcname)

        #print(self.original_filename, self.filename, return_filename)
        #print(xml.tostring(self.acbf_document.tree, pretty_print=True))
        output_file_size = round(float(os.path.getsize(output_file))/1024/1024, 2)
        if not self.is_cmd_line:
            progress_dialog.destroy()
        else:
          print("File size: " + str(self.original_file_size) + " MB" + " -> " + str(output_file_size) + " MB" + " -> " + str(round((output_file_size/float(self.original_file_size))*100,1)) + " %")

      except Exception as inst:
        if not self.is_cmd_line:
          message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.WARNING, buttons=gtk.BUTTONS_OK, message_format=None)
          message.set_markup("Failed to save comic book.\n\n" + 'Exception: %s' % inst)
          response = message.run()
          message.destroy()
          progress_dialog.destroy()
        else:
          print('Failed to save comic book. Exception: %s' % inst)

      print("Done.")
      return

    def add_element(self, element, sub_element, text):
      if text != None and text != '':
        new_element = xml.SubElement(element, sub_element)
        new_element.text = str(text)

    def modify_element(self, path, value):
      element_name = path.split('/')[-1]
      element_path = path[:len(path) - len(path.split('/')[-1]) - 1]
      element = self.acbf_document.tree.find(path)

      if element == None:
        element = xml.SubElement(self.acbf_document.tree.find(element_path), element_name)
      element.text = str(value)

      return

    def exit_program(self, *args):
      self.clean_temp()
      sys.exit(1)
      return False

    def terminate_program(self, *args):
      if self.is_modified:
        message = gtk.MessageDialog(parent=self, flags=0, type=gtk.MessageType.QUESTION, buttons=gtk.ButtonsType.YES_NO, message_format=None)
        message.set_markup("Data has been modified. Are you sure you want to exit without saving it?")
        response = message.run()
        message.destroy()

        if response != gtk.ResponseType.YES:
         return True

      self.clean_temp()
      gtk.main_quit()
      return False

    def clean_temp(self, *args):
      # clear temp directory
      for root, dirs, files in os.walk(self.tempdir):
        for f in files:
          os.unlink(os.path.join(root, f))
        for d in dirs:
          shutil.rmtree(os.path.join(root, d))
      shutil.rmtree(self.tempdir)
      return False

    def pil_to_pixbuf(self, PILImage, BGColor):
        bcolor = Gdk.RGBA()
        Gdk.RGBA.parse(bcolor, BGColor)
        bcolor = (int(bcolor.red*255), int(bcolor.green*255), int(bcolor.blue*255))
        try:
          PILImage = PILImage.convert("RGBA")
          bg = Image.new("RGB", PILImage.size, bcolor)
          bg.paste(PILImage,PILImage)

          with io.BytesIO() as dummy_file:
            bg.save(dummy_file, "ppm")
            contents = dummy_file.getvalue()

          loader = GdkPixbuf.PixbufLoader()
          loader.write(contents)
          pixbuf = loader.get_pixbuf()
          loader.close()
          return pixbuf
        except:
          bg = Image.new("RGB", (150 * self.ui_scale_factor, 200 * self.ui_scale_factor), bcolor)
          with io.BytesIO() as dummy_file:
            bg.save(dummy_file, "ppm")
            contents = dummy_file.getvalue()

          loader = GdkPixbuf.PixbufLoader()
          loader.write(contents)
          pixbuf = loader.get_pixbuf()
          loader.close()
          return pixbuf

def set_sensitivity(widget, sensitivity, level):
  try:
    widget.set_sensitive(sensitivity)
  except:
    None

  if (hasattr(widget, 'get_child') and callable(getattr(widget, 'get_child'))):
    child = widget.get_child()
    if child is not None:
      return set_sensitivity(child, sensitivity, level + 1)
  elif (hasattr(widget, 'get_children') and callable(getattr(widget, 'get_children'))):
    children = widget.get_children()
    found = None
    for child in children:
      if child is not None:
        found = set_sensitivity(child, sensitivity, level + 1)
        if found: return found



