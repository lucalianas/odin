import os, sys, argparse, logging
import numpy as np
from PIL import Image

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.deepzoom.deepzoom_wrapper import DeepZoomWrapper
from odin.libs.deepzoom.errors import UnsupportedFormatError, MissingFileError, DZIBadTileAddress
from odin.libs.patches.utils import extract_white_mask

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class TilesExtractor(object):

    def __init__(self, slide_path, tile_size, log_level='INFO', log_file=None):
        self.tile_size = tile_size
        if not self.tile_size % 2 == 0:
            raise ValueError('Tile size must be an even number')
        try:
            self.dzi_extractor_wrapper = DeepZoomWrapper(slide_path, self.tile_size/2)
            self.dzi_description_wrapper = DeepZoomWrapper(slide_path, self.tile_size)
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

    def _get_reduced_tile(self, zoom_level, column, row):
        try:
            return self.dzi_extractor_wrapper.get_tile(zoom_level, column, row)
        except DZIBadTileAddress:
            return None

    def _get_reduced_tiles(self, zoom_level, column, row):
        return {
            'upper_left': self._get_reduced_tile(zoom_level, column-1, row-1),
            'upper_right': self._get_reduced_tile(zoom_level, column, row-1),
            'lower_left': self._get_reduced_tile(zoom_level, column-1, row),
            'lower_right': self._get_reduced_tile(zoom_level, column, row)
        }

    def _combine_reduced_tiles(self, reduced_tiles):
        background_img = Image.new('RGB', (self.tile_size, self.tile_size), (255, 255, 255))
        if reduced_tiles['upper_left']:
            background_img.paste(reduced_tiles['upper_left'], (0, 0))
        if reduced_tiles['upper_right']:
            background_img.paste(reduced_tiles['upper_right'], (self.tile_size/2, 0))
        if reduced_tiles['lower_left']:
            background_img.paste(reduced_tiles['lower_left'], (0, self.tile_size/2))
        if reduced_tiles['lower_right']:
            background_img.paste(reduced_tiles['lower_right'], (self.tile_size/2, self.tile_size/2))
        return background_img

    def _accept_tile(self, tile, max_white_percentage):
        white_mask = extract_white_mask(tile, 230)
        white_percentage = white_mask.sum() / np.prod(white_mask.shape)
        return white_percentage <= max_white_percentage

    def _get_tiles(self, zoom_level, column, row, max_white_percentage):
        tiles_map = dict()
        for x in (column*2, (column*2)+1):
            for y in (row*2, (row*2)+1):
                tmp_tile = self._combine_reduced_tiles(self._get_reduced_tiles(zoom_level, x, y))
                if self._accept_tile(tmp_tile, max_white_percentage):
                    tiles_map['%.1f_%.1f' % (y/2., x/2.)] = tmp_tile
        return tiles_map

    def _get_tile_fname(self, zoom_level, address):
        return '%s_L%d_%s.jpeg' % (self.slide_label, zoom_level, address)

    def _save_tile(self, tile, tile_fname, out_folder):
        if tile:
            with open(os.path.join(out_folder, tile_fname), 'w') as out_file:
                tile.save(out_file)

    def run(self, zoom_level, max_white_percentage, out_folder):
        self.logger.info('Starting job')
        target_level = self.dzi_description_wrapper.get_max_zoom_level() + zoom_level
        tiles_resolution = self.dzi_description_wrapper.get_level_grid(target_level)
        self.logger.info('Resolution for level %d --- ROWS: %d COLUMNS: %d', target_level,
                         tiles_resolution['rows'], tiles_resolution['columns'])
        try:
            os.mkdir(os.path.join(out_folder, self.slide_label))
        except OSError:
            pass
        finally:
            out_folder = os.path.join(out_folder, self.slide_label)
            self.logger.debug('Saving tile into folder %s', out_folder)
        # adding one extra row and one extra column to cover lower and right borders
        for row in xrange(0, tiles_resolution['rows']+1):
            self.logger.debug('Processing row %d', row)
            for col in xrange(0, tiles_resolution['columns']+1):
                self.logger.debug('Processing column %d', col)
                tiles = self._get_tiles(target_level, col, row, max_white_percentage)
                for address, tile in tiles.iteritems():
                    tfname = self._get_tile_fname(zoom_level, address)
                    self._save_tile(tile, tfname, out_folder)
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
