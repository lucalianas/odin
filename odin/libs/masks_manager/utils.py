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
