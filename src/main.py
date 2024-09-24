"""main.py - Main window.

Copyright (C) 2011-2019 Robert Kubik
https://launchpad.net/~just-me
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
import logging
import os
import random

import pangocffi
from pangocffi import EllipsizeMode
from gi.repository import Gtk, GObject, Gdk, GdkPixbuf, Adw, Gio, GLib
from PIL import Image
import io
import lxml.etree as xml
from copy import deepcopy
import zipfile
import shutil
import time
from xml.sax.saxutils import escape, unescape
import re
from typing import Any
import isocodes

import constants
import acbfdocument
import filechooser
import fileprepare
import preferences
import prefsdialog
import frames_editor
import fontselectiondialog
import text_layer as tl
import edit_authors
import edit_series
import edit_contents
import edit_styles
import edit_genres
import edit_characters
import edit_keywords
import edit_languages
import edit_dbref
import edit_sources
import edit_history
import edit_content_rating
from edit_languages import Language

logger = logging.getLogger("acbf_editor")
logger.setLevel(logging.DEBUG)


class MainWindow(Gtk.ApplicationWindow):
    """The ACBF main window"""
    def __init__(self, application=None, open_path=None, output_file=None, cmd_options=None):
        super().__init__(application=application)
        self.app = application
        # Preferences
        self.preferences = preferences.Preferences()
        self._window = self
        self.font_idx = 0

        # Start variables
        self.is_modified: bool = False

        self.original_filename: str = ""

        # check if custom temp dir is defined
        # TODO use tempfile
        self.tempdir_root = str(os.path.join(self.preferences.get_value("tmpfs_dir"), 'acbfe'))
        if self.preferences.get_value("tmpfs") != 'False':
            print("Temporary directory override set to: " + self.tempdir_root)
        else:
            self.tempdir_root = constants.DATA_DIR
        self.tempdir = str(
            os.path.join(self.tempdir_root, ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for i in range(10))))

        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)

        self.filename = open_path
        if self.filename is None:
            pass
            #self.filename = "/home/whale/Work/ACBF/trunk/xSample Comic Book/Doctorow, Cory - Craphound.acbf"
            #self.original_filename = self.filename
        else:
            if output_file is None:
                prepared_file = fileprepare.FilePrepare(self, open_path, self.tempdir, True)
            else:
                prepared_file = fileprepare.FilePrepare(self, open_path, self.tempdir, False)
            self.filename = prepared_file.filename
            self.original_filename = open_path

        try:
            self.original_file_size = round(float(os.path.getsize(open_path)) / 1024 / 1024, 2)
        except:
            self.original_file_size = 1

        self.acbf_document = acbfdocument.ACBFDocument(self, self.filename)

        # Command line processing
        self.is_cmd_line = False
        if output_file is not None:
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
                        print('Error: Unrecognized image format:',
                              value + '. Use one of following: ' + str(formats_supported).replace('(', '').replace(')',
                                                                                                                   '').replace(
                                  '\'', ''))
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
                    if re.match('[0-9]*x[0-9]*[<>]', value) is not None:
                        resize_geometry = value
                    else:
                        print('')
                        print('Error: Image geometry must be in format [width]x[height][flag].')
                        print('[width] and [height] defines target image size as integer.')
                        print('[flag] defines wheather to shrink (>) or enlarge (<) target image.')
                        self.exit_program()
                if opt in ('-l', '--filter'):
                    if value.upper() not in ('NEAREST', 'BILINEAR', 'BICUBIC', 'ANTIALIAS'):
                        print('Error: Unrecognized resize filter:',
                              value + '. Use one of following: NEAREST, BILINEAR, BICUBIC, ANTIALIAS.')
                        self.exit_program()
                    else:
                        resize_filter = value
                if opt in ('-t', '--text_layer'):
                    lang_found = False
                    i = 0
                    while i < 999:
                        lang = self.acbf_document.languages.get_item(i)
                        if lang is None:
                            break
                        if lang.get("lang") == value and lang.get("show"):
                    #for idx, lang in enumerate(self.acbf_document.languages):
                        #if lang[0] == value and lang[1] == 'TRUE':
                            lang_found = True
                            text_layer = i
                    if not lang_found:
                        logger.error('Error: Language layer', value, 'is not defined in comic book.')
                        self.exit_program()
                    else:
                        for item in self.acbf_document.tree.findall("meta-data/book-info/languages/text-layer"):
                            if item.get("show") == 'False':
                                item.attrib['lang'] = value

            if convert_format is not None or resize_geometry is not None or text_layer is not None:
                self.convert_images(convert_format, convert_quality, resize_geometry, resize_filter, text_layer)
            self.write_file(output_file)
            self.exit_program()

        # Create a store for dropdown use for all languages
        self.all_langs: Gio.ListStore = Gio.ListStore.new(Language)
        for lang in isocodes.languages.items:
            if lang.get("alpha_2"):
                self.all_langs.append(Language(lang_iso=lang["alpha_2"], lang=lang["name"]))

        self.all_lang_store: Gio.ListStore = Gio.ListStore.new(Language)

        # Create a deduplicated lang store
        self.lang_store: Gio.ListStore = self.dedupe_langs(self.all_lang_store)

        # Window properties
        self.set_title("ACBF Editor")
        self.set_size_request(900, 860)
        self.isFullscreen = False

        action: Gio.SimpleAction = Gio.SimpleAction.new("open", None)
        action.connect("activate", self.open_file)
        self.add_action(action)

        action: Gio.SimpleAction = Gio.SimpleAction.new("revert", None)
        action.connect("activate", self.revert_file)
        self.add_action(action)

        self.save_action = Gio.SimpleAction.new("save", None)
        self.save_action.connect("activate", self.save_file)
        self.add_action(self.save_action)

        self.save_action = Gio.SimpleAction.new("saveas", None)
        self.save_action.connect("activate", self.save_as_file)
        self.add_action(self.save_action)

        self.toc_action = Gio.SimpleAction.new("toc", None)
        self.toc_action.connect("activate", self.open_edit_contents)
        self.add_action(self.toc_action)

        self.frames_action = Gio.SimpleAction.new("frames", None)
        self.frames_action.connect("activate", self.edit_frames)
        self.add_action(self.frames_action)

        self.styles_action = Gio.SimpleAction.new("styles", None)
        self.styles_action.connect("activate", self.edit_styles)
        self.add_action(self.styles_action)

        self.lang_action = Gio.SimpleAction.new("lang", None)
        self.lang_action.connect("activate", self.edit_languages)
        self.add_action(self.lang_action)

        action = Gio.SimpleAction.new("prefs", None)
        action.connect("activate", self.open_preferences)
        self.add_action(action)

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.show_about_window)
        self.add_action(action)

        menu = Gio.Menu.new()
        menu.append("Open", "win.open")
        menu.append("Save", "win.save")

        menu.append("Tables of Contents", "win.toc")
        menu.append("Frames/Texts Area Definitions", "win.frames")
        menu.append("Font/Style Definitions", "win.styles")
        menu.append("Preferences", "win.prefs")
        menu.append("Languages", "win.lang")
        menu.append("About", "win.about")

        # Create a popover
        self.popover = Gtk.PopoverMenu()
        self.popover.set_has_arrow(False)
        self.popover.set_offset(86, -1)
        self.popover.set_menu_model(menu)

        # Create a menu button
        self.hamburger = Gtk.MenuButton()
        self.hamburger.set_popover(self.popover)
        self.hamburger.set_icon_name("open-menu-symbolic")

        header = Gtk.HeaderBar()
        self.set_titlebar(header)
        header.pack_start(self.hamburger)
        open_button: Gtk.Button = Gtk.Button.new_from_icon_name("document-open-symbolic")
        open_button.set_tooltip_text("Open file")
        header.pack_start(open_button)
        open_button.connect('clicked', self.open_file)
        self.save_button: Gtk.Button = Gtk.Button.new_from_icon_name("document-save-symbolic")
        self.save_button.set_tooltip_text("Save file")
        header.pack_start(self.save_button)
        self.save_button.connect('clicked', self.save_file)

        self.lang_button: Gtk.DropDown = self.create_lang_dropdown(self.lang_store, self.change_language)
        #self.update_languages()
        #self.lang_button: Gtk.DropDown = self.create_lang_dropdown(self.acbf_document.languages, self.change_language)

        header.pack_start(self.lang_button)

        self.panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.panes.set_position(300)

        # TODO Change coverpage
        self.coverpage = Gtk.Picture()
        self.coverpage.set_size_request(200, 300)
        self.coverpage.set_hexpand(True)
        self.panes.set_start_child(self.coverpage)

        # book-info
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tab: Gtk.Grid = Gtk.Grid()
        tab.set_margin_top(5)
        tab.set_margin_start(5)
        tab.set_margin_end(5)
        tab.set_margin_bottom(5)
        tab.set_row_spacing(3)
        tab.set_column_spacing(3)
        scrolled.set_child(tab)

        label: Gtk.Label = Gtk.Label.new("Title:")
        label.set_xalign(1)
        tab.attach(label, 0, 0, 1, 1)
        self.book_title = Gtk.Entry()
        self.book_title.set_hexpand(True)
        #self.book_title.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.book_title.connect("changed", self.entry_changed)
        tab.attach(self.book_title, 1, 0, 1, 1)

        # Authors
        label: Gtk.Label = Gtk.Label.new("Author(s):")
        label.set_xalign(1)
        tab.attach(label, 0, 1, 1, 1)
        self.authors: Gtk.Entry = Gtk.Entry()
        #self.authors.set_ellipsize(3)
        self.authors.set_editable(False)
        self.authors.set_can_focus(False)
        self.authors.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.authors.set_icon_sensitive(Gtk.EntryIconPosition.SECONDARY, True)
        self.authors.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.authors.connect("icon-press", self.edit_authors)
        tab.attach(self.authors, 1, 1, 1, 1)

        # Series
        label = Gtk.Label.new("Series:")
        label.set_xalign(1)
        tab.attach(label, 0, 2, 1, 1)
        self.series: Gtk.Entry = Gtk.Entry()
        self.series.set_can_focus(False)
        self.series.set_editable(False)
        self.series.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.series.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.series.connect("icon-press", self.edit_series)
        tab.attach(self.series, 1, 2, 1, 1)

        # Genres
        label = Gtk.Label.new("Genres:")
        label.set_xalign(1)
        tab.attach(label, 0, 3, 1, 1)
        self.genres: Gtk.Entry = Gtk.Entry()
        self.genres.set_can_focus(False)
        self.genres.set_editable(False)
        self.genres.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.genres.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.genres.connect('icon-press', self.edit_genres)
        tab.attach(self.genres, 1, 3, 1, 1)

        # Characters
        label = Gtk.Label.new("Characters:")
        label.set_xalign(1)
        tab.attach(label, 0, 4, 1, 1)
        self.characters: Gtk.Entry = Gtk.Entry()
        self.characters.set_editable(False)
        self.characters.set_can_focus(False)
        self.characters.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.characters.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.characters.connect('icon-press', self.edit_characters)
        tab.attach(self.characters, 1, 4, 1, 1)

        # Annotation
        label = Gtk.Label.new("Annotation:")
        label.set_xalign(1)
        tab.attach(label, 0, 5, 1, 1)
        self.annotation: Gtk.Entry = Gtk.Entry()
        self.annotation.set_editable(False)
        #self.annotation.set_can_focus(False)
        #self.annotation.set_
        self.annotation.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.annotation.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.annotation.connect('icon-press', self.edit_annotation)
        tab.attach(self.annotation, 1, 5, 1, 1)

        # Keywords
        label = Gtk.Label.new("Keywords:")
        label.set_xalign(1)
        tab.attach(label, 0, 6, 1, 1)
        self.keywords: Gtk.Entry = Gtk.Entry()
        self.keywords.set_editable(False)
        self.keywords.set_can_focus(False)
        self.keywords.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "tag-symbolic")
        self.keywords.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.keywords.connect('icon-press', self.edit_keywords)
        tab.attach(self.keywords, 1, 6, 1, 1)

        # Languages
        label = Gtk.Label.new("Languages:")
        label.set_xalign(1)
        tab.attach(label, 0, 7, 1, 1)
        self.languages: Gtk.Entry = Gtk.Entry()
        self.languages.set_editable(False)
        self.languages.set_can_focus(False)
        self.languages.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "language-chooser-symbolic")
        self.languages.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.languages.connect('icon-press', self.edit_languages)
        tab.attach(self.languages, 1, 7, 1, 1)

        # databaseref
        label = Gtk.Label.new("Database Reference:")
        label.set_xalign(1)
        tab.attach(label, 0, 8, 1, 1)
        self.databaseref: Gtk.Entry = Gtk.Entry()
        self.databaseref.set_editable(False)
        self.databaseref.set_can_focus(False)
        self.databaseref.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.databaseref.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.databaseref.connect('icon-press', self.edit_dbref)
        tab.attach(self.databaseref, 1, 8, 1, 1)

        # content rating
        label = Gtk.Label.new("Content Rating:")
        label.set_xalign(1)
        tab.attach(label, 0, 9, 1, 1)
        self.rating: Gtk.Entry = Gtk.Entry()
        self.rating.set_editable(False)
        self.rating.set_can_focus(False)
        self.rating.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.rating.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.rating.connect('icon-press', self.edit_ratings)
        tab.attach(self.rating, 1, 9, 1, 1)

        # reading direction # 1.2
        label = Gtk.Label.new("Reading Direction:")
        label.set_xalign(1)
        tab.attach(label, 0, 10, 1, 1)
        self.reading: Gtk.DropDown = Gtk.DropDown.new_from_strings(["LTR", "RTL"])
        #self.reading.connect('notify::selection', self.edit_reading_direction)
        tab.attach(self.reading, 1, 10, 1, 1)

        # publish-info
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(5)
        sep.set_margin_bottom(5)
        tab.attach(sep, 0, 11, 2, 1)

        # Publisher
        label = Gtk.Label.new("Publisher:")
        label.set_xalign(1)
        tab.attach(label, 0, 12, 1, 1)
        self.publisher: Gtk.Entry = Gtk.Entry()
        self.publisher.connect("changed", self.entry_changed)
        #self.publisher.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        tab.attach(self.publisher, 1, 12, 1, 1)

        # Publish Date
        label = Gtk.Label.new("Publish Date:")
        label.set_xalign(1)
        tab.attach(label, 0, 13, 1, 1)
        self.publish_date: Gtk.Entry = Gtk.Entry()
        self.publish_date.set_editable(False)
        self.publish_date.set_can_focus(False)
        self.publish_date.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-calendar-symbolic")
        self.publish_date.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.publish_date.connect('icon-press', self.edit_publish_date)
        tab.attach(self.publish_date, 1, 13, 1, 1)

        # City
        label = Gtk.Label.new("City:")
        label.set_xalign(1)
        tab.attach(label, 0, 14, 1, 1)
        self.city: Gtk.Entry = Gtk.Entry()
        self.city.connect("changed", self.entry_changed)
        #self.city.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        tab.attach(self.city, 1, 14, 1, 1)

        # ISBN
        label = Gtk.Label.new("ISBN:")
        label.set_xalign(1)
        tab.attach(label, 0, 15, 1, 1)
        self.isbn: Gtk.Entry = Gtk.Entry()
        self.isbn.connect("changed", self.entry_changed)
        #self.isbn.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        tab.attach(self.isbn, 1, 15, 1, 1)

        # License
        label = Gtk.Label.new("License:")
        label.set_xalign(1)
        tab.attach(label, 0, 16, 1, 1)
        self.license: Gtk.Entry = Gtk.Entry()
        self.license.connect("changed", self.entry_changed)
        #self.license.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        tab.attach(self.license, 1, 16, 1, 1)

        # document-info
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(5)
        sep.set_margin_bottom(5)
        tab.attach(sep, 0, 17, 2, 1)

        # Doc ID
        label = Gtk.Label.new("Document ID:")
        label.set_xalign(1)
        tab.attach(label, 0, 18, 1, 1)
        self.doc_id: Gtk.Entry = Gtk.Entry()
        self.doc_id.set_sensitive(False)
        self.doc_id.set_tooltip_text('Unique document ID (UUID)')
        tab.attach(self.doc_id, 1, 18, 1, 1)

        # Doc Author
        label = Gtk.Label.new("Author(s):")
        label.set_xalign(1)
        tab.attach(label, 0, 19, 1, 1)
        self.doc_author: Gtk.Entry = Gtk.Entry()
        self.doc_author.set_editable(False)
        self.doc_author.set_can_focus(False)
        self.doc_author.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.doc_author.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.doc_author.connect('icon-press', self.edit_authors, True)
        tab.attach(self.doc_author, 1, 19, 1, 1)

        # creation date
        label = Gtk.Label.new("Creation Date:")
        label.set_xalign(1)
        tab.attach(label, 0, 20, 1, 1)
        self.creation_date: Gtk.Entry = Gtk.Entry()
        self.creation_date.set_editable(False)
        self.creation_date.set_can_focus(False)
        self.creation_date.set_tooltip_text("The creation date of this ACBF document")
        self.creation_date.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-calendar-symbolic")
        self.creation_date.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.creation_date.connect('icon-press', self.edit_creation_date)
        tab.attach(self.creation_date, 1, 20, 1, 1)

        # source
        label = Gtk.Label.new("Source(s):")
        label.set_xalign(1)
        tab.attach(label, 0, 21, 1, 1)
        self.source: Gtk.Entry = Gtk.Entry()
        self.source.set_editable(False)
        self.source.set_can_focus(False)
        self.source.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.source.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.source.connect('icon-press', self.edit_source)
        tab.attach(self.source, 1, 21, 1, 1)

        # version
        label = Gtk.Label.new("Version:")
        label.set_xalign(1)
        tab.attach(label, 0, 22, 1, 1)
        self.version: Gtk.Entry = Gtk.Entry()
        tab.attach(self.version, 1, 22, 1, 1)

        # history
        label = Gtk.Label.new("History:")
        label.set_xalign(1)
        tab.attach(label, 0, 23, 1, 1)
        self.history: Gtk.Entry = Gtk.Entry()
        self.history.set_editable(False)
        self.history.set_can_focus(False)
        self.history.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-symbolic")
        self.history.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Click to edit")
        self.history.connect('icon-press', self.edit_history)
        tab.attach(self.history, 1, 23, 1, 1)

        self.update_languages()

        self.panes.set_end_child(scrolled)
        self.set_child(self.panes)

        self.connect("close-request", self.terminate_program)

        self.set_header_title()

        if self.acbf_document.valid:
            self.update_forms(True)
        else:
            self.panes.set_sensitive(False)
            self.save_action.set_enabled(False)
            self.save_button.set_sensitive(False)
            self.toc_action.set_enabled(False)
            self.lang_action.set_enabled(False)
            self.frames_action.set_enabled(False)
            self.styles_action.set_enabled(False)

    def dedupe_langs(self, langs: Gio.ListStore) -> Gio.ListStore:
        new_langs: Gio.ListStore = Gio.ListStore.new(item_type=Language)
        seen_lang_isos: set[str] = set()
        i = 0

        while i < 9999:
            item = langs.get_item(i)
            if item is None:
                break
            lang_iso = item.lang_iso

            if lang_iso not in seen_lang_isos:
                seen_lang_isos.add(item.lang_iso)
                lang_info = isocodes.languages.get(alpha_2=item.lang_iso)
                new_langs.append(Language(lang_iso=item.lang_iso, lang=lang_info.get("name"), show=True))

            i += 1

        return new_langs

    def setup_lang_item(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        label = Gtk.Label()
        list_item.set_child(label)

    def bind_lang_item(self, factory: Gtk.ListItemFactory, list_item: Gtk.ListItem):
        item: Language = list_item.get_item()
        entry: Gtk.Label = list_item.get_child()

        entry.set_text(item.lang)

    def create_lang_dropdown(self, model: Gio.ListStore, con_sel) -> Gtk.DropDown:
        expression = Gtk.PropertyExpression.new(Language, None, "lang")

        dropdown: Gtk.DropDown = Gtk.DropDown.new(model, expression)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_lang_item)
        factory.connect("bind", self.bind_lang_item)

        dropdown.set_list_factory(factory)
        dropdown.connect("notify::selected", con_sel)

        return dropdown

    def set_header_title(self) -> None:
        book_title = "*" if self.is_modified else ""
        if self.acbf_document.valid:
            try:
                book_title = unescape(self.acbf_document.book_title[self.lang_button.get_selected_item().lang_iso]) + book_title
            except:
                book_title = unescape(self.acbf_document.book_title[list(self.acbf_document.book_title.items())[0][0]]) + book_title

            self.set_title(f"{book_title} - ACBF Editor")
        else:
            self.set_title(f"ACBF Editor")

    def convert_images(self, im_format, im_quality, im_geometry, im_filter, im_text_layer):
        # print 'Format:', im_format, 'Quality:', im_quality, 'Resize:', im_geometry, 'Filter:', im_filter, 'Text-layer', im_text_layer
        resize_filters = {'NEAREST': 0, 'BILINEAR': 2, 'BICUBIC': 3, 'ANTIALIAS': 1}
        if im_filter == None:
            im_filter = 'ANTIALIAS'

        for idx, page in enumerate(self.acbf_document.pages, start=1):
            in_path = os.path.join(self.tempdir, page.find("image").get("href").replace("\\", "/"))
            in_path_short = in_path[len(self.tempdir) + 1:]
            if im_format == None:
                im_format = os.path.splitext(in_path)[1][1:]
            out_path = os.path.splitext(in_path)[0] + '.' + im_format.lower()
            out_path_short = out_path[len(self.tempdir) + 1:]
            page.find("image").attrib['href'] = out_path_short
            perc_done = str(int(round(float(idx) / float(self.acbf_document.pages_total) * 100, 0))).rjust(4) + '%'
            print(perc_done, in_path_short, '->', out_path_short)

            # convert image
            if in_path != out_path or im_geometry != None or im_text_layer != None:
                if im_text_layer != None and idx > 0:
                    xx = tl.TextLayer(in_path, idx + 1, self.acbf_document, im_text_layer,
                                      self.acbf_document.font_styles['normal'],
                                      self.acbf_document.font_styles['strong'],
                                      self.acbf_document.font_styles['emphasis'],
                                      self.acbf_document.font_styles['code'],
                                      self.acbf_document.font_styles['commentary'],
                                      self.acbf_document.font_styles['sign'], self.acbf_document.font_styles['formal'],
                                      self.acbf_document.font_styles['heading'],
                                      self.acbf_document.font_styles['letter'],
                                      self.acbf_document.font_styles['audio'],
                                      self.acbf_document.font_styles['thought'])
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
                                new_point = (
                                    round(int(coord.split(',')[0]) * ratio, 0),
                                    round(int(coord.split(',')[1]) * ratio, 0))
                                new_coord = new_coord + str(int(new_point[0])) + ',' + str(int(new_point[1])) + ' '

                            frame.attrib['points'] = new_coord.strip()
                        # scale text-layers
                        for text_layer in page.findall("text-layer"):
                            for text_area in text_layer.findall("text-area"):
                                new_coord = ''
                                for coord in text_area.get("points").split(' '):
                                    new_point = (round(int(coord.split(',')[0]) * ratio, 0),
                                                 round(int(coord.split(',')[1]) * ratio, 0))
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
        prefs_dialog = prefsdialog.PrefsDialog(self)
        prefs_dialog.present()

    def open_edit_contents(self, action: Gio.SimpleAction, _pspec):
        edit_contents_dialog = edit_contents.EditContentWindow(self)
        edit_contents_dialog.present()

    def edit_styles(self, *args):
        edit_styles_dialog = edit_styles.EditStylesWindow(self)
        edit_styles_dialog.present()

        '''dialog = Gtk.Dialog('Edit Styles/Fonts Definitions', self,
                            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK))
        dialog.set_resizable(True)
        #        dialog.set_border_width(8)

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
                        constants.FONTS_LIST.append((f.replace('.ttf', '').replace('.TTF', '').replace('.otf',
                                                                                                       '').replace(
                            '.OTF', ''), os.path.join(root, f)))

        # Font Styles
        entries_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        #        entries_box.set_border_width(5)

        ## Speech
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Speech (default): </tt>')
        hbox.append(label)

        self.speech_font = Gtk.Button.new_with_label()
        self.speech_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["normal"]))[0]:
                self.speech_font.font_idx = idx
                break
        self.speech_font.set_label(constants.FONTS_LIST[self.speech_font.font_idx][0])

        hbox.append(self.speech_font)
        self.speech_font.connect("clicked", self.set_speech_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["speech"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'speech')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Emphasis
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Emphasis:         </tt>')
        hbox.append(label)

        self.emphasis_font = Gtk.Button.new_with_label()
        self.emphasis_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["emphasis"]))[0]:
                self.emphasis_font.font_idx = idx
                break
        self.emphasis_font.set_label(constants.FONTS_LIST[self.emphasis_font.font_idx][0])

        hbox.append(self.emphasis_font)
        self.emphasis_font.connect("clicked", self.set_emphasis_font)

        color_button = Gtk.ColorButton(Gdk.color_parse("#999999"))
        color_button.set_sensitive(False)
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Strong
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Strong:           </tt>')
        hbox.append(label)

        self.strong_font = Gtk.Button.new_with_label()
        self.strong_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["strong"]))[0]:
                self.strong_font.font_idx = idx
                break
        self.strong_font.set_label(constants.FONTS_LIST[self.strong_font.font_idx][0])

        hbox.append(self.strong_font)
        self.strong_font.connect("clicked", self.set_strong_font)

        color_button = Gtk.ColorButton(Gdk.color_parse("#999999"))
        color_button.set_sensitive(False)
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Commentary
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Commentary:       </tt>')
        hbox.append(label)

        self.commentary_font = Gtk.Button.new_with_label()
        self.commentary_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["commentary"]))[0]:
                self.commentary_font.font_idx = idx
                break
        self.commentary_font.set_label(constants.FONTS_LIST[self.commentary_font.font_idx][0])

        hbox.append(self.commentary_font)
        self.commentary_font.connect("clicked", self.set_commentary_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["commentary"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'commentary')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Code
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Code:             </tt>')
        hbox.append(label)

        self.code_font = Gtk.Button.new_with_label()
        self.code_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["code"]))[0]:
                self.code_font.font_idx = idx
                break
        self.code_font.set_label(constants.FONTS_LIST[self.code_font.font_idx][0])

        hbox.append(self.code_font)
        self.code_font.connect("clicked", self.set_code_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["code"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'code')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Formal
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Formal:           </tt>')
        hbox.append(label)

        self.formal_font = Gtk.Button.new_with_label()
        self.formal_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["formal"]))[0]:
                self.formal_font.font_idx = idx
                break
        self.formal_font.set_label(constants.FONTS_LIST[self.formal_font.font_idx][0])

        hbox.append(self.formal_font)
        self.formal_font.connect("clicked", self.set_formal_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["formal"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'formal')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Letter
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Letter:           </tt>')
        hbox.append(label)

        self.letter_font = Gtk.Button.new_with_label()
        self.letter_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["letter"]))[0]:
                self.letter_font.font_idx = idx
                break
        self.letter_font.set_label(constants.FONTS_LIST[self.letter_font.font_idx][0])

        hbox.append(self.letter_font)
        self.letter_font.connect("clicked", self.set_letter_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["letter"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'letter')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Heading
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Heading:          </tt>')
        hbox.append(label)

        self.heading_font = Gtk.Button.new_with_label()
        self.heading_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["heading"]))[0]:
                self.heading_font.font_idx = idx
                break
        self.heading_font.set_label(constants.FONTS_LIST[self.heading_font.font_idx][0])

        hbox.append(self.heading_font)
        self.heading_font.connect("clicked", self.set_heading_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["heading"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'heading')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Audio
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Audio:            </tt>')
        hbox.append(label)

        self.audio_font = Gtk.Button.new_with_label()
        self.audio_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["audio"]))[0]:
                self.audio_font.font_idx = idx
                break
        self.audio_font.set_label(constants.FONTS_LIST[self.audio_font.font_idx][0])

        hbox.append(self.audio_font)
        self.audio_font.connect("clicked", self.set_audio_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["audio"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'audio')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Thought
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Thought:          </tt>')
        hbox.append(label)

        self.thought_font = Gtk.Button.new_with_label()
        self.thought_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["thought"]))[0]:
                self.thought_font.font_idx = idx
                break
        self.thought_font.set_label(constants.FONTS_LIST[self.thought_font.font_idx][0])

        hbox.append(self.thought_font)
        self.thought_font.connect("clicked", self.set_thought_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["thought"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'thought')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        ## Sign
        hbox = Gtk.HBox(True, 0)

        label = Gtk.Label()
        label.set_markup('<tt>Sign:             </tt>')
        hbox.append(label)

        self.sign_font = Gtk.Button.new_with_label()
        self.sign_font.font_idx = 0
        for idx, font in enumerate(constants.FONTS_LIST, start=0):
            if font[0] == os.path.splitext(os.path.basename(self.acbf_document.font_styles["sign"]))[0]:
                self.sign_font.font_idx = idx
                break
        self.sign_font.set_label(constants.FONTS_LIST[self.sign_font.font_idx][0])

        hbox.append(self.sign_font)
        self.sign_font.connect("clicked", self.set_sign_font)

        color = Gdk.color_parse(self.acbf_document.font_colors["sign"])
        color_button = Gtk.ColorButton(color)
        color_button.set_title('Select Color')
        color_button.connect("color-set", self.set_font_color, 'sign')
        hbox.append(color_button)

        hbox.show_all()
        entries_box.append(hbox)

        # show it
        dialog.vbox.append(entries_box)
        dialog.show_all()
        response = dialog.run()

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
        return'''

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
        self.font_dialog = fontselectiondialog.FontSelectionDialog(self, "Commentary Font",
                                                                   self.commentary_font.font_idx)
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

    def edit_genres(self, widget: Gtk.Button, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_genres.GenresDialog(self)
        dialog.present()

    def edit_authors(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition = 0, doc_auth: bool = False):
        dialog = edit_authors.AuthorsDialog(self, doc_auth)
        dialog.present()

    def edit_series(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_series.SeriesDialog(self)
        dialog.present()

    def edit_characters(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_characters.CharacterDialog(self)
        dialog.present()

    def edit_keywords(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_keywords.KeywordsDialog(self)
        dialog.present()

    def edit_languages(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_languages.LanguageDialog(self)
        dialog.present()

    def edit_dbref(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_dbref.DBRefDialog(self)
        dialog.present()

    def edit_ratings(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_content_rating.ContentRatingsDialog(self)
        dialog.present()

    def edit_source(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_sources.SourcesDialog(self)
        dialog.present()

    def edit_history(self, widget: Gtk.Entry, pos_icon: Gtk.EntryIconPosition):
        dialog = edit_history.HistoryDialog(self)
        dialog.present()

    def genre_widget_update(self):
        self.genres.set_placeholder_text(", ".join([g[0].replace("_", " ").capitalize() for g in self.acbf_document.genres]))

    def char_widget_update(self) -> None:
        self.characters.set_placeholder_text(", ".join(sorted(self.acbf_document.characters)))

    def sources_widget_update(self) -> None:
        self.source.set_placeholder_text(", ".join(self.acbf_document.sources))

    def history_widget_update(self) -> None:
        self.history.set_placeholder_text(", ".join(self.acbf_document.history))

    def rating_widget_update(self) -> None:
        self.rating.set_placeholder_text(", ".join([f"{r[0]} - {r[1]}" for r in self.acbf_document.content_ratings]))

    def series_widget_update(self) -> None:
        self.series.set_placeholder_text(", ".join([s[0] for s in self.acbf_document.sequences]))

    def keywords_widget_update(self) -> None:
        self.keywords.set_placeholder_text(", ".join(sorted(self.acbf_document.keywords)))

    def dbref_widget_update(self) -> None:
        current = self.databaseref.get_text()
        dbnames = []
        for item in self.acbf_document.databaseref:
            dbnames.append(item["dbname"])
        self.databaseref.set_placeholder_text(", ".join(dbnames))

    def lang_widget_update(self) -> None:
        languages: list[str] = []
        for lang in self.acbf_document.languages:
            if lang[1]:
                languages.append(lang[0])
            else:
                languages.append(lang[0] + " (no text layer)")

        self.languages.set_placeholder_text(", ".join(languages))

    def authors_widget_update(self):
        authors_text = []
        for authors in self.acbf_document.authors:
            if authors.get("first_name"):
                authors_text.append(authors["first_name"] + " " + authors.get("last_name", ""))
            elif authors.get("nickname"):
                authors_text.append(authors["nickname"])

        self.authors.set_placeholder_text(", ".join(authors_text))

    def doc_authors_widget_update(self):
        authors_text = []
        for authors in self.acbf_document.doc_authors:
            if authors.get("first_name"):
                authors_text.append(authors["first_name"] + " " + authors.get("last_name", ""))
            elif authors.get("nickname"):
                authors_text.append(authors["nickname"])

        self.doc_author.set_placeholder_text(", ".join(authors_text))

    def anno_widget_update(self):
        anno_text: str = ""
        item: Language = self.lang_button.get_selected_item()
        if item:
            anno_text = self.acbf_document.annotation.get(item.lang_iso, "")
        # If this is placeholder text any newlines expand the box
        self.annotation.set_text(anno_text)

    def edit_annotation(self, widget: Gtk.Widget, pos):
        def save_and_exit(widget, popup: Gtk.Popover):
            new_text = anno_text.get_buffer().get_text(anno_text.get_buffer().get_bounds()[0], anno_text.get_buffer().get_bounds()[1], False)
            if new_text != old_text:
                self.acbf_document.annotation[self.lang_button.get_selected_item().lang_iso] = new_text
                self.anno_widget_update()
                self.modified()
            popup.popdown()

        popup = Gtk.Popover()
        popup.set_parent(widget)
        popup.connect("closed", save_and_exit, popup)

        anno_text: Gtk.TextView = Gtk.TextView()
        anno_text.set_size_request(500, 200)
        anno_text.set_margin_end(5)
        anno_text.set_margin_start(5)
        anno_text.set_margin_top(5)
        anno_text.set_margin_bottom(5)
        anno_text.set_wrap_mode(Gtk.WrapMode.WORD)
        anno_text.get_buffer().set_text(unescape(self.acbf_document.annotation.get(self.lang_button.get_selected_item().lang_iso, "")))
        old_text = anno_text.get_buffer().get_text(anno_text.get_buffer().get_bounds()[0], anno_text.get_buffer().get_bounds()[1], False)

        popup.set_child(anno_text)
        popup.popup()

    def edit_publish_date(self, widget, pos):
        popup = Gtk.Popover()
        popup.set_parent(widget)
        calendar = Gtk.Calendar()

        try:
            calendar_date = GLib.DateTime.new_from_iso8601(self.publish_date.get_text() + "T00:00:00Z")
        except Exception as e:
            calendar_date = GLib.DateTime.new_now_local()
            logger.warning(f"Failed to parse date: {self.publish_date.get_text()} with error: {e}")

        calendar.select_day(calendar_date)
        calendar.connect('day-selected', self.update_publish_date_entry)

        popup.set_child(calendar)

        popup.show()

    def edit_creation_date(self, widget, pos):
        popup = Gtk.Popover()
        popup.set_parent(widget)
        calendar = Gtk.Calendar()

        try:
            calendar_date = GLib.DateTime.new_from_iso8601(self.creation_date.get_text() + "T00:00:00Z")
        except Exception as e:
            calendar_date = GLib.DateTime.new_now_local()
            logger.warning(f"Failed to parse date: {self.creation_date.get_text()} with error: {e}")

        calendar.select_day(calendar_date)
        calendar.connect('day-selected', self.update_creation_date_entry)

        popup.set_child(calendar)

        popup.show()

    def update_publish_date_entry(self, widget: Gtk.Calendar) -> None:
        publish_date = widget.get_date().format("%Y-%m-%d")
        self.publish_date.set_text(publish_date)
        self.modified()

    def update_creation_date_entry(self, widget: Gtk.Calendar) -> None:
        publish_date = widget.get_date().format("%Y-%m-%d")
        self.creation_date.set_text(publish_date)
        self.modified()

    def update_forms(self, is_new):
        if is_new:
            #self.coverpage.set_from_pixbuf(self.pil_to_pixbuf(self.acbf_document.cover_page, "#000"))
            if self.acbf_document.cover_page is not None:
                #self.coverpage.set_from_paintable(self.pil_to_paintable(self.acbf_document.cover_page))
                self.coverpage.set_pixbuf(self.pil_to_pixbuf(self.acbf_document.cover_page))
            book_title = ""
            if self.acbf_document.valid:
                try:
                    book_title = unescape(self.book_title_list[self.lang_button.get_selected_item().lang_iso])
                except:
                    try:
                        book_title = unescape(self.book_title_list["en"])
                    except:
                        book_title = ""

            self.anno_widget_update()
            self.book_title.set_text(book_title)
            self.set_header_title()
            self.keywords_widget_update()
            self.publisher.set_text(unescape(self.acbf_document.publisher))
            self.city.set_text(self.acbf_document.city)
            self.isbn.set_text(self.acbf_document.isbn)
            self.version.set_text(self.acbf_document.version)
            self.license.set_text(self.acbf_document.license)

        self.authors_widget_update()
        self.doc_authors_widget_update()

        '''if self.acbf_document.doc_authors == "" and self.acbf_document.valid:
            for item in self.acbf_document.tree.findall("meta-data/document-info/author"):
                self.acbf_document.tree.find("meta-data/document-info").remove(item)

            element = xml.SubElement(self.acbf_document.tree.find("meta-data/document-info"), "author")
            for author in ["first-name", "middle-name", "nickname", "last-name"]:
                name = self.preferences.get_value(author.replace("-", "_"))
                if name is not None:
                    element_fn = xml.SubElement(element, author)
                    element_fn.text = str(name)

            self.acbf_document.load_metadata()
        self.doc_author.set_text(self.acbf_document.doc_authors)'''
        self.doc_id.set_text(self.acbf_document.id)

        '''sequences = ""
        for sequence in self.acbf_document.sequences:
            sequences = sequences + unescape(sequence[0]) + ' (' + sequence[1] + '), '
        sequences = sequences[:-2]'''
        #self.series.set_text(", ".join(self.acbf_document.get_sequences()))
        self.series_widget_update()
        self.genre_widget_update()
        self.char_widget_update()
        '''languages = ""
        for language in self.acbf_document.languages:
            if language[1] == "FALSE":
                languages = languages + language[0] + "(no text layer), "
            else:
                languages = languages + language[0] + ", "
        languages = languages[:-2]'''

        self.lang_widget_update()
        self.dbref_widget_update()
        self.sources_widget_update()
        self.history_widget_update()
        self.rating_widget_update()
        self.publish_date.set_text(self.acbf_document.publish_date_value)
        self.creation_date.set_text(self.acbf_document.creation_date)

        if len(self.acbf_document.languages) > 1: # or self.acbf_document.languages[0][0] != "??":
            self.lang_button.set_sensitive(True)
        else:
            self.lang_button.set_sensitive(False)

        self.modified(False)
        return

    # toolbar actions
    def open_file(self, *args):
        self.filename_before = self.filename
        filechooser.FileChooserDialog(self).open_file_dialog()

    def revert_file(self, *args):
        self.opened_file()

    def opened_file(self):
        """Triggered from open (async) dialog"""
        if self.filename_before != self.filename:
            try:
                self.acbf_document = acbfdocument.ACBFDocument(self, self.filename)
            except Exception as e:
                logger.error(e)

            self.book_title_list = self.acbf_document.book_title

            self.update_languages()
            self.update_forms(True)

        if self.acbf_document.valid:
            self.panes.set_sensitive(True)
            self.save_action.set_enabled(True)
            self.save_button.set_sensitive(True)
            self.toc_action.set_enabled(True)
            self.frames_action.set_enabled(True)
            self.lang_action.set_enabled(True)
            self.styles_action.set_enabled(True)
            self.modified(False)
        else:
            self.panes.set_sensitive(False)
            self.save_action.set_enabled(False)
            self.save_button.set_sensitive(False)
            self.toc_action.set_enabled(False)
            self.lang_action.set_enabled(False)
            self.frames_action.set_enabled(False)
            self.styles_action.set_enabled(False)

    def show_about_window(self, action, param):
        logo = Gdk.Texture.new_from_filename("./images/acbfe.png")
        dialog: Gtk.AboutDialog = Gtk.AboutDialog.new()
        dialog.set_program_name("ACBF Editor")
        dialog.set_version(constants.VERSION)
        dialog.set_license_type(Gtk.License(Gtk.License.GPL_3_0))
        dialog.set_comments("ACBF Editor is a tool to create and edit Advanced Comic Book Format files")
        dialog.set_website("http://launchpad.net/acbf")
        dialog.add_credit_section("Creator", ["Robert Kubik"])
        dialog.add_credit_section("Developer(s)", ["mizaki"])
        #dialog.set_translator_credits("Name1 url")
        dialog.set_copyright("© 2013-2019 Robert Kubik")
        dialog.set_logo(logo)

        dialog.present()

    '''def set_titlepage(self, widget, event, hbox):
        print("set title page")
        for i in hbox.get_children():
            if i.get_name() == "GtkComboBox":
                page_image, bg_color = self.acbf_document.load_page_image(i.get_active() + 2)
                page_image.thumbnail((200, 200), Image.Resampling.BICUBIC)
                self.titlepage.set_from_pixbuf(self.pil_to_pixbuf(page_image, '#000'))
        return'''

    def change_language(self, widget: Gtk.DropDown, _pspec: int) -> None:
        # TODO check for unsaved changes
        self.update_forms(True)

    def update_languages(self):
        self.all_lang_store.remove_all()
        for lang in self.acbf_document.languages:
            lang_info = isocodes.languages.get(alpha_2=lang[0])
            if lang_info:
                lang_text = lang_info.get("name", "")
                new_lang = Language(lang_iso=lang[0], show=lang[1], lang=lang_text if lang[1] else lang_text + " (no text layers)")
                self.all_lang_store.append(new_lang)

        self.lang_store = self.dedupe_langs(self.all_lang_store)
        self.lang_button.set_model(self.lang_store)
        self.lang_button.set_selected(0)

    def edit_frames(self, *args):
        frames_dialog = frames_editor.FramesEditorDialog(self)
        frames_dialog.present()

    def save_file(self, *args):
        self.saved_file(self.original_filename)

    def save_as_file(self, *args):
        save_file_dialog = filechooser.FileChooserDialog(self).save_file_dialog()

    def saved_file(self, filename: str):
        self.modified(False)
        to_remove = self.acbf_document.tree.findall("meta-data/book-info/book-title")
        for i in to_remove:
            self.acbf_document.tree.find("meta-data/book-info").remove(i)

        if self.lang_button.get_selected_item().lang_iso in self.book_title_list:
            self.book_title_list[self.lang_button.get_selected_item().lang_iso] = self.book_title.get_text()

        for title in list(self.book_title_list.items()):
            if title[0] != '??' and title[1] is not None and title[1] != '':
                new_title = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "book-title",
                                           lang=title[0])
                new_title.text = unescape(str(title[1]))
            elif title[0] == '??':
                new_title = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "book-title")
                new_title.text = unescape(str(title[1]))

        to_remove = self.acbf_document.tree.findall("meta-data/book-info/annotation")
        for i in to_remove:
            self.acbf_document.tree.find("meta-data/book-info").remove(i)

        for anno in list(self.acbf_document.annotation.items()):
            if anno[0] == '??' and anno[1] is not None and anno[1] != '':
                new_anno = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "annotation")
                for line in anno[1].split('\n'):
                    new_line = xml.SubElement(new_anno, "p")
                    new_line.text = str(line)
            elif anno[1] is not None and anno[1] != '':
                new_anno = xml.SubElement(self.acbf_document.tree.find("meta-data/book-info"), "annotation",
                                          lang=anno[0])
                for line in anno[1].split('\n'):
                    new_line = xml.SubElement(new_anno, "p")
                    new_line.text = str(line)

        self.modify_element("meta-data/publish-info/publisher", self.publisher.get_text())
        self.modify_element("meta-data/publish-info/city", self.city.get_text())
        self.modify_element("meta-data/publish-info/isbn", self.isbn.get_text())
        self.modify_element("meta-data/publish-info/license", self.license.get_text())

        self.write_file(filename)

    def write_file(self, output_file):
        if not self.is_cmd_line:
            progress_dialog = Gtk.Window()
            progress_dialog.set_transient_for(self)
            progress_dialog.set_title("Saving file...")
            progress_dialog.set_resizable(False)
            progress_dialog.set_size_request(100, 400)
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_size_request(-1, 13)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.append(progress_bar)

            progress_dialog.set_child(box)
            progress_dialog.present()

        print("Saving file ...", output_file)

        try:
            # create tree with namespace
            tree = xml.Element("ACBF", xmlns="http://www.acbf.info/xml/acbf/1.1")
            for element in self.acbf_document.tree.getroot():
                tree.append(deepcopy(element))

            with open(os.path.join(self.tempdir, os.path.basename(self.filename)), 'wb') as f:
                f.write(xml.tostring(tree, pretty_print=True, xml_declaration=True))

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
                        fraction = float(processed_files) / total_files
                        if not self.is_cmd_line:
                            progress_bar.set_fraction(fraction)
                        filename = os.path.join(root, f)
                        if os.path.isfile(filename):  # regular files only
                            arcname = os.path.join(os.path.relpath(root, self.tempdir), f)
                            zip.write(filename, arcname)

            # print self.original_filename, self.filename, return_filename
            # print xml.tostring(self.acbf_document.tree, pretty_print=True)
            output_file_size = round(float(os.path.getsize(output_file)) / 1024 / 1024, 2)
            if not self.is_cmd_line:
                progress_dialog.close()
            else:
                logger.info("File size: " + str(self.original_file_size) + " MB" + " -> " + str(
                    output_file_size) + " MB" + " -> " + str(
                    round((output_file_size / float(self.original_file_size)) * 100, 1)) + " %")

        except Exception as e:
            if not self.is_cmd_line:
                progress_dialog.close()
                message = Gtk.AlertDialog()
                message.set_message("Failed to save comic book.\n\n" + 'Exception: %s' % e)
                logger.error(f"Failed to save comic book. Exception: {e}")
                message.show()
            else:
                logger.error(f"Failed to save comic book. Exception: {e}")

        logger.info("Done")
        return

    def add_element(self, element, sub_element, text):
        if text is not None and text != '':
            new_element = xml.SubElement(element, sub_element)
            new_element.text = str(text)

    def modify_element(self, path, value):
        element_name = path.split('/')[-1]
        element_path = path[:len(path) - len(path.split('/')[-1]) - 1]
        element = self.acbf_document.tree.find(path)

        if element is None:
            element = xml.SubElement(self.acbf_document.tree.find(element_path), element_name)
        element.text = str(value)

        return

    def entry_changed(self, widget: Gtk.Entry):
        self.modified()

    def exit_program(self, *args):
        logger.info("exit")
        self.clean_temp()
        self.app.quit()
        #sys.exit(1)

    def terminate_program(self, *args):
        def handle_response(dialog: Gtk.AlertDialog, task: Gio.Task, data: Any):
            response = dialog.choose_finish(task)
            if response == 2:
                self.disconnect_by_func(self.terminate_program)
                self.exit_program()
                #self.close()
            elif response == 1:
                self.disconnect_by_func(self.terminate_program)
                self.save_file()
                self.exit_program()
                #self.close()
            else:
                pass

        if self.is_modified:
            alert = Gtk.AlertDialog()
            alert.set_message("Unsaved Changes")
            alert.set_detail("There are unsaved changes that will be lost:")
            alert.set_buttons(["Cancel", "Save and Close", "Close"])
            alert.set_cancel_button(0)
            alert.set_default_button(1)
            alert.choose(self, None, handle_response, None)
        else:
            return False

        self.exit_program()
        return True

    def clean_temp(self, *args):
        # clear temp directory
        logger.info("clean temp")
        for root, dirs, files in os.walk(self.tempdir):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))
        shutil.rmtree(self.tempdir, ignore_errors=True)
        logger.info("finish clean temp")
        return False

    def modified(self, modified: bool = True) -> None:
        if self.is_modified is not modified:
            self.is_modified = modified
            self.set_header_title()

    def pil_to_paintable(self, PILImage):
        # TODO for GTK5?
        if PILImage is None:
            PILImage = Image.new("RGBA", (150, 200), (0, 0, 0, 0))

        buffer = GLib.Bytes.new(PILImage.tobytes())
        texture = Gdk.Texture.new_from_bytes(buffer)

        image = Gtk.Image.new_from_paintable(texture)

        return texture

    def pil_to_pixbuf(self, PILImage):
        # Parse the background color to get the RGB values
        '''bcolor = Gdk.RGBA()
        bcolor.parse(BGColor)
        bcolor = (int(bcolor.red * 255), int(bcolor.green * 255), int(bcolor.blue * 255))'''

        try:
            PILImage = PILImage.convert("RGBA")

            # https://gist.github.com/mozbugbox/10cd35b2872628246140
            data = PILImage.tobytes()
            w, h = PILImage.size
            data = GLib.Bytes.new(data)
            pix = GdkPixbuf.Pixbuf.new_from_bytes(data, GdkPixbuf.Colorspace.RGB, True, 8, w, h, w * 4)
            return pix
            # Convert PIL image to RGBA format
            '''PILImage = PILImage.convert("RGBA")

            # Create a new background image with the specified color
            bg = Image.new("RGBA", PILImage.size, bcolor)

            # Composite the PIL image onto the background
            bg.paste(PILImage, (0, 0), PILImage)

            # Convert the composite image to PPM format and load into GdkPixbuf
            dummy_file = io.BytesIO()
            bg.save(dummy_file, "ppm")
            dummy_file.seek(0)  # Go to the start of the BytesIO buffer
            contents = dummy_file.read()
            dummy_file.close()

            loader = GdkPixbuf.PixbufLoader.new_with_type('pnm')
            loader.write(contents)
            loader.close()
            pixbuf = loader.get_pixbuf()
            return pixbuf'''
        except Exception as e:
            print("failed to create pixbuf with alpha: ", e)
            bg = Image.new("RGBA", (150, 200), (0, 0, 0, 0))

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
