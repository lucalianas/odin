import os, sys, argparse, logging
import numpy as np

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.deepzoom.deepzoom_wrapper import DeepZoomWrapper
from odin.libs.deepzoom.errors import UnsupportedFormatError, MissingFileError
from odin.libs.patches.utils import extract_white_mask

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class TilesExtractor(object):

    def __init__(self, slide_path, tile_size, log_level='INFO', log_file=None):
        try:
            self.dzi_wrapper = DeepZoomWrapper(slide_path, tile_size)
        except MissingFileError:
            sys.exit('%s is not a valid file' % slide_path)
        except UnsupportedFormatError:
            sys.exit('file type not supported')
        self.slide_label = self._get_slide_label(slide_path)
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

    def _accept_tile(self, tile, max_white_percentage):
        white_mask = extract_white_mask(tile, 230)
        white_percentage = white_mask.sum() / np.prod(white_mask.shape)
        return white_percentage <= max_white_percentage

    def _get_tile(self, zoom_level, column, row, max_white_percentage):
        tile = self.dzi_wrapper.get_tile(zoom_level, column, row)
        if self._accept_tile(tile, max_white_percentage):
            return tile
        else:
            return None

    def _get_tile_fname(self, zoom_level, column, row):
        return '%s_L%d_%d_%d.jpeg' % (self.slide_label, zoom_level, row, column)

    def _save_tile(self, tile, tile_fname, out_folder):
        if tile:
            with open(os.path.join(out_folder, tile_fname), 'w') as out_file:
                tile.save(out_file)

    def run(self, zoom_level, max_white_percentage, out_folder):
        self.logger.info('Starting job')
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
        for row in xrange(0, tiles_resolution['rows']):
            self.logger.debug('Processing row %d', row)
            for col in xrange(0, tiles_resolution['columns']):
                self.logger.debug('Processing column %d', col)
                tile = self._get_tile(target_level, col, row, max_white_percentage)
                if tile:
                    tfname = self._get_tile_fname(zoom_level, col, row)
                    self._save_tile(tile, tfname, out_folder)
                else:
                    self.logger.debug('Ignoring tile %d_%d, too much white' % (row, col))
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
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    tiles_extractor = TilesExtractor(args.slide, args.tile_size, args.log_level, args.log_file)
    tiles_extractor.run(args.zoom_level, args.max_white, args.out_folder)


if __name__ == '__main__':
    main(sys.argv[1:])
