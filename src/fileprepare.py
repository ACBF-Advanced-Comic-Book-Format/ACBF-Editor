"""fileprepare.py - unzip and prepare file.

Copyright (C) 2011-2018 Robert Kubik
https://launchpad.net/~just-me
"""

from __future__ import annotations

import logging
import os
import shutil
import zipfile

import lxml.etree as xml
import patoolib
import preferences
from gi.repository import Gtk
from PIL import Image
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

logger = logging.getLogger(__name__)


class FilePrepare:
    def __init__(self, window: Gtk.Window, filename: str, tempdir: str, show_dialog: bool):
        self._window = window
        self.filename: str = filename
        file_type = None
        self.preferences = preferences.Preferences()

        if zipfile.is_zipfile(filename):
            file_type = "ZIP"
        elif filename[-3:].upper() == "CBR":
            file_type = "RAR"

        if file_type is not None:
            # show progress bar
            progress_dialog = Gtk.Window()
            # progress_dialog.set_transient_for(window)
            progress_dialog.set_title("Loading Comic Book ...")

            progress_bar = Gtk.ProgressBar()
            # progress_bar.set_size_request(-1, 13 * self._window._window.ui_scale_factor)
            progress_dialog.set_child(progress_bar)
            # progress_title = Gtk.Label()
            # progress_title.set_markup('Loading file ...')
            # progress_dialog.set_child(progress_title)
            if show_dialog:
                progress_dialog.show()

            """while Gtk.events_pending():
                Gtk.main_iteration()"""

            # clear temp directory
            for root, dirs, files in os.walk(tempdir):
                for f in files:
                    os.unlink(os.path.join(root, f))
                for d in dirs:
                    shutil.rmtree(os.path.join(root, d))

            # extract files from CBZ into DATA_DIR
            if file_type == "ZIP":
                z = zipfile.ZipFile(filename)
                for idx, f in enumerate(z.namelist()):
                    fraction = float(idx) / len(z.namelist())
                    z.extract(f, tempdir)
                    progress_bar.set_fraction(fraction)
            else:
                logger.info("running patool ...")
                progress_bar.set_fraction(0.5)
                try:
                    patoolib.extract_archive(filename, outdir=tempdir)
                except Exception as inst:
                    message = Gtk.AlertDialog()
                    message.set_message("Extract command failed: %s" % inst)
                    self.filename = ""
                    message.show()
                    return

            # check if there's ACBF file inside
            acbf_found: bool = False
            for datafile in os.listdir(tempdir):
                if datafile[-4:] == "acbf":
                    acbf_found = True
                    return_filename = os.path.join(tempdir, datafile)

            if not acbf_found:
                # create dummy acbf file
                tree = xml.Element(
                    "ACBF",
                    xmlns="http://www.fictionbook-lib.org/xml/acbf/1.2",
                )
                metadata = xml.SubElement(tree, "meta-data")
                bookinfo = xml.SubElement(metadata, "book-info")
                coverpage = xml.SubElement(bookinfo, "coverpage")
                cover_image = ""
                all_files = []
                files_to_elements: dict[str, xml.Element] = {}
                publishinfo = xml.SubElement(metadata, "publish-info")
                xml.SubElement(metadata, "document-info")
                body = xml.SubElement(tree, "body")

                if os.path.isfile(os.path.join(tempdir, "comic.xml")):
                    is_acv_file = True
                else:
                    is_acv_file = False

                for root, dirs, files in os.walk(tempdir):
                    for f in files:
                        all_files.append(
                            os.path.join(root, f)[len(tempdir) + 1 :],
                        )
                for datafile in sorted(all_files):
                    if datafile[-4:].upper() in (
                        ".JPG",
                        ".PNG",
                        ".GIF",
                        "WEBP",
                        ".BMP",
                        "JPEG",
                    ):
                        if cover_image == "":
                            # insert coverpage
                            cover_image = xml.SubElement(
                                coverpage,
                                "image",
                                href=datafile,
                            )
                            files_to_elements[
                                os.path.basename(
                                    datafile,
                                )[:-4]
                            ] = cover_image
                        else:
                            # insert normal page
                            if is_acv_file and "/" not in datafile:
                                page = xml.SubElement(body, "page")
                                image = xml.SubElement(
                                    page,
                                    "image",
                                    href=datafile,
                                )
                                files_to_elements[os.path.basename(datafile)[:-4]] = image
                            elif not is_acv_file:
                                page = xml.SubElement(body, "page")
                                image = xml.SubElement(
                                    page,
                                    "image",
                                    href=datafile,
                                )

                # check for ACV's comic.xml
                if is_acv_file:
                    acv_tree = xml.parse(
                        source=os.path.join(tempdir, "comic.xml"),
                    )

                    if acv_tree.getroot().get("bgcolor") is not None:
                        body.set("bgcolor", acv_tree.getroot().get("bgcolor"))

                    if acv_tree.getroot().get("title") is not None:
                        book_title = xml.SubElement(bookinfo, "book-title")
                        book_title.text = acv_tree.getroot().get("title")

                    images = acv_tree.find("images")
                    pattern_length = len(images.get("indexPattern"))
                    pattern_format = images.get("namePattern").replace(
                        "@index",
                        "%%0%dd" % pattern_length,
                    )
                    for screen in acv_tree.findall("screen"):
                        element = files_to_elements[
                            pattern_format
                            % int(
                                screen.get("index"),
                            )
                        ]
                        xsize, ysize = Image.open(
                            os.path.join(
                                tempdir,
                                element.get("href"),
                            ),
                        ).size
                        for frame in screen:
                            x1, y1, w, h = list(
                                map(float, frame.get("relativeArea").split(" ")),
                            )
                            ix1 = int(xsize * x1)
                            ix2 = int(xsize * (x1 + w))
                            iy1 = int(ysize * y1)
                            iy2 = int(ysize * (y1 + h))
                            envelope = "%d,%d %d,%d %d,%d %d,%d" % (
                                ix1,
                                iy1,
                                ix2,
                                iy1,
                                ix2,
                                iy2,
                                ix1,
                                iy2,
                            )
                            frame_elt = xml.SubElement(
                                element.getparent(),
                                "frame",
                                points=envelope,
                            )
                            if frame.get("bgcolor") is not None:
                                frame_elt.set("bgcolor", frame.get("bgcolor"))

                # check if there's ComicInfo.xml file inside
                # TODO This should be an option
                elif os.path.isfile(os.path.join(tempdir, "ComicInfo.xml")):
                    # load comic book information from ComicInfo.xml
                    comicinfo_tree = xml.parse(
                        source=os.path.join(tempdir, "ComicInfo.xml"),
                    )

                    for author in [
                        "Writer",
                        "Penciller",
                        "Inker",
                        "Colorist",
                        "CoverArtist",
                        "Adapter",
                        "Letterer",
                    ]:
                        if comicinfo_tree.find(author) is not None:
                            author_element = xml.SubElement(
                                bookinfo,
                                "author",
                                activity=author,
                            )
                            first_name = xml.SubElement(
                                author_element,
                                "first-name",
                            )
                            first_name.text = comicinfo_tree.find(
                                author,
                            ).text.split(" ")[0]
                            if len(comicinfo_tree.find(author).text.split(" ")) > 2:
                                middle_name = xml.SubElement(
                                    author_element,
                                    "middle-name",
                                )
                                middle_name.text = ""
                                for i in range(len(comicinfo_tree.find(author).text.split(" "))):
                                    if i > 0 and i < (len(comicinfo_tree.find(author).text.split(" ")) - 1):
                                        middle_name.text = (
                                            middle_name.text
                                            + " "
                                            + comicinfo_tree.find(
                                                author,
                                            ).text.split(" ")[i]
                                        )
                            last_name = xml.SubElement(
                                author_element,
                                "last-name",
                            )
                            last_name.text = comicinfo_tree.find(
                                author,
                            ).text.split(" ")[-1]

                    if comicinfo_tree.find("Title") is not None:
                        book_title = xml.SubElement(bookinfo, "book-title")
                        book_title.text = comicinfo_tree.find("Title").text

                    if comicinfo_tree.find("Genre") is not None:
                        for one_genre in comicinfo_tree.find("Genre").text.split(", "):
                            genre = xml.SubElement(bookinfo, "genre")
                            genre.text = one_genre

                    if comicinfo_tree.find("Characters") is not None:
                        characters = xml.SubElement(bookinfo, "characters")
                        for character in comicinfo_tree.find("Characters").text.split(", "):
                            name = xml.SubElement(characters, "name")
                            name.text = character

                    if comicinfo_tree.find("Series") is not None:
                        sequence = xml.SubElement(
                            bookinfo,
                            "sequence",
                            title=comicinfo_tree.find("Series").text,
                        )
                        if comicinfo_tree.find("Number") is not None:
                            sequence.text = comicinfo_tree.find("Number").text
                        else:
                            sequence.text = "0"

                    if comicinfo_tree.find("Summary") is not None:
                        annotation = xml.SubElement(bookinfo, "annotation")
                        for text_line in comicinfo_tree.find("Summary").text.split("\n"):
                            if text_line != "":
                                paragraph = xml.SubElement(annotation, "p")
                                paragraph.text = text_line

                    if comicinfo_tree.find("LanguageISO") is not None:
                        languages = xml.SubElement(bookinfo, "languages")
                        xml.SubElement(
                            languages,
                            "text-layer",
                            lang=comicinfo_tree.find("LanguageISO").text,
                            show="False",
                        )

                    if (
                        comicinfo_tree.find("Year") is not None
                        and comicinfo_tree.find("Month") is not None
                        and comicinfo_tree.find("Day") is not None
                    ):
                        publish_date = (
                            comicinfo_tree.find("Year").text
                            + "-"
                            + comicinfo_tree.find("Month").text
                            + "-"
                            + comicinfo_tree.find("Day").text
                        )
                        publish_date = xml.SubElement(
                            publishinfo,
                            "publish-date",
                            value=publish_date,
                        )
                        publish_date.text = comicinfo_tree.find("Year").text

                    if comicinfo_tree.find("Publisher") is not None:
                        publisher = xml.SubElement(publishinfo, "publisher")
                        publisher.text = comicinfo_tree.find("Publisher").text

                # save generated acbf file
                progress_bar.set_fraction(1)
                return_filename = os.path.join(
                    tempdir,
                    os.path.splitext(
                        os.path.basename(filename),
                    )[0]
                    + ".acbf",
                )
                with open(return_filename, "w") as file:
                    # f = open(return_filename, 'w')
                    file.write(
                        xml.tostring(
                            tree,
                            encoding="Unicode",
                            pretty_print=True,
                        ),
                    )
                    # f.close()

            self.filename = return_filename
            progress_dialog.close()
        # else:
        # filename remains the same
