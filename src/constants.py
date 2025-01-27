"""constants.py - Miscellaneous constants.

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

import os
import sys
import utils

import portability


VERSION = "1.18"
HOME_DIR = portability.get_home_directory()
CONFIG_DIR = portability.get_config_directory()
DATA_DIR = portability.get_data_directory()
FONTS_DIR = portability.get_fonts_directory()
PLATFORM = portability.get_platform()

exec_path = os.path.abspath(sys.argv[0])
BASE_DIR = os.path.dirname(os.path.dirname(exec_path))

# set icons directory
if os.path.isfile(os.path.join(BASE_DIR, "images/acbfe.png")):
    ICON_PATH = os.path.join(BASE_DIR, "images")
elif os.path.isfile(os.path.join(os.path.dirname(exec_path), "images/acbfe.png")):
    ICON_PATH = os.path.join(os.path.dirname(exec_path), "images")
else:  # Try system directories.
    for prefix in ["/usr", "/usr/local", "/usr/X11R6"]:
        if os.path.isfile(os.path.join(prefix, "share/acbfe/images/acbfe.png")):
            ICON_PATH = os.path.join(prefix, "share/acbfe/images")
            break

GENRES_LIST = [
    "other",
    "adult",
    "adventure",
    "alternative",
    "artbook",
    "biography",
    "caricature",
    "children",
    "computer",
    "crime",
    "education",
    "fantasy",
    "history",
    "horror",
    "humor",
    "manga",
    "military",
    "mystery",
    "non-fiction",
    "politics",
    "real_life",
    "religion",
    "romance",
    "science_fiction",
    "sports",
    "superhero",
    "western",
]
AUTHORS_LIST = [
    "Writer",
    "Adapter",
    "Artist",
    "Penciller",
    "Inker",
    "Colorist",
    "Letterer",
    "CoverArtist",
    "Photographer",
    "Editor",
    "Assistant Editor",
    "Translator",
    "Other",
]
LANGUAGES = [
    "??#",
    "aa",
    "ab",
    "ae",
    "af",
    "ak",
    "am",
    "an",
    "ar",
    "as",
    "av",
    "ay",
    "az",
    "ba",
    "be",
    "bg",
    "bh",
    "bi",
    "bm",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "ce",
    "co",
    "cr",
    "cs",
    "cu",
    "cv",
    "cy",
    "da",
    "de",
    "dv",
    "dz",
    "ee",
    "el",
    "en",
    "eo",
    "es",
    "et",
    "eu",
    "fa",
    "ff",
    "fi",
    "fj",
    "fo",
    "fr",
    "fy",
    "ga",
    "gd",
    "gl",
    "gn",
    "gu",
    "gv",
    "ha",
    "he",
    "hi",
    "ho",
    "hr",
    "ht",
    "hu",
    "hy",
    "hz",
    "ch",
    "ia",
    "id",
    "ie",
    "ig",
    "ii",
    "ik",
    "io",
    "is",
    "it",
    "iu",
    "ja",
    "jv",
    "ka",
    "kg",
    "ki",
    "kj",
    "kk",
    "kl",
    "km",
    "kn",
    "ko",
    "kr",
    "ks",
    "ku",
    "kv",
    "kw",
    "ky",
    "la",
    "lb",
    "lg",
    "li",
    "ln",
    "lo",
    "lt",
    "lu",
    "lv",
    "mg",
    "mh",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "na",
    "nb",
    "nd",
    "ne",
    "ng",
    "nl",
    "nn",
    "no",
    "nr",
    "nv",
    "ny",
    "oc",
    "oj",
    "om",
    "or",
    "os",
    "pa",
    "pi",
    "pl",
    "ps",
    "pt",
    "qu",
    "rm",
    "rn",
    "ro",
    "ru",
    "rw",
    "sa",
    "sc",
    "sd",
    "se",
    "sg",
    "si",
    "sk",
    "sl",
    "sm",
    "sn",
    "so",
    "sq",
    "sr",
    "ss",
    "st",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "ti",
    "tk",
    "tl",
    "tn",
    "to",
    "tr",
    "ts",
    "tt",
    "tw",
    "ty",
    "ug",
    "uk",
    "ur",
    "uz",
    "ve",
    "vi",
    "vo",
    "wa",
    "wo",
    "xh",
    "yi",
    "yo",
    "za",
    "zh",
    "zu",
]

# Create system font list
SYSTEM_FONT_LIST: dict[str, dict[str, str]] = (
    utils.findSystemFonts()
)  # filename stem: full path, family name, style, weight, stretch
default_font = ""
if SYSTEM_FONT_LIST.get("arial"):
    default_font = SYSTEM_FONT_LIST.get("arial", {})["path"]
elif SYSTEM_FONT_LIST.get("dejavusans"):
    default_font = SYSTEM_FONT_LIST.get("dejavusans", {})["path"]
