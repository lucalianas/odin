import os, sys, argparse, logging
import numpy as np
from PIL import Image

sys.path.append('../../')

from odin.libs.masks_manager import utils as mask_utils
from odin.libs.patches.utils import apply_mask

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class PredictionMaskApplier(object):

    def __init__(self, log_level='INFO', log_file=None):
        self.logger = self.get_logger(log_level, log_file)

    def get_logger(self, log_level='INFO', log_file=None, mode='a'):
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
        self.logger.info('Mapeed %d patches to mask' % len(patches_map))
        return patches_map

    def _apply_mask(self, uuid, patch, mask, output_dir, mask_color, mask_alpha=0.5):
        patch_img = Image.open(patch)
        mask_np = np.load(mask)
        patch_img = apply_mask(patch_img, mask_np['prediction'],
                               mask_color, mask_alpha)
        patch_img.save(os.path.join(output_dir, '%s.jpeg' % uuid))

    def run(self, masks_dir, patches_dir, output_dir, mask_color, mask_alpha):
        self.logger.info('Staring job')
        patches_map = self._build_patches_map(masks_dir, patches_dir)
        for k, v in patches_map.iteritems():
            self.logger.info('Processing patch %s', k)
            self._apply_mask(k, v['patch_file'], v['mask_file'], output_dir,
                             mask_color, mask_alpha)
        self.logger.info('Job completed')


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--masks-dir', type=str, required=True, help='Folder containing the .npz masks')
    parser.add_argument('--patches-dir', type=str, required=True, help='Folder containing the .jpeg patches')
    parser.add_argument('--output-dir', type=str, required=True, help='output folder')
    parser.add_argument('--mask-color', type=int, nargs='+', default=[255, 0, 0],
                        help='mask color as a RGB triplet (i.e. 0 255 0 for green)')
    parser.add_argument('--mask-alpha', type=float, default=0.3, help='value of alpha channel of the mask')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    prediction_mask_applier = PredictionMaskApplier()
    prediction_mask_applier.run(args.masks_dir, args.patches_dir, args.output_dir, tuple(args.mask_color),
                                args.mask_alpha)


if __name__ == '__main__':
    main(sys.argv[1:])
