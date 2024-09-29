"""acbfdocument.py - ACBF Document object.

Copyright (C) 2011-2018 Robert Kubik
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

import os.path
import shutil

import PIL.ImageFont
import lxml.etree as xml
from lxml import objectify
import base64
from gi.repository import GLib, Pango
from PIL import Image
from xml.sax.saxutils import escape
import io
import logging
import urllib.request, urllib.parse, urllib.error
import re
import zipfile
import uuid
# TODO remove
from matplotlib import font_manager

import constants

logger = logging.getLogger(__name__)


class ACBFDocument():
    def __init__(self, parent, filename):
        self.parent = parent
        self.cover_page = None
        self.cover_thumb = None
        self.pages_total: int = 0
        self.bg_color: str = '#000000'
        self.valid: bool = False
        self.filename: str = filename
        self.authors: list[
            dict[str, str]] = []  # activity, language, first_name, middle_name, last_name, nickname, home_page, email
        self.databaseref: list[dict[str, str, str]] = []  # dbname, dbtype, value
        self.genres: list[tuple[str, int]] = []
        self.characters: list[str] = []
        self.keywords: list[str] = []
        self.publisher = self.publish_date = self.city = self.isbn = self.license = self.publish_date_value = ""
        self.doc_authors: list[dict[str, str]] = []
        self.creation_date: str = ""
        self.sources: list[str] = []  # <source><p>source 1</p><p>source 2</p></source>
        self.id = ""
        self.version: str = ""
        self.history: list[str] = []  # <p> separated
        self.languages: list[tuple[str, bool]] = []  # en, False
        self.contents_table: list[tuple[str, str]] = []  # title, page
        self.sequences: list[tuple[str, str, str]] = []  # name, volume, number
        self.book_title: dict[str, str] = {}
        self.annotation: dict[str, str] = {}
        self.content_ratings: list[tuple[str, str]] = []  # (type, value)
        self.reading_direction: str = "LTR"
        # self.genres_dict = {}
        self.has_frames: bool = False
        self.fonts_dir: str = os.path.join(self.parent.tempdir, 'Fonts')
        self.font_styles: dict[str, str] = {'normal': '', 'emphasis': '', 'strong': '', 'code': '', 'commentary': '',
                                            'sign': '', 'formal': '', 'heading': '', 'letter': '', 'audio': '',
                                            'thought': ''}
        self.font_families: dict[str, str] = {'normal': '', 'emphasis': '', 'strong': '', 'code': '', 'commentary': '',
                                              'sign': '', 'formal': '', 'heading': '', 'letter': '', 'audio': '',
                                              'thought': ''}
        self.font_colors: dict[str, str] = {'inverted': '#ffffff', 'speech': '#000000', 'code': '#000000',
                                            'commentary': '#000000', 'sign': '#000000', 'formal': '#000000',
                                            'heading': '#000000', 'letter': '#000000', 'audio': '#000000',
                                            'thought': '#000000'}
        for style in ['normal', 'emphasis', 'strong', 'code', 'commentary', 'sign', 'formal', 'heading', 'letter',
                      'audio', 'thought']:
            self.font_styles[style] = constants.default_font

        try:
            self.base_dir = os.path.dirname(filename)
            self.tree = xml.parse(source=filename)
            root = self.tree.getroot()

            for elem in root.getiterator():
                i = elem.tag.find('}')
                if i >= 0:
                    elem.tag = elem.tag[i + 1:]
            objectify.deannotate(root)

            self.bookinfo = self.tree.find("meta-data/book-info")
            self.publishinfo = self.tree.find("meta-data/publish-info")
            self.docinfo = self.tree.find("meta-data/document-info")
            self.references = self.tree.find("references")
            self.bg_color = self.tree.find("body").get("bgcolor")
            if self.bg_color is None:
                self.bg_color = '#000000'
            self.pages = self.tree.findall("body/" + "page")
            self.pages_total = len(self.pages)
            self.binaries = self.tree.findall("data/" + "binary")
            self.load_metadata()
            self.get_contents_table()
            self.extract_fonts()
            self.stylesheet = self.tree.find("style")
            if self.stylesheet is not None:
                self.load_stylesheet()
            # self.tree = None # keep memory usage low
            self.valid = True
        except Exception as inst:
            logger.error("Unable to open ACBF file: %s %s" % (filename, inst))
            self.valid = False
            return

    def load_metadata(self):
        # Get cover page. While it is mandatory fallback to blank page
        try:
            image_id = self.bookinfo.find("coverpage/" + "image").get("href")
            image_uri = ImageURI(image_id)
            self.cover_page = self.load_image(image_uri)
        except Exception as e:
            logger.warning(f"Failed to load cover, using blank page. {e}")
            self.cover_page = Image.new("RGB", (50, 50), (0, 0, 0))
        self.cover_thumb = self.cover_page.copy()
        self.cover_thumb.thumbnail((200, 200), Image.Resampling.NEAREST)

        # Authors (mandatory)
        for author in self.bookinfo.findall("author"):
            first_name = middle_name = last_name = nickname = home_page = email = ""
            if author.find("first-name") is not None:
                first_name = author.find("first-name").text
            if author.find("middle-name") is not None:
                middle_name = author.find("middle-name").text
            if author.find("last-name") is not None:
                last_name = author.find("last-name").text
            if author.find("nickname") is not None:
                nickname = author.find("nickname").text
            if author.find("home-page") is not None:
                home_page = author.find("home-page").text
            if author.find("email") is not None:
                email = author.find("email").text

            author_record = {"activity": author.get("activity"), "language": author.get("lang"),
                             "first_name": first_name, "middle_name": middle_name, "last_name": last_name,
                             "nickname": nickname, "home_page": home_page, "email": email}
            self.authors.append(author_record)

        # book-title (mandatory)
        for title in self.bookinfo.findall("book-title"):
            if title.get("lang") == None or title.get("lang") == 'en':
                self.book_title['en'] = escape(title.text)
            else:
                if title.text == None:
                    self.book_title[title.get("lang")] = ''
                else:
                    self.book_title[title.get("lang")] = escape(title.text)
        if self.book_title == {}:
            self.book_title['??'] = escape(os.path.basename(self.filename))[:-5]

        # genres (mandatory)
        acbf_xml_genres: list[xml.Element] = self.bookinfo.findall("genre")
        for g in acbf_xml_genres:
            if g.text in constants.GENRES_LIST:
                self.genres.append((g.text, int(g.get("match", 0))))

        # languages
        '''self.languages = []
        for language in self.bookinfo.findall("languages/" + "text-layer"):
            self.languages.append((language.get("lang"), language.get("show").upper()))
        if len(self.languages) == 0:
            self.languages.append(('??', 'FALSE'))'''
        try:
            for language in self.bookinfo.findall("languages/text-layer"):
                #full_lang = isocodes.languages.get(alpha_2=language.get("lang"))
                show = False if language.get("show") == "False" else True
                self.languages.append((language.get("lang"), show))
            if len(self.languages) == 0:
                self.languages.append("en", False)
        except:
            pass

        # annotation (mandatory)
        for annotation in self.bookinfo.findall("annotation"):
            annotation_text = ""
            for line in annotation.findall("p"):
                if line.text is not None:
                    annotation_text = annotation_text + line.text + "\n"
            annotation_text = escape(annotation_text[:-1])

            if annotation.get("lang") is None:
                self.annotation["??"] = annotation_text
            else:
                self.annotation[annotation.get("lang")] = annotation_text

        # keywords
        self.keywords = get_element_text(self.bookinfo, "keywords").split(", ")

        # sequence
        try:
            for sequence in self.bookinfo.findall("sequence"):
                name = sequence.get("title") or ""
                volume = sequence.get("volume") or ""
                number = sequence.text or ""

                self.sequences.append((name, volume, number))
        except:
            pass

        # databaseref
        try:
            for line in self.bookinfo.findall("databaseref"):
                if line.text is not None:
                    dbname = line.get("dbname", "")
                    dbtype = line.get("type", "")
                    value = line.text or ""
                    self.databaseref.append({"dbname": dbname, "dbtype": dbtype, "value": value})
        except:
            pass

        try:
            for rating in self.bookinfo.findall("content-rating"):
                self.content_ratings.append((rating.get("type"), rating.text))
        except:
            pass

        try:
            direction = self.bookinfo.find("reading-direction")
            self.reading_direction = direction.text
        except:
            pass

        # characters
        try:
            for line in self.bookinfo.findall("characters/" + "name"):
                self.characters.append(line.text)
        except:
            pass

        # publish-info

        # publisher (mandatory)
        self.publisher = get_element_text(self.publishinfo, 'publisher')

        # publish date (mandatory)
        if self.publishinfo.find("publish-date") is not None:
            if self.publishinfo.find("publish-date").get("value") is not None:
                self.publish_date_value = self.publishinfo.find("publish-date").get("value")
                self.publish_date = ' (' + self.publish_date_value + ')'
            self.publish_date = get_element_text(self.publishinfo, 'publish-date') + self.publish_date

        self.city = get_element_text(self.publishinfo, 'city')
        self.isbn = get_element_text(self.publishinfo, 'isbn')
        self.license = get_element_text(self.publishinfo, 'license')

        # document-info
        '''for doc_author in self.docinfo.findall("author"):
            for element in ['first-name', 'middle-name', 'nickname', 'last-name']:
                name = get_element_text(doc_author, element)
                if name != '':
                    self.doc_authors = self.doc_authors + name + ' '
            self.doc_authors = self.doc_authors[:-1] + ', '
        self.doc_authors = self.doc_authors[:-2]'''
        # doc author (mandatory)
        for doc_author in self.docinfo.findall("author"):
            first_name = middle_name = last_name = nickname = home_page = email = ""
            if doc_author.find("first-name") is not None:
                first_name = doc_author.find("first-name").text
            if doc_author.find("middle-name") is not None:
                middle_name = doc_author.find("middle-name").text
            if doc_author.find("last-name") is not None:
                last_name = doc_author.find("last-name").text
            if doc_author.find("nickname") is not None:
                nickname = doc_author.find("nickname").text
            if doc_author.find("home-page") is not None:
                home_page = doc_author.find("home-page").text
            if doc_author.find("email") is not None:
                email = doc_author.find("email").text

            doc_author_record = {"activity": doc_author.get("activity"), "language": doc_author.get("lang"),
                                 "first_name": first_name, "middle_name": middle_name, "last_name": last_name,
                                 "nickname": nickname, "home_page": home_page, "email": email}
            self.doc_authors.append(doc_author_record)

        # acbf doc creation date (mandatory)
        try:
            self.creation_date = self.docinfo.find("creation-date").get("value")
            if self.creation_date is None:
                self.creation_date = get_element_text(self.docinfo, "creation-date")
        except:
            self.creation_date = GLib.DateTime.new_now_local().format("%Y-%m-%d")
        if self.creation_date == "":
            self.creation_date = GLib.DateTime.new_now_local().format("%Y-%m-%d")

        try:
            for line in self.docinfo.findall("source/" + "p"):
                self.sources.append(line.text)
        except:
            pass

        self.id = get_element_text(self.docinfo, 'id')
        if self.id == "":
            self.id = str(uuid.uuid1())

        self.version = get_element_text(self.docinfo, 'version')

        try:
            for line in self.docinfo.findall("history/" + "p"):
                self.history.append(line.text)
        except:
            pass

        # has frames
        for page in self.pages:
            for frame in page.findall("frame"):
                self.has_frames = True

    def load_image(self, image_uri):
        # print image_uri.file_type, image_uri.archive_path, image_uri.file_path, self._window.tempdir
        try:
            if image_uri.file_type == "embedded":
                for image in self.binaries:
                    if image.get("id") == image_uri.file_path:
                        decoded = base64.b64decode(image.text)
                        return Image.open(io.StringIO(decoded))
            elif image_uri.file_type == "zip":
                z = zipfile.ZipFile(os.path.join(self.base_dir, image_uri.archive_path))
                z.extract(image_uri.file_path, self.parent.tempdir)
                return Image.open(os.path.join(self.parent.tempdir, image_uri.file_path))
            elif image_uri.file_type == "http":
                try:
                    http_image = Image.open(io.StringIO(urllib.request.urlopen(image_uri.file_path).read()))
                    return http_image
                except:
                    logger.error(f"Failed to load HTTP image: {image_uri.file_path}")
                    '''md = Gtk.MessageDialog(self.parent, Gtk.DialogFlags.DESTROY_WITH_PARENT, Gtk.MessageType.ERROR,
                                           Gtk.ButtonsType.CLOSE, "Error loading image: " + page_image_id)
                    md.run()
                    md.destroy()'''
            else:
                return Image.open(os.path.join(self.base_dir, image_uri.file_path))

        except Exception as inst:
            logger.warning("Unable to read image: %s" % inst)
            return None

    def load_page_image(self, page_num=1):
        if page_num == 1:
            pilBackgroundImage = self.cover_page
            page_bg_color = '#000000'
        else:
            image_id = self.pages[page_num - 2].find("image").get("href")
            page_bg_color = self.pages[page_num - 2].get("bgcolor")
            if page_bg_color == None:
                page_bg_color = self.bg_color

            image_uri = ImageURI(image_id)
            pilBackgroundImage = self.load_image(image_uri)

        return pilBackgroundImage, page_bg_color

    def load_page_frames(self, page_num=1):
        if page_num == 1:
            xml_frames = self.bookinfo.findall("coverpage/" + "frame")
            if xml_frames == None:
                return []
        else:
            xml_frames = self.pages[page_num - 2].findall("frame")
        frames = []
        coordinate_list = []
        for frame in xml_frames:
            for coordinate in frame.get("points").split(' '):
                coordinate_tuple = (int(coordinate.split(',')[0]), int(coordinate.split(',')[1]))
                coordinate_list.append(coordinate_tuple)
            frame_tuple = (coordinate_list, frame.get("bgcolor"))
            frames.append(frame_tuple)
            coordinate_list = []
        return frames

    def load_page_texts(self, page_num, language):
        text_areas = []
        references = []
        all_lines = ""
        text_rotation = 0
        area_type = "speech"
        inverted = False
        if page_num == 1:
            return text_areas, references
        for text_layer in self.pages[page_num - 2].findall("text-layer"):
            if text_layer.get("bgcolor") is not None:
                bgcolor_layer = text_layer.get("bgcolor")
            else:
                bgcolor_layer = "#ffffff"
            if text_layer.get("lang") == language:
                for text_area in text_layer.findall("text-area"):
                    if text_area.get("bgcolor") is not None:
                        bgcolor = text_area.get("bgcolor")
                    else:
                        bgcolor = bgcolor_layer
                    if text_area.get("text-rotation") is not None:
                        text_rotation = int(text_area.get("text-rotation"))
                    else:
                        text_rotation = 0
                    if text_area.get("type") is not None:
                        area_type = text_area.get("type")
                    else:
                        area_type = "speech"
                    if text_area.get("inverted") is None:
                        inverted = False
                    elif text_area.get("inverted").upper() == "TRUE":
                        inverted = True
                    else:
                        inverted = False
                    if text_area.get("transparent") is None:
                        transparent = False
                    elif text_area.get("transparent").upper() == "TRUE":
                        transparent = True
                    else:
                        transparent = False
                    coordinate_list = []
                    area_text = ""
                    for coordinate in text_area.get("points").split(" "):
                        coordinate_tuple = (int(coordinate.split(',')[0]), int(coordinate.split(",")[1]))
                        coordinate_list.append(coordinate_tuple)
                    for paragraph in text_area.findall("p"):
                        area_text = area_text + re.sub(r"<p[^>]*>", "", xml.tostring(paragraph, encoding="Unicode",
                                                                                     with_tail=False)).replace("</p>",
                                                                                                               " <BR>")
                        # references
                        for reference in paragraph.findall("a"):
                            for item in self.references.findall("reference"):
                                if item.get("id") == reference.get("href")[1:]:
                                    all_lines = ''
                                    for line in item.findall("p"):
                                        all_lines = all_lines + line.text + '\n'
                                    all_lines = all_lines[:-2]
                                    references.append((reference.get("href")[1:], all_lines))
                        for commentary in paragraph.findall("commentary"):
                            for reference in commentary.findall("a"):
                                for item in self.references.findall("reference"):
                                    if item.get("id") == reference.get("href")[1:]:
                                        all_lines = ""
                                        for line in item.findall("p"):
                                            all_lines = all_lines + line.text + "\n"
                                        all_lines = all_lines[:-2]
                                        references.append((reference.get("href")[1:], all_lines))

                    area_text = area_text[:-5]
                    text_area_tuple = (
                        coordinate_list, area_text, bgcolor, text_rotation, area_type, inverted, transparent)
                    text_areas.append(text_area_tuple)

        # print(xml.tostring(text_areas[0][1][0], pretty_print=True))

        return text_areas, references

    def get_page_transition(self, page_num) -> int | None:
        if page_num == 1:
            return None
        elif self.pages[page_num - 2].get("transition") is None:
            return None
        else:
            return self.pages[page_num - 2].get("transition")

    def get_contents_table(self):
        self.contents_table = []
        for lang in self.languages:
            contents = []
            for idx, page in enumerate(self.pages, start=2):
                for title in page.findall("title"):
                    if (title.get("lang") == lang[0]) or (title.get("lang") == None):
                        contents.append((title.text, str(idx)))
            self.contents_table.append(contents)

    def load_stylesheet(self):
        # print self.stylesheet.text
        # sheet = cssutils.parseString(self.stylesheet.text)
        font = ''

        for rule in self.stylesheet.text.replace('\n', ' ').split('}'):
            if rule.strip() != '':
                selector = rule.strip().split('{')[0].strip().upper()
                # print "selectorText: ", selector
                font_style = 'normal'
                font_weight = 'normal'
                font_stretch = 'normal'
                font_families = ''
                for style in rule.strip().split('{')[1].strip().split(';'):
                    if style != '':
                        # print "style:", style.split(':')[0].strip()
                        # print "value:", style.split(':')[1].strip()
                        current_style = style.split(':')[0].strip().upper()
                        if current_style == 'FONT-FAMILY':
                            font_families = style.split(':')[1].strip()
                        elif current_style == 'FONT-STYLE':
                            font_style = style.split(':')[1].strip()
                        elif current_style == 'FONT-WEIGHT':
                            font_weight = style.split(':')[1].strip()
                        elif current_style == 'FONT-STRETCH':
                            font_stretch = style.split(':')[1].strip()

                        if selector == '*' and current_style == 'COLOR':
                            self.font_colors['speech'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[INVERTED=TRUE]' and current_style == 'COLOR':
                            self.font_colors['inverted'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=SPEECH]' and current_style == 'COLOR':
                            self.font_colors['speech'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=COMMENTARY]' and current_style == 'COLOR':
                            self.font_colors['commentary'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=FORMAL]' and current_style == 'COLOR':
                            self.font_colors['formal'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=LETTER]' and current_style == 'COLOR':
                            self.font_colors['letter'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=CODE]' and current_style == 'COLOR':
                            self.font_colors['code'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=HEADING]' and current_style == 'COLOR':
                            self.font_colors['heading'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=AUDIO]' and current_style == 'COLOR':
                            self.font_colors['audio'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=THOUGHT]' and current_style == 'COLOR':
                            self.font_colors['thought'] = style.split(':')[1].strip().strip('"')
                        elif selector == 'TEXT-AREA[TYPE=SIGN]' and current_style == 'COLOR':
                            self.font_colors['sign'] = style.split(':')[1].strip().strip('"')

                if font_families != '':
                    for font_family in font_families.split(','):
                        # check if font exists in acbf document
                        font_family_stripped = font_family.strip().strip('"')
                        if os.path.isfile(os.path.join(self.fonts_dir, font_family_stripped)):
                            font = os.path.join(self.fonts_dir, font_family_stripped)
                            font_obj = PIL.ImageFont.truetype(font)
                            font_families_list = font_families.split(", ")
                            font_families_list[0] = font_obj.font.family
                            font_families = ", ".join(font_families_list)
                            break

                        # search in system fonts
                        # TODO Not use matplotlib just to search for fonts
                        '''font_map = Pango.Context().get_font_map()
                        font_families = font_map.list_families()
                        for family in font_families:
                            if family.get_name() == font_family_stripped:
                                pass'''

                        prop = font_manager.FontProperties(family=font_family_stripped, style=font_style,
                                                           weight=font_weight, stretch=font_stretch)
                        try:
                            font = font_manager.findfont(prop, fontext='ttf', fallback_to_default=False)
                        except Exception as e:
                            # TODO Use fallback
                            logging.warning(f"Failed load font: {e}")
                            break

                if selector in ('P', 'TEXT-AREA') and font != '':
                    self.font_styles['normal'] = font
                    self.font_families['normal'] = font_families
                elif selector == 'EMPHASIS' and font != '':
                    self.font_styles['emphasis'] = font
                    self.font_families['emphasis'] = font_families
                elif selector == 'STRONG' and font != '':
                    self.font_styles['strong'] = font
                    self.font_families['strong'] = font_families
                elif selector in ('CODE', 'TEXT-AREA[TYPE=CODE]', 'TEXT-AREA[TYPE="CODE"]') and font != '':
                    self.font_styles['code'] = font
                    self.font_families['code'] = font_families
                elif selector in (
                        'COMMENTARY', 'TEXT-AREA[TYPE=COMMENTARY]', 'TEXT-AREA[TYPE="COMMENTARY"]') and font != '':
                    self.font_styles['commentary'] = font
                    self.font_families['commentary'] = font_families
                elif selector in ('TEXT-AREA[TYPE=SIGN]', 'TEXT-AREA[TYPE="SIGN"]') and font != '':
                    self.font_styles['sign'] = font
                    self.font_families['sign'] = font_families
                elif selector in ('TEXT-AREA[TYPE=FORMAL]', 'TEXT-AREA[TYPE="FORMAL"]') and font != '':
                    self.font_styles['formal'] = font
                    self.font_families['formal'] = font_families
                elif selector in ('TEXT-AREA[TYPE=HEADING]', 'TEXT-AREA[TYPE="HEADING"]') and font != '':
                    self.font_styles['heading'] = font
                    self.font_families['heading'] = font_families
                elif selector in ('TEXT-AREA[TYPE=LETTER]', 'TEXT-AREA[TYPE="LETTER"]') and font != '':
                    self.font_styles['letter'] = font
                    self.font_families['letter'] = font_families
                elif selector in ('TEXT-AREA[TYPE=AUDIO]', 'TEXT-AREA[TYPE="AUDIO"]') and font != '':
                    self.font_styles['audio'] = font
                    self.font_families['audio'] = font_families
                elif selector in ('TEXT-AREA[TYPE=THOUGHT]', 'TEXT-AREA[TYPE="THOUGHT"]') and font != '':
                    self.font_styles['thought'] = font
                    self.font_families['thought'] = font_families

        for style in ['emphasis', 'strong', 'code', 'commentary', 'sign', 'formal', 'heading', 'letter', 'audio',
                      'thought']:
            if self.font_styles[style] == constants.default_font:
                self.font_styles[style] = self.font_styles['normal']

        for style in ['emphasis', 'strong', 'code', 'commentary', 'sign', 'formal', 'heading', 'letter', 'audio',
                      'thought']:
            if self.font_families[style] == constants.default_font:
                self.font_families[style] = self.font_families['normal']

        # print self.font_styles

    def extract_fonts(self):
        if os.path.exists(os.path.join(self.base_dir, 'Fonts')) and not os.path.exists(self.fonts_dir):
            shutil.copytree(os.path.join(self.base_dir, 'Fonts'), self.fonts_dir)
        if not os.path.exists(self.fonts_dir):
            os.makedirs(self.fonts_dir, 0o700)
        for font in self.binaries:
            if font.get("content-type") == 'application/font-sfnt':
                decoded = base64.b64decode(font.text)
                f = open(os.path.join(self.fonts_dir, font.get("id")), 'wb')
                f.write(decoded)
                f.close()

    def save_to_tree(self):
        """Save new data to self.tree"""
        def add_element(element, sub_element, text):
            if text is not None and text != '':
                new_element = xml.SubElement(element, sub_element)
                new_element.text = str(text)

        def modify_element(path, value):
            element_name = path.split('/')[-1]
            element_path = path[:len(path) - len(path.split('/')[-1]) - 1]
            element = self.tree.find(path)

            if element is None:
                element = xml.SubElement(self.tree.find(element_path), element_name)
            element.text = str(value)

            return

        for i in self.tree.findall("meta-data/book-info/book-title"):
            self.tree.find("meta-data/book-info").remove(i)
        for lang, title in self.book_title.items():
            ele: xml.SubElement = xml.SubElement(self.tree.find("meta-data/book-info"), "book-title")
            ele.text = str(title)
            ele.attrib["lang"] = lang

        for i in self.tree.findall("meta-data/book-info/annotation"):
            self.tree.find("meta-data/book-info").remove(i)
        for anno in list(self.annotation.items()):
            if anno[0] == '??' and anno[1] is not None and anno[1] != '':
                new_anno = xml.SubElement(self.tree.find("meta-data/book-info"), "annotation")
                for line in anno[1].split('\n'):
                    new_line = xml.SubElement(new_anno, "p")
                    new_line.text = str(line)
            elif anno[1] is not None and anno[1] != '':
                new_anno = xml.SubElement(self.tree.find("meta-data/book-info"), "annotation", lang=anno[0])
                for line in anno[1].split('\n'):
                    new_line = xml.SubElement(new_anno, "p")
                    new_line.text = str(line)

        # book authors
        for item in self.tree.findall("meta-data/book-info/author"):
            self.tree.find("meta-data/book-info").remove(item)
        for a in self.authors:
            if a.get('activity') == 'Translator':
                element = xml.SubElement(self.tree.find("meta-data/book-info"), "author", activity=a['activity'],
                                         lang=a.get('language', 'en'))
            else:
                element = xml.SubElement(self.tree.find("meta-data/book-info"), "author", activity=a['activity'])

            if a.get('first_name'):
                add_element(element, "first-name", a['first_name'])
            if a.get('middle_name'):
                add_element(element, "middle-name", a['middle_name'])
            if a.get('last_name'):
                add_element(element, "last-name", a['last_name'])
            if a.get('email'):
                add_element(element, "email", a['email'])
            if a.get('home_page'):
                add_element(element, "home-page", a['home_page'])
            if a.get('nickname'):
                add_element(element, "nickname", a['nickname'])

        for item in self.tree.findall("meta-data/book-info/sequence"):
            self.tree.find("meta-data/book-info").remove(item)
        for s in self.sequences:
            ele: xml.SubElement = xml.SubElement(self.tree.find("meta-data/book-info"), "sequence")
            ele.text = s[2]
            ele.attrib["title"] = s[0]
            if s[1]:
                ele.attrib["volume"] = s[1]

        for item in self.tree.findall("meta-data/book-info/genre"):
            self.tree.find("meta-data/book-info").remove(item)
        for s in self.genres:
            element = xml.SubElement(self.tree.find("meta-data/book-info"), "genre")
            element.text = s[0]
            if s[1]:
                element.attrib['match'] = str(s[1])

        self.tree.find("meta-data/book-info/characters").clear()
        for c in self.characters:
            add_element(self.tree.find("meta-data/book-info/characters"), "name", c)

        modify_element("meta-data/book-info/keywords", ", ".join(self.keywords))

        for item in self.tree.findall("meta-data/book-info/languages/text-layer"):
            self.tree.find("meta-data/book-info/languages").remove(item)
        for l in self.languages:
            element = xml.SubElement(self.tree.find("meta-data/book-info/languages"), "text-layer")
            element.attrib['lang'] = l[0]
            element.attrib['show'] = str(l[1])

        for item in self.tree.findall("meta-data/book-info/databaseref"):
            self.tree.find("meta-data/book-info").remove(item)
        for d in self.databaseref:
            element = xml.SubElement(self.tree.find("meta-data/book-info"), "databaseref")
            element.text = d['value']
            element.attrib['dbname'] = d['dbname']
            if d.get('dbtype'):
                element.attrib['type'] = d['dbtype']

        for item in self.tree.findall("meta-data/book-info/content-rating"):
            self.tree.find("meta-data/book-info").remove(item)
        for r in self.content_ratings:
            element = xml.SubElement(self.tree.find("meta-data/book-info"), "content-rating")
            element.text = r[1]
            if r[0]:
                element.attrib['type'] = r[0]

        modify_element("meta-data/book-info/reading-direction", self.reading_direction)

        # Publisher info
        modify_element("meta-data/publish-info/publisher", self.publisher)
        modify_element("meta-data/publish-info/city", self.city)
        modify_element("meta-data/publish-info/isbn", self.isbn)
        modify_element("meta-data/publish-info/license", self.license)

        pd = self.tree.find("meta-data/publish-info/publish-date")
        pd.text = self.publish_date
        pd.attrib['value'] = self.publish_date

        # ACBF document
        modify_element("meta-data/document-info/id", self.id)

        # ACBF document authors
        for item in self.tree.findall("meta-data/document-info/author"):
            self.tree.find("meta-data/document-info").remove(item)
        for a in self.doc_authors:
            if a.get('activity') == 'Translator':
                element = xml.SubElement(self.tree.find("meta-data/document-info/author"), "author", activity=a['activity'],
                                         lang=a.get('language', 'en'))
            else:
                element = xml.SubElement(self.tree.find("meta-data/document-info"), "author", activity=a['activity'])

            if a.get('first_name'):
                add_element(element, "first-name", a['first_name'])
            if a.get('middle_name'):
                add_element(element, "middle-name", a['middle_name'])
            if a.get('last_name'):
                add_element(element, "last-name", a['last_name'])
            if a.get('email'):
                add_element(element, "email", a['email'])
            if a.get('home_page'):
                add_element(element, "home-page", a['home_page'])
            if a.get('nickname'):
                add_element(element, "nickname", a['nickname'])

        cd = self.tree.find("meta-data/document-info/creation-date")
        cd.text = self.creation_date
        cd.attrib['value'] = self.creation_date

        self.tree.find("meta-data/document-info/source").clear()
        for s in self.sources:
            add_element(self.tree.find("meta-data/document-info/source"), "p", s)

        if self.version:
            modify_element("meta-data/document-info/version", self.version)

        self.tree.find("meta-data/document-info/history").clear()
        for h in self.history:
            add_element(self.tree.find("meta-data/document-info/history"), "p", h)


class ImageURI():

    def __init__(self, input_path):
        self.file_type = 'unknown'
        self.archive_path = ''
        self.file_path = ''

        if input_path[0:3] == 'zip':
            self.file_type = 'zip'
            self.archive_path = input_path[4:input_path.find('!')]
            self.file_path = input_path[input_path.find('!') + 2:]
        elif input_path[:1] == "#":
            self.file_type = 'embedded'
            self.file_path = input_path[1:]
        elif input_path[:7] == "http://":
            self.file_type = 'http'
            self.file_path = input_path
        else:
            self.file_path = input_path

        if input_path[:7] != "http://":
            if constants.PLATFORM == 'win32':
                self.archive_path = self.archive_path.replace('/', '\\')
                self.file_path = self.file_path.replace('/', '\\')
            else:
                self.archive_path = self.archive_path.replace('\\', '/')
                self.file_path = self.file_path.replace('\\', '/')


# function to retrieve text value from element without throwing exception
def get_element_text(element_tree, element):
    try:
        text_value = escape(element_tree.find(element).text)
        if text_value is None:
            text_value = ""
    except:
        text_value = ""
    return text_value
