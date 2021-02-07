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
from multiprocessing import Pool, cpu_count

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.deepzoom.deepzoom_wrapper import DeepZoomWrapper
from odin.libs.deepzoom.errors import UnsupportedFormatError, MissingFileError
from odin.libs.patches.utils import extract_white_mask

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


def extract_row_tiles(dzi_wrapper, slide_label, tile_size, row, col, zoom_level, max_white, out_folder):
    return TilesExtractor.process_row(dzi_wrapper, slide_label, tile_size, row, col, zoom_level, max_white,
                                      out_folder)


class TilesExtractor(object):

    def __init__(self, slide_path, tile_size, log_level='INFO', log_file=None):
        self.slide_path = slide_path
        self.tile_size = tile_size
        try:
            self.dzi_wrapper = DeepZoomWrapper(self.slide_path, self.tile_size)
        except MissingFileError:
            sys.exit('%s is not a valid file' % self.slide_path)
        except UnsupportedFormatError:
            sys.exit('file type not supported')
        self.slide_label = self._get_slide_label(self.slide_path)
        self.logger = self._get_logger(log_level, log_file)

    def _get_slide_label(self, slide_path):
        slide_fname = slide_path.split('/')[-1]
        return slide_fname.split('.')[0]

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

    @staticmethod
    def process_row(slide_path, slide_label, tile_size, row, columns, zoom_level, max_white_percentage,
                    out_folder):
        dzi_wrapper = DeepZoomWrapper(slide_path, tile_size)
        for col in xrange(0, columns):
            tile = TilesExtractor._get_tile(dzi_wrapper, tile_size,
                                            zoom_level, col, row, max_white_percentage)
            if tile:
                tfname = TilesExtractor._get_tile_fname(slide_label, zoom_level, col, row)
                TilesExtractor._save_tile(tile, tfname, out_folder)
        return row

    @staticmethod
    def _get_tile(dzi_wrapper, tile_size, zoom_level, column, row, max_white_percentage):
        tile = dzi_wrapper.get_tile(zoom_level, column, row)
        tile = TilesExtractor._complete_tile(tile, tile_size)
        if max_white_percentage == 100:
            return tile
        else:
            if TilesExtractor._accept_tile(tile, max_white_percentage):
                return tile
            else:
                return None

    @staticmethod
    def _complete_tile(tile, tile_size):
        white_img = Image.new('RGB', (tile_size, tile_size), (255, 255, 255))
        white_img.paste(tile, (0, 0))
        return white_img

    @staticmethod
    def _accept_tile(tile, max_white_percentage):
        white_mask = extract_white_mask(tile, 230)
        white_percentage = white_mask.sum() / np.prod(white_mask.shape)
        return white_percentage <= max_white_percentage

    @staticmethod
    def _get_tile_fname(slide_label, zoom_level, column, row):
        return '%s_L%d_%d_%d.jpeg' % (slide_label, zoom_level, row, column)

    @staticmethod
    def _save_tile(tile, tile_fname, out_folder):
        if tile:
            with open(os.path.join(out_folder, tile_fname), 'w') as out_file:
                tile.save(out_file)

    def run(self, zoom_level, max_white_percentage, out_folder, max_processes):
        self.logger.info('Starting job with %d parallel processes', max_processes)
        target_level = self.dzi_wrapper.get_max_zoom_level() + zoom_level
        tiles_resolution = self.dzi_wrapper.get_level_grid(target_level)
        self.logger.info('Resolution for level %d --- ROWS: %d COLUMNS: %d', target_level,
                         tiles_resolution['rows'], tiles_resolution['columns'])
        # prepare output path
        try:
            os.mkdir(os.path.join(out_folder, self.slide_label))
        except OSError:
            pass
        finally:
            out_folder = os.path.join(out_folder, self.slide_label)
            self.logger.debug('Saving tile into folder %s', out_folder)
        runners_pool = Pool(processes=max_processes)
        results = [runners_pool.apply_async(extract_row_tiles, (self.slide_path, self.slide_label, self.tile_size, row,
                                                                tiles_resolution['columns'], target_level,
                                                                max_white_percentage,
                                                                out_folder)) for row in
                   xrange(0, tiles_resolution['rows'])]
        for p in results:
            self.logger.debug('Row %d processed' % p.get())
        self.logger.info('Job completed')


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slide', type=str, required=True, help='slide path')
    parser.add_argument('--zoom-level', type=int, required=True,
                        help='zoom level for extraction (as a negative number where 0 is the slide\'s full resolution level)')
    parser.add_argument('--tile-size', type=int, required=True,
                        help='tile size in pixels (only one dimension required, tiles will be squared)')
    parser.add_argument('--out-folder', type=str, required=True, help='output folder for tiles')
    parser.add_argument('--max-white', type=float, default=0.9,
                        help='max percentage of white acceptable for a tile to be valid')
    parser.add_argument('--max-processes', type=int,
                        help='maximum number of allowed parallel processes, if not specified all available CPUs will be used')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def get_max_processes(user_max_processes):
    max_cpus = cpu_count()
    if not user_max_processes:
        return max_cpus
    else:
        return min(user_max_processes, max_cpus)


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    max_processes = get_max_processes(args.max_processes)
    tiles_extractor = TilesExtractor(args.slide, args.tile_size, args.log_level, args.log_file)
    tiles_extractor.run(args.zoom_level, args.max_white, args.out_folder, max_processes)


if __name__ == '__main__':
    main(sys.argv[1:])
