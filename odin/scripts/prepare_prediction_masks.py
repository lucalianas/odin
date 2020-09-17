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
import pickle

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class PredictionMasksExtractor(object):

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

    def _get_input_folder_map(self, in_folder):
        slide_folders = [f for f in os.listdir(in_folder) if os.path.isdir(os.path.join(in_folder, f))]
        slides_map = dict()
        for s in slide_folders:
            masks_file = os.path.join(in_folder, s, 'binary_predictions.npy')
            patch_names_file = os.path.join(in_folder, s, 'patch_names.pickle')
            if os.path.isfile(masks_file) and os.path.isfile(patch_names_file):
                slides_map[s] = {
                    'masks': masks_file, 'patch_names': patch_names_file
                }
        return slides_map

    def _extract_masks(self, slide, masks_file, patch_names_file, out_folder):
        with open(patch_names_file) as f:
            fnames = pickle.load(f)
        masks = np.load(masks_file)
        for i, f in enumerate(fnames):
            try:
                os.mkdir(os.path.join(out_folder, slide))
            except OSError:
                pass
            out_file = os.path.join(out_folder, slide,
                                    '%s.npz' % f.split('/')[-1].split('.')[0])
            np.savez_compressed(out_file, prediction=np.uint8(masks[i, 0, :, :]))

    def run(self, in_folder, out_folder):
        slides_map = self._get_input_folder_map(in_folder)
        for slide, files in slides_map.iteritems():
            self.logger.info('Processing data for slide %s', slide)
            self._extract_masks(slide, files['masks'], files['patch_names'], out_folder)


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-folder', type=str, required=True,
                        help='input folder containing multiple folders, each one with masks and files description files')
    parser.add_argument('--output-folder', type=str, required=True, help='output folder')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    masks_extractor = PredictionMasksExtractor(args.log_level, args.log_file)
    masks_extractor.run(args.input_folder, args.output_folder)


if __name__ == '__main__':
    main(sys.argv[1:])
