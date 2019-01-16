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
from PIL import Image


def binary_mask_to_rgb(mask, red, green, blue):
    width, height = mask.shape
    rgba_mask = np.empty((width, height, 3), dtype=np.uint8)
    rgba_mask[:, :, :] = mask[:, :, np.newaxis]
    return Image.fromarray(np.uint8(rgba_mask * [red, green, blue]), mode='RGB')


def binary_mask_to_rgba(mask, red, green, blue, alpha=0.5):
    width, height = mask.shape
    rgba_mask = np.empty((width, height, 4), dtype=np.uint8)
    rgba_mask[:, :, :] = mask[:, :, np.newaxis]
    return Image.fromarray(np.uint8(rgba_mask * [red, green, blue, alpha*255]), mode='RGBA')


def add_mask(mask_1, mask_2):
    result = np.logical_or(mask_1, mask_2)
    return np.uint8(result)


def remove_mask(mask_1, mask_2):
    result = np.logical_and(mask_1, np.logical_not(mask_2))
    return np.uint8(result)


def extract_contours(mask):
    _, contours, _ = cv2.findContours(mask, mode=cv2.RETR_EXTERNAL,
                                      method=cv2.CHAIN_APPROX_SIMPLE)
    return contours
