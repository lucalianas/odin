import numpy as np
import cv2

from odin.libs.masks_manager.utils import binary_mask_to_rgb, binary_mask_to_rgba


def extract_white_mask(patch_img, lower_bound):
    cv2_img = cv2.cvtColor(np.array(patch_img), cv2.COLOR_RGB2BGR)
    white_mask = cv2.inRange(cv2_img, np.array([lower_bound, lower_bound, lower_bound], dtype=np.uint8),
                             np.array([255, 255, 255], dtype=np.uint8))
    return white_mask / 255


def apply_mask(patch_img, mask, mask_color, mask_alpha=None):
    patch_copy = patch_img.copy()
    if mask_alpha is None:
        mask_img = binary_mask_to_rgb(mask, *mask_color)
    else:
        mask_img = binary_mask_to_rgba(mask, *mask_color, alpha=mask_alpha)
    patch_copy.paste(mask_img, (0, 0), mask_img)
    return patch_copy


def apply_contours(patch_img, contours, color, thickness):
    patch_copy = patch_img.copy()
    return cv2.drawContours(patch_copy, contours, -1, color, thickness)
