"""utils.py - ACBF utilities module.

Copyright (C) 2011-2018 Robert Kubik
https://github.com/ACBF-Advanced-Comic-Book-Format/ACBF-Editor
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

from pathlib import Path
import subprocess
import plistlib
import pathlib
from PIL import ImageFont
import os
import sys
import logging

logger = logging.getLogger(__name__)


# Taken from Matplot https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/font_manager.py
# OS Font paths
try:
    _HOME = Path.home()
except Exception:  # Exceptions thrown by home() are not specified...
    _HOME = Path(os.devnull)  # Just an arbitrary path with no children.
MSFolders = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
MSFontDirectories = [
    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Fonts",
]
MSUserFontDirectories = [
    str(_HOME / "AppData/Local/Microsoft/Windows/Fonts"),
    str(_HOME / "AppData/Roaming/Microsoft/Windows/Fonts"),
]
X11FontDirectories = [
    # an old standard installation point
    "/usr/X11R6/lib/X11/fonts/TTF/",
    "/usr/X11/lib/X11/fonts",
    # here is the new standard location for fonts
    "/usr/share/fonts/",
    # documented as a good place to install new fonts
    "/usr/local/share/fonts/",
    # common application, not really useful
    "/usr/lib/openoffice/share/fonts/truetype/",
    # user fonts
    str((Path(os.environ.get("XDG_DATA_HOME") or _HOME / ".local/share")) / "fonts"),
    str(_HOME / ".fonts"),
]
OSXFontDirectories = [
    "/Library/Fonts/",
    "/Network/Library/Fonts/",
    "/System/Library/Fonts/",
    # fonts installed via MacPorts
    "/opt/local/share/fonts",
    # user fonts
    str(_HOME / "Library/Fonts"),
]

FONT_STYLES = ["regular", "book", "demi", "italic", "oblique"]
FONT_WEIGHTS = [
    "thin",
    "extralight",
    "light",
    "normal",
    "medium",
    "semibold",
    "bold",
    "extrabold",
    "black",
    "extrablack",
]
FONT_STRETCHES = [
    "normal",
    "semicondensed",
    "condensed",
    "extracondensed",
    "ultracondensed",
    "semi-expanded",
    "expanded",
    "extraexpanded",
    "ultraexpanded",
]


def get_fontext_synonyms(fontext: str) -> list[str]:
    """
    Return a list of file extensions that are synonyms for
    the given file extension *fileext*.
    """
    return {
        "afm": ["afm"],
        "otf": ["otf", "ttc", "ttf"],
        "ttc": ["otf", "ttc", "ttf"],
        "ttf": ["otf", "ttc", "ttf"],
    }[fontext]


def list_fonts(directory: str | Path, extensions: list[str]) -> list[str]:
    """
    Return a list of all fonts matching any of the extensions, found
    recursively under the directory.
    """
    extensions = ["." + ext for ext in extensions]
    return [
        os.path.join(dirpath, filename)
        # os.walk ignores access errors, unlike Path.glob.
        for dirpath, _, filenames in os.walk(directory)
        for filename in filenames
        if Path(filename).suffix.lower() in extensions
    ]


def win32FontDirectory() -> str:
    r"""
    Return the user-specified font directory for Win32.  This is
    looked up from the registry key ::

      \\HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders\Fonts

    If the key is not found, ``%WINDIR%\Fonts`` will be returned.
    """  # noqa: E501
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MSFolders) as user:  # type: ignore[attr-defined]
            return winreg.QueryValueEx(user, "Fonts")[0]  # type: ignore[attr-defined]
    except OSError:
        return os.path.join(os.environ["WINDIR"], "Fonts")


def _get_win32_installed_fonts() -> set[Path]:
    """List the font paths known to the Windows registry."""
    import winreg

    items = set()
    # Search and resolve fonts listed in the registry.
    for domain, base_dirs in [
        (winreg.HKEY_LOCAL_MACHINE, [win32FontDirectory()]),  # type: ignore[attr-defined]  # System.
        (winreg.HKEY_CURRENT_USER, MSUserFontDirectories),  # type: ignore[attr-defined]  # User.
    ]:
        for base_dir in base_dirs:
            for reg_path in MSFontDirectories:
                try:
                    with winreg.OpenKey(domain, reg_path) as local:  # type: ignore[attr-defined]
                        for j in range(winreg.QueryInfoKey(local)[1]):  # type: ignore[attr-defined]
                            # value may contain the filename of the font or its
                            # absolute path.
                            key, value, tp = winreg.EnumValue(local, j)  # type: ignore[attr-defined]
                            if not isinstance(value, str):
                                continue
                            try:
                                # If value contains already an absolute path,
                                # then it is not changed further.
                                path = Path(base_dir, value).resolve()
                            except RuntimeError:
                                # Don't fail with invalid entries.
                                continue
                            items.add(path)
                except (OSError, MemoryError):
                    continue
    return items


def _get_fontconfig_fonts() -> list[Path]:
    """Cache and list the font paths known to ``fc-list``."""
    try:
        if b"--format" not in subprocess.check_output(["fc-list", "--help"]):
            logger.warning(  # fontconfig 2.7 implemented --format.
                "Need fontconfig>=2.7 to query system fonts."
            )
            return []
        out = subprocess.check_output(["fc-list", "--format=%{file}\\n"])
    except (OSError, subprocess.CalledProcessError):
        return []
    return [Path(os.fsdecode(fname)) for fname in out.split(b"\n")]


def _get_macos_fonts() -> list[Path]:
    """Cache and list the font paths known to ``system_profiler SPFontsDataType``."""
    try:
        (d,) = plistlib.loads(subprocess.check_output(["system_profiler", "-xml", "SPFontsDataType"]))
    except (OSError, subprocess.CalledProcessError, plistlib.InvalidFileException):
        return []
    return [Path(entry["path"]) for entry in d["_items"]]


def findSystemFonts(fontpaths: list[str] | None = None, fontext: str = "ttf") -> dict[str, dict[str, str]]:
    """
    Search for fonts in the specified font paths.  If no paths are
    given, will use a standard set of system paths, as well as the
    list of fonts tracked by fontconfig if fontconfig is installed and
    available.  A list of TrueType fonts are returned by default with
    AFM fonts as an option.
    """
    fontfiles: set[str] = set()
    fontexts = get_fontext_synonyms(fontext)

    if fontpaths is None:
        if sys.platform == "win32":
            installed_fonts = _get_win32_installed_fonts()
            fontpaths = []
        else:
            installed_fonts = _get_fontconfig_fonts()
            if sys.platform == "darwin":
                installed_fonts += _get_macos_fonts()
                fontpaths = [*X11FontDirectories, *OSXFontDirectories]
            else:
                fontpaths = X11FontDirectories
        fontfiles.update(str(path) for path in installed_fonts if path.suffix.lower()[1:] in fontexts)

    elif isinstance(fontpaths, str):
        fontpaths = [fontpaths]

    for path in fontpaths:
        fontfiles.update(map(os.path.abspath, list_fonts(path, fontexts)))

    fontpaths_list = [fname for fname in fontfiles if os.path.exists(fname)]

    font_info: dict[str, dict[str, str]] = {}  # filename stem: full path, family name, style, weight, stretch
    for font in fontpaths_list:
        try:
            font_path: pathlib.Path = pathlib.Path(font)
            pil_font = ImageFont.truetype(font_path)
            pil_font_name = pil_font.getname()

            # style and weight and stretch are all in the same font "style" field
            style_split = pil_font_name[1].split(" ")
            style: str = "normal"
            weight: str = "normal"
            stretch: str = "normal"
            for s in style_split:
                if s.casefold() in FONT_STYLES:
                    style = s.casefold()
                elif s.casefold() in FONT_WEIGHTS:
                    weight = s.casefold()
                elif s.casefold() in FONT_STRETCHES:
                    stretch = s.casefold()

            font_info[font_path.stem.casefold()] = {
                "path": str(font_path),
                "name": str(pil_font_name[0]),
                "style": style,
                "weight": weight,
                "stretch": stretch,
            }
        except Exception:
            pass

    return font_info
