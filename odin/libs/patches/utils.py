import numpy as np
import cv2


def extract_white_mask(patch_img, lower_bound):
    cv2_img = cv2.cvtColor(np.array(patch_img), cv2.COLOR_RGB2BGR)
    white_mask = cv2.inRange(cv2_img, np.array([lower_bound, lower_bound, lower_bound], dtype=np.uint8),
                             np.array([255, 255, 255], dtype=np.uint8))
    return white_mask / 255
