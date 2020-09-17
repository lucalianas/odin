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

import os, sys, argparse, logging
import numpy as np
from PIL import Image

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.deepzoom.deepzoom_wrapper import DeepZoomWrapper
from odin.libs.deepzoom.errors import UnsupportedFormatError
from odin.libs.masks_manager.utils import extract_contours
from odin.libs.patches.utils import apply_contours

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class MasksToSlideApplier(object):

    def __init__(self, log_level='INFO', log_file=None):
        self.logger = self._get_logger(log_level, log_file)

    def _get_logger(self, log_level='INFO', log_file=None, mode='a'):
        LOG_FORMAT = '%(asctime)s|%(levelname)-8s|%(message)s'
        LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'

        logger = logging.getLogger('mask_applier')
        if not isinstance(log_level, int):
            try:
                log_level = getattr(logging, log_level)
            except AttributeError:
                raise ValueError('Unsupported literal log level: %s' % log_level)
        logger.setLevel(log_level)
        logger.handlers = []
        if log_file:
            handler = logging.FileHandler(log_file, mode=mode)
        else:
            handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _create_slide_image(self, slide_file, zoom_level, tile_size=256):
        try:
            dzi_wrapper = DeepZoomWrapper(slide_file, tile_size)
        except UnsupportedFormatError:
            sys.exit('File type not supported')
        target_level = dzi_wrapper.get_max_zoom_level() + zoom_level
        img_resolution = dzi_wrapper.get_level_resolution(target_level)
        full_slide_img = Image.new('RGB', (img_resolution['width'], img_resolution['height']))
        tiles_resolution = dzi_wrapper.get_level_grid(target_level)
        for row in xrange(0, tiles_resolution['rows']):
            for col in xrange(0, tiles_resolution['columns']):
                tile = dzi_wrapper.get_tile(target_level, col, row)
                full_slide_img.paste(tile, ((col * tile_size), (row * tile_size)))
        return full_slide_img, img_resolution

    def _reshape_mask(self, mask, mask_origin, slide_resolution):
        upper_right = mask_origin[1] + mask.shape[0]
        lower_left = mask_origin[0] + mask.shape[1]
        if upper_right > slide_resolution[0]:
            max_x = upper_right - slide_resolution[0]
        else:
            max_x = mask.shape[0]
        if lower_left > slide_resolution[1]:
            max_y = lower_left - slide_resolution[1]
        else:
            max_y = mask.shape[1]
        return mask[0:max_x, 0:max_y]

    def _create_full_mask(self, slide_resolution, masks_folder):
        full_mask = np.zeros((slide_resolution['height'], slide_resolution['width']), dtype=np.uint8)
        for f in os.listdir(masks_folder):
            mask = np.load(os.path.join(masks_folder, f))['prediction']
            _, _, row, col = f.split('.')[0].split('_')
            # is it always a square?
            mask_size = mask.shape[0]
            origin_x = int(row) * mask_size
            origin_y = int(col) * mask_size
            mask = self._reshape_mask(mask, (origin_x, origin_y),
                                      (slide_resolution['width'], slide_resolution['height']))
            full_mask[origin_x:origin_x+mask.shape[0], origin_y:origin_y+mask.shape[1]] = mask
        return full_mask

    def run(self, slide_label, zoom_level, slides_folder, masks_folder, out_folder, contours_color,
            contours_thickness):
        self.logger.info('Starting job')
        slide_file = os.path.join(slides_folder, '%s.mrxs' % slide_label)
        masks_folder = os.path.join(masks_folder, slide_label)
        if os.path.isfile(slide_file) and os.path.isdir(masks_folder):
            # TODO: add tile_size to arguments
            self.logger.info('Reconstructing slide %s for zoom level %d', slide_label, zoom_level)
            slide_img, slide_resolution = self._create_slide_image(slide_file, zoom_level)
            self.logger.info('Reconstruction completed')
            self.logger.info('Building full prediction mask')
            full_mask = self._create_full_mask(slide_resolution, masks_folder)
            self.logger.info('Prediction mask created')
            self.logger.info('Applying contours to full slide')
            contours = extract_contours(full_mask)
            slide_img = Image.fromarray(apply_contours(slide_img, contours, contours_color, contours_thickness))
            slide_img.save(os.path.join(out_folder, '%s.jpeg' % slide_label))
            self.logger.info('Slide saved as file %s', os.path.join(out_folder, '%s.jpeg' % slide_label))
            self.logger.info('Job completed')
        else:
            if not os.path.isfile(slide_file):
                sys.exit('There is no file %s' % slide_file)
            if not os.path.isdir(masks_folder):
                sys.exit('There is no folder %s' % masks_folder)


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slide-label', type=str, required=True, help='')
    parser.add_argument('--zoom-level', type=int, required=True, help='')
    parser.add_argument('--slides-folder', type=str, required=True, help='')
    parser.add_argument('--masks-folder', type=str, required=True, help='')
    parser.add_argument('--output-folder', type=str, required=True, help='')
    parser.add_argument('--contours-color', nargs='+', type=int, default=[0, 0, 255], help='')
    parser.add_argument('--contours-thickness', type=int, default=2, help='')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    masks_applier = MasksToSlideApplier(args.log_level, args.log_file)
    masks_applier.run(args.slide_label, args.zoom_level, args.slides_folder, args.masks_folder,
                      args.output_folder, args.contours_color, args.contours_thickness)


if __name__ == '__main__':
    main(sys.argv[1:])
