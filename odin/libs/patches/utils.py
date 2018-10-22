#  Copyright (c) 2019, CRS4
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of
#  this software and associated documentation files (the "Software"), to deal in
#  the Software without restriction, including without limitation the rights to
#  use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
#  the Software, and to permit persons to whom the Software is furnished to do so,
#  subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
#  FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
#  IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
#  CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import numpy as np
import cv2
from PIL.Image import Image

from odin.libs.masks_manager.utils import binary_mask_to_rgb, binary_mask_to_rgba


def extract_white_mask(patch_img, lower_bound):
    cv2_img = cv2.cvtColor(np.array(patch_img), cv2.COLOR_RGB2BGR)
    white_mask = cv2.inRange(cv2_img, np.array([lower_bound, lower_bound, lower_bound], dtype=np.uint8),
                             np.array([255, 255, 255], dtype=np.uint8))
    return white_mask / 255


def extract_saturation_mask(patch_img, min_saturation):
    cv2_patch = np.array(patch_img)
    img_width, img_height, _ = cv2_patch.shape
    filter_mask = np.zeros((img_width, img_height), dtype=np.bool)
    hsv_image = cv2.cvtColor(cv2_patch, cv2.COLOR_BGR2HSV)
    for x in xrange(0, img_width):
        for y in xrange(0, img_height):
            if hsv_image[x, y, 1] >= min_saturation:
                filter_mask[x, y] = 1
    return filter_mask


def apply_mask(patch_img, mask, mask_color, mask_alpha=None):
    patch_copy = patch_img.copy()
    if mask_alpha is None:
        mask_img = binary_mask_to_rgb(mask, *mask_color)
    else:
        mask_img = binary_mask_to_rgba(mask, *mask_color, alpha=mask_alpha)
    patch_copy.paste(mask_img, (0, 0), mask_img)
    return patch_copy


def apply_contours(patch_img, contours, color, thickness):
    if type(patch_img) == Image:
        patch_img = np.array(patch_img)
    patch_copy = patch_img.copy()
    return cv2.drawContours(patch_copy, contours, -1, color, thickness)
