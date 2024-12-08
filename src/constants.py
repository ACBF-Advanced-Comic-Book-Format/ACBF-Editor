"""constants.py - Miscellaneous constants.

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
import sys
from fontTools import ttLib

try:
  from . import portability
except Exception:
  import portability

VERSION = '3.0'
HOME_DIR = portability.get_home_directory()
CONFIG_DIR = portability.get_config_directory()
DATA_DIR = portability.get_data_directory()
FONTS_DIR = portability.get_fonts_directory()
PLATFORM = portability.get_platform()

exec_path = os.path.abspath(sys.argv[0])
BASE_DIR = os.path.dirname(os.path.dirname(exec_path))

# set icons directory
ICON_PATH = ''
if os.path.isfile(os.path.join(BASE_DIR, 'images/acbfe.png')):
  ICON_PATH = os.path.join(BASE_DIR, 'images')
# pyinstallyer
elif os.path.isfile(os.path.join(BASE_DIR, 'acbfe/_internal/images/acbfe.png')):
  ICON_PATH = os.path.join(BASE_DIR, 'acbfe/_internal/images')
elif os.path.isfile(os.path.join(os.path.dirname(exec_path), 'images/acbfe.png')):
  ICON_PATH = os.path.join(os.path.dirname(exec_path), 'images')
elif os.path.isfile(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../images/acbfe.png')):
  ICON_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../images')
else: # Try system directories.
  for prefix in ['/usr', '/usr/local', '/usr/X11R6']:
    if os.path.isfile(os.path.join(prefix, 'share/acbfe/images/acbfe.png')):
      ICON_PATH = os.path.join(prefix, 'share/acbfe/images')
      break

GENRES_LIST = ['other', 'adult', 'adventure', 'alternative', 'artbook', 'biography', 'caricature', 'children', 'computer', 'crime', 'education', 'fantasy', 'history', 'horror', 'humor', 'manga', 'military', 'mystery', 'non-fiction', 'politics', 'real_life', 'religion', 'romance', 'science_fiction', 'sports', 'superhero', 'western']
AUTHORS_LIST = ['Writer', 'Adapter', 'Artist', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'CoverArtist', 'Photographer', 'Editor', 'Assistant Editor', 'Translator', 'Other']
LANGUAGES = ['??#', 'aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az', 'ba', 'be', 'bg', 'bh', 'bi', 'bm', 'bn', 'bo', 'br', 'bs', 'ca', 'ce', 'co', 'cr', 'cs', 'cu', 'cv', 'cy', 'da', 'de', 'dv', 'dz', 'ee', 'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'ff', 'fi', 'fj', 'fo', 'fr', 'fy', 'ga', 'gd', 'gl', 'gn', 'gu', 'gv', 'ha', 'he', 'hi', 'ho', 'hr', 'ht', 'hu', 'hy', 'hz', 'ch', 'ia', 'id', 'ie', 'ig', 'ii', 'ik', 'io', 'is', 'it', 'iu', 'ja', 'jv', 'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'km', 'kn', 'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lg', 'li', 'ln', 'lo', 'lt', 'lu', 'lv', 'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'na', 'nb', 'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr', 'nv', 'ny', 'oc', 'oj', 'om', 'or', 'os', 'pa', 'pi', 'pl', 'ps', 'pt', 'qu', 'rm', 'rn', 'ro', 'ru', 'rw', 'sa', 'sc', 'sd', 'se', 'sg', 'si', 'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss', 'st', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tr', 'ts', 'tt', 'tw', 'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'wo', 'xh', 'yi', 'yo', 'za', 'zh', 'zu']

# load fonts
def getFont(font, font_path):
    x = lambda x: font['name'].getDebugName(x)
    if x(16) is None:
      return x(1), font_path, x(2)
    if x(16) is not None:
      return x(16), font_path, x(17)
    else:
      pass

FONTS_LIST = []
default_font = ''
for font_dir in FONTS_DIR:
  for root, dirs, files in os.walk(font_dir):
    for f in files:
      is_duplicate = False
      if f.upper()[-4:] == '.TTF' or f.upper()[-4:] == '.OTF':
        full_font_path = os.path.join(root, f)
        font_tuple = getFont(ttLib.TTFont(full_font_path), full_font_path)
        for font in FONTS_LIST:
          if font_tuple[0] == font[0] and font_tuple[2] == font[2]:
            FONTS_LIST.remove(font)
            FONTS_LIST.append(font_tuple)
            is_duplicate = True
            break
        if not is_duplicate:
          if font_tuple[2] != None:
            FONTS_LIST.append(font_tuple)
          # try to set default font
          if f == 'DejaVuSans-Bold.ttf':
            default_font = os.path.join(root, f)
          elif f == 'Arial_Bold.ttf':
            default_font = os.path.join(root, f)

if default_font == '':
  default_font = FONTS_LIST[0][1]
sorted_list = sorted(FONTS_LIST, key=lambda font_name: font_name[0].upper())

FONTS_LIST = [('Default', default_font, 'Bold')]
for font in sorted_list:
  FONTS_LIST.append(font)

#print("Default font:", default_font)
