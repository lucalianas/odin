import numpy as np
from PIL import Image


def binary_mask_to_rgb(mask, red, green, blue):
    width, height = mask.shape
    rgba_mask = np.empty((width, height, 4), dtype=np.uint8)
    rgba_mask[:, :, :] = mask[:, :, np.newaxis]
    return Image.fromarray(np.uint8(rgba_mask * [red, green, blue]), mode='RGB')


def binary_mask_to_rgba(mask, red, green, blue, alpha=0.5):
    width, height = mask.shape
    rgba_mask = np.empty((width, height, 4), dtype=np.uint8)
    rgba_mask[:, :, :] = mask[:, :, np.newaxis]
    return Image.fromarray(np.uint8(rgba_mask * [red, green, blue, alpha*255]), mode='RGBA')
