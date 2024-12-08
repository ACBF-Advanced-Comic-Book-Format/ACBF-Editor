"""detection.py - ACBF detection module

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

import numpy
import cv2

from typing import Any


def text_bubble_detection(image_full_path: str, x: float, y: float) -> list[tuple[Any, float] | tuple[Any, Any]]:
    """
    Detect a single text bubble under the mouse cursor location
    """
    x = int(x)
    y = int(y)

    rgb = cv2.imread(image_full_path)

    imgray = cv2.GaussianBlur(rgb, (5, 5), 0)
    imgray = cv2.cvtColor(imgray, cv2.COLOR_BGR2GRAY)
    imgray = cv2.copyMakeBorder(imgray, 6, 6, 6, 6, cv2.BORDER_CONSTANT, 0)
    height, width = imgray.shape[:2]
    border = int(float(min(height, width)) * 0.008)
    if border < 2:
        border = 2

    # get point color and range
    px: int = int(imgray[y + 6, x + 6])
    low_color = numpy.array(max(0, px - 30), dtype=numpy.uint8)
    high_color = numpy.array(min(255, px + 30), dtype=numpy.uint8)

    # threshold image on selected color
    thresholded: numpy.ndarray[Any, numpy.dtype] | numpy.ndarray = cv2.inRange(imgray, low_color, high_color)

    # floodfil with gray
    mask: numpy.ndarray[Any, numpy.dtype] | numpy.float_ = numpy.zeros((height + 2, width + 2), numpy.uint8)
    cv2.floodFill(thresholded, mask, (x + 7, y + 7), 100)
    mask = cv2.inRange(thresholded, 99, 101)

    # carve out the bubble first
    min_x: int | numpy.ndarray[Any, numpy.dtype[numpy.signedinteger | int]] = 0
    min_y: int | float = 0
    max_x: int | numpy.ndarray[Any, numpy.dtype[numpy.signedinteger | int]] = 0
    max_y: int | float = 0
    for idx, line in enumerate(mask):
        if cv2.countNonZero(line) > 0:  # If the line has non-zero elements
            nonzero_indices = numpy.nonzero(line)[0]  # Get all non-zero indices in the line
            if min_x == 0 or min_x > nonzero_indices[0]:
                min_x = nonzero_indices[0]
            if max_x == 0 or max_x < nonzero_indices[-1]:
                max_x = nonzero_indices[-1]
            if min_y == 0:  # The first non-empty row
                min_y = idx
            max_y = idx  # Update the last non-empty row

    # Adjust slicing indices with boundary checks
    min_y = max(0, min_y - 1)
    max_y = min(mask.shape[0] - 1, max_y + 1)
    min_x = max(0, min_x - 1)
    max_x = min(mask.shape[1] - 1, max_x + 2)

    # Slice the mask
    mask = mask[min_y:max_y, min_x:max_x]  # type: ignore
    hi, wi = mask.shape

    # check if it's rectangle
    check = numpy.copy(mask)
    mask = text_bubble_fill_inside(check, 0.08)

    if (numpy.count_nonzero(check) / float(check.size)) > 0.9:
        is_rectangle = True
    else:
        is_rectangle = False

    # rotate and remove short lines (bubble tail)
    for angle in (0, 1):
        if is_rectangle:
            mask = rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
            mask = rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
        else:
            mask = text_bubble_cut_tails(mask, 0.15)
            mask = rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
            mask = text_bubble_cut_tails(mask, 0.15)
            mask = rotate_image(mask, 45 * numpy.pi / 180, 100, 100)
    rhi, rwi = mask.shape
    mask = mask[
        int((rhi - hi) / 2) - 10 : int((rhi - hi) / 2) + hi + 10,
        int((rwi - wi) / 2) - 10 : int((rwi - wi) / 2) + wi + 10,
    ]
    # remove text
    mask = text_bubble_fill_inside(mask, 0.08)
    mask = numpy.rot90(mask, 1)
    mask = text_bubble_fill_inside(mask, 0.08)
    mask = numpy.rot90(mask, 1)

    # check if top/bottom is straight line
    if numpy.count_nonzero(mask[11]) / float(mask[11].size) > 0.5:
        is_cut_at_top = True
    else:
        is_cut_at_top = False

    if numpy.count_nonzero(mask[-12]) / float(mask[-12].size) > 0.5:
        is_cut_at_bottom = True
    else:
        is_cut_at_bottom = False

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (border, border))
    mask = cv2.erode(mask, kernel, iterations=1)

    # edges
    mask = cv2.Canny(mask, 10, 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(border / 2), int(border / 2)))
    mask = cv2.dilate(mask, kernel, iterations=1)

    # find contours
    i = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    try:
        contours, _ = i[1], i[2]
    except Exception:
        contours, _ = i[0], i[1]

    if len(contours) == 0:
        return []

    contours_sorted = sorted(contours, key=lambda c: cv2.contourArea(c), reverse=True)
    arc_len = cv2.arcLength(contours_sorted[0], True)
    approx = cv2.approxPolyDP(contours_sorted[0], 0.003 * arc_len, True)
    points = []

    # move due to mask and image border added earlier + bubble carve out
    for point in approx.tolist():
        x = point[0][0] - 6 + min_x - 11
        y = point[0][1] - 6 + min_y - 10
        points.append((x, y))

    # cut top and bottom of the bubble (helps text-fitting algorithm)
    cut_by = 1 + round(height * 0.001, 0)
    min_y = min(points, key=lambda item: item[1])[1]
    max_y = max(points, key=lambda item: item[1])[1]
    new_points = []
    points_on_line_upper = []
    points_on_line_lower = []
    for point in points:
        if is_rectangle:
            if point[1] < min_y + (cut_by * 0.5):
                new_points.append((point[0], min_y + int(cut_by * 0.5)))
                points_on_line_upper.append((point[0], min_y + int(cut_by * 0.5)))
            elif point[1] > (max_y - (cut_by * 0.3)):
                new_points.append((point[0], max_y - int(cut_by * 0.3)))
                points_on_line_lower.append((point[0], max_y - int(cut_by * 0.3)))
            else:
                new_points.append((point[0], point[1]))
        elif is_cut_at_top:
            if point[1] < min_y + (cut_by * 0.1):
                new_points.append((point[0], min_y + int(cut_by * 0.1)))
                points_on_line_upper.append((point[0], min_y + int(cut_by * 0.1)))
            elif point[1] > (max_y - (cut_by * 0.7)):
                new_points.append((point[0], max_y - int(cut_by * 0.7)))
                points_on_line_lower.append((point[0], max_y - int(cut_by * 0.7)))
            else:
                new_points.append((point[0], point[1]))
        elif is_cut_at_bottom:
            if point[1] < min_y + (cut_by * 1):
                new_points.append((point[0], min_y + int(cut_by * 1)))
                points_on_line_upper.append((point[0], min_y + int(cut_by * 1)))
            elif point[1] > (max_y - (cut_by * 0.1)):
                new_points.append((point[0], max_y - int(cut_by * 0.1)))
                points_on_line_lower.append((point[0], max_y - int(cut_by * 0.1)))
            else:
                new_points.append((point[0], point[1]))
        else:
            if point[1] < min_y + (cut_by * 1):
                new_points.append((point[0], min_y + int(cut_by * 1)))
                points_on_line_upper.append((point[0], min_y + int(cut_by * 1)))
            elif point[1] > (max_y - (cut_by * 0.7)):
                new_points.append((point[0], max_y - int(cut_by * 0.7)))
                points_on_line_lower.append((point[0], max_y - int(cut_by * 0.7)))
            else:
                new_points.append((point[0], point[1]))

    # remove points on the same line
    try:
        points_on_line_upper_max_x = max(points_on_line_upper, key=lambda x: x[0])
        points_on_line_upper_min_x = min(points_on_line_upper, key=lambda x: x[0])
        points_on_line_lower_max_x = max(points_on_line_lower, key=lambda x: x[0])
        points_on_line_lower_min_x = min(points_on_line_lower, key=lambda x: x[0])

        points = []
        for point in new_points:
            if point in (
                points_on_line_upper_max_x,
                points_on_line_upper_min_x,
                points_on_line_lower_max_x,
                points_on_line_lower_min_x,
            ):
                points.append(point)
            elif point not in points_on_line_upper and point not in points_on_line_lower:
                points.append(point)
    except Exception:
        points = new_points

    return points


def text_bubble_cut_tails(mask: numpy.ndarray[Any, numpy.dtype], narrow_by: float) -> numpy.ndarray[Any, numpy.dtype]:
    zero_these = {}
    for idx, line in enumerate(mask):
        if cv2.countNonZero(line) > 0:
            zero_these[idx] = (numpy.nonzero(line)[0][0], numpy.nonzero(line)[0][-1], len(numpy.nonzero(line)[0]))

    values = list(zero_these.values())
    keys = list(zero_these.keys())
    keys.sort()
    bubble_width = max(values, key=lambda item: item[2])[2]

    for idx, line in enumerate(mask):
        if idx in zero_these and zero_these[idx][2] < bubble_width * narrow_by:  # remove narrow lines
            mask[idx] = 0

    return mask


def text_bubble_fill_inside(mask: numpy.ndarray[Any, numpy.dtype], narrow_by: float) -> numpy.ndarray[Any, numpy.dtype]:
    zero_these = {}
    for idx, line in enumerate(mask):
        if cv2.countNonZero(line) > 0:
            zero_these[idx] = (numpy.nonzero(line)[0][0], numpy.nonzero(line)[0][-1], len(numpy.nonzero(line)[0]))

    keys = list(zero_these.keys())
    keys.sort()

    for idx, line in enumerate(mask):
        if idx in zero_these:  # remove inside holes
            mask[idx][zero_these[idx][0] : zero_these[idx][1]] = 255

    return mask


def rotate_coords(x: list[int], y: list[int], theta: float, ox: int, oy: int) -> tuple[numpy.ndarray, numpy.ndarray]:
    """Rotate arrays of coordinates x and y by theta radians about the
    point (ox, oy)."""
    s, c = numpy.sin(theta), numpy.cos(theta)
    x, y = numpy.asarray(x) - ox, numpy.asarray(y) - oy
    return x * c - y * s + ox, x * s + y * c + oy


def rotate_image(
    src: numpy.ndarray,
    theta: float,
    ox: int,
    oy: int,
    fill: int = 0,
) -> numpy.ndarray[Any, numpy.dtype[numpy.floating[numpy._64Bit] | numpy.float_]]:
    """Rotate the image src by theta radians about (ox, oy).
    Pixels in the result that don't correspond to pixels in src are
    replaced by the value fill."""

    # Images have origin at the top left, so negate the angle.
    theta = -theta

    # Dimensions of source image. Note that scipy.misc.imread loads
    # images in row-major order, so src.shape gives (height, width).
    sh, sw = src.shape

    # Rotated positions of the corners of the source image.
    cx, cy = rotate_coords([0, sw, sw, 0], [0, 0, sh, sh], theta, ox, oy)

    # Determine dimensions of destination image.
    dw, dh = (int(numpy.ceil(numpy.max(c) - numpy.min(c))) for c in (cx, cy))

    # Coordinates of pixels in destination image.
    dx, dy = numpy.meshgrid(numpy.arange(dw), numpy.arange(dh))

    # Corresponding coordinates in source image. Since we are
    # transforming dest-to-src here, the rotation is negated.
    sx, sy = rotate_coords(dx + numpy.min(cx), dy + numpy.min(cy), -theta, ox, oy)

    # Select nearest neighbour.
    sx, sy = sx.round().astype(int), sy.round().astype(int)

    # Mask for valid coordinates.
    mask = (0 <= sx) & (sx < sw) & (0 <= sy) & (sy < sh)

    # Create destination image.
    dest = numpy.empty(shape=(dh, dw), dtype=src.dtype)

    # Copy valid coordinates from source image.
    dest[dy[mask], dx[mask]] = src[sy[mask], sx[mask]]

    # Fill invalid coordinates.
    dest[dy[~mask], dx[~mask]] = fill

    return dest
