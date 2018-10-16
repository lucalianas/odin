import os, sys, argparse, logging, cv2
import numpy as np
from PIL import Image

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.masks_manager import utils as mask_utils
from odin.libs.patches.utils import apply_mask, apply_contours

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class PredictionMaskApplier(object):

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

    def _build_patches_map(self, masks_dir, patches_dir):
        masks = os.listdir(masks_dir)
        self.logger.info('Loaded %d masks', len(masks))
        patches = os.listdir(patches_dir)
        self.logger.info('Loaded %d patches', len(patches))

        patches_map = dict()
        for m in masks:
            uuid = m.split('.')[0]
            if '%s.jpeg' % uuid in patches:
                patches_map[uuid] = {
                    'mask_file': os.path.join(masks_dir, m),
                    'patch_file': os.path.join(patches_dir, '%s.jpeg' % uuid)
                }
        self.logger.info('Mapped %d patches to mask' % len(patches_map))
        return patches_map

    def _load_patch(self, patch_path):
        return cv2.imread(patch_path)

    def _cv2_img_to_pil(self, patch_img):
        return Image.fromarray(patch_img)

    def _load_mask(self, mask_path, mask_label):
        return np.load(mask_path)[mask_label]

    def _apply_mask(self, patch_img, mask, color, alpha):
        patch_img = apply_mask(patch_img, mask, color, alpha)
        return patch_img

    def _apply_contours(self, patch_img, mask, color, thickness):
        contours = mask_utils.extract_contours(mask)
        patch_img = apply_contours(patch_img, contours, color, thickness)
        return patch_img

    def _save_patch(self, uuid, patch, output_dir):
        patch.save(os.path.join(output_dir, '%s.jpeg' % uuid))

    def run(self, masks_dir, patches_dir, output_dir, no_fill, fill_color, fill_alpha,
            no_contours, contours_color, contours_thickness):
        self.logger.info('Staring job')
        patches_map = self._build_patches_map(masks_dir, patches_dir)
        for k, v in patches_map.iteritems():
            self.logger.info('Processing patch %s', k)
            # using OpenCV image
            img = self._load_patch(v['patch_file'])
            mask = self._load_mask(v['mask_file'], 'prediction')
            if not no_contours:
                img = self._apply_contours(img, mask, contours_color, contours_thickness)
            # using PIL image
            img = self._cv2_img_to_pil(img)
            if not no_fill:
                img = self._apply_mask(img, mask, fill_color, fill_alpha)
            self._save_patch(k, img, output_dir)
        self.logger.info('Job completed')


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--masks-dir', type=str, required=True, help='Folder containing the .npz masks')
    parser.add_argument('--patches-dir', type=str, required=True, help='Folder containing the .jpeg patches')
    parser.add_argument('--output-dir', type=str, required=True, help='output folder')
    parser.add_argument('--no-fill', action='store_true', required=False, help='don\'t fill the mask')
    parser.add_argument('--fill-color', type=int, nargs='+', default=[0, 255, 0],
                        help='mask color as a RGB triplet (i.e. 0 255 0 for green)')
    parser.add_argument('--fill-alpha', type=float, default=0.3, help='value of alpha channel of the mask')
    parser.add_argument('--no-contours', action='store_true', required=False, help='don\'t print mask contours')
    parser.add_argument('--contours-color', type=int, nargs='+', default=[85, 107, 47],
                        help='mask contours color as a RGB triplet (i.e. 255 0 0  for red)')
    parser.add_argument('--contours-thickness', type=int, default=2, help='mask contours thickness')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    if args.no_fill and args.no_contours:
        sys.exit('Nothing to do, exit')
    prediction_mask_applier = PredictionMaskApplier()
    prediction_mask_applier.run(args.masks_dir, args.patches_dir, args.output_dir, args.no_fill, tuple(args.fill_color),
                                args.fill_alpha, args.no_contours, args.contours_color, args.contours_thickness)


if __name__ == '__main__':
    main(sys.argv[1:])
