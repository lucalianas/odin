import os, sys, argparse, logging
import numpy as np
from PIL import Image

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.deepzoom.deepzoom_wrapper import DeepZoomWrapper
from odin.libs.deepzoom.errors import UnsupportedFormatError, MissingFileError, DZIBadTileAddress
from odin.libs.patches.utils import extract_saturation_mask

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class TilesExtractor(object):

    def __init__(self, slide_path, tile_size, log_level='INFO', log_file=None):
        self.tile_size = tile_size
        if not self.tile_size % 2 == 0:
            raise ValueError('Tile size must be an even number')
        try:
            self.dzi_wrapper = DeepZoomWrapper(slide_path, self.tile_size)
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

    def _get_big_tile(self, zoom_level, column, row):
        big_tile = Image.new('RGB', (self.tile_size*2, self.tile_size*2), (255, 255, 255))
        for x in (column, column+1):
            for y in (row, row+1):
                try:
                    tile = self.dzi_wrapper.get_tile(zoom_level, x, y)
                    big_tile.paste(tile, (
                        x * self.tile_size - column * self.tile_size,
                        y * self.tile_size - row * self.tile_size
                    ))
                except DZIBadTileAddress:
                    self.logger.debug('Unable to load tile %d:%d for level %d', x, y, zoom_level)
        return big_tile

    def _accept_tile(self, tile, max_white_percentage):
        tissue_mask = np.uint8(extract_saturation_mask(tile, 20))
        tissue_percentage = float(tissue_mask.sum()) / np.prod(tissue_mask.shape)
        return (1.0 - tissue_percentage) <= max_white_percentage

    def _get_tile_address(self, x, y, column, row):
        real_x = (column * self.tile_size) + x
        real_y = (row * self.tile_size) + y
        return '%010d_%010d' % (real_x, real_y)

    def _get_tile_fname(self, zoom_level, address):
        return '%s_L%d_%s.jpeg' % (self.slide_label, zoom_level, address)

    def _save_tile(self, tile, tile_fname, out_folder):
        self.logger.debug('Saving file %s', os.path.join(out_folder, tile_fname))
        if tile:
            with open(os.path.join(out_folder, tile_fname), 'w') as out_file:
                tile.save(out_file)

    def _extract_tiles(self, zoom_level, column, row, overlap_step, max_white_percentage, out_folder):
        big_tile = self._get_big_tile(zoom_level, column, row)
        for x in xrange(0, self.tile_size, int(self.tile_size * overlap_step)):
            for y in xrange(0, self.tile_size, int(self.tile_size * overlap_step)):
                # extract a piece from big tile
                tile = big_tile.crop((x, y, x+self.tile_size, y+self.tile_size))
                if self._accept_tile(tile, max_white_percentage):
                    # save tile in tiles_map
                    self.logger.info('Saving tile for address %r' % self._get_tile_address(x, y, column, row))
                    tile_fname = self._get_tile_fname(zoom_level, self._get_tile_address(x, y, column, row))
                    self._save_tile(tile, tile_fname, out_folder)
                else:
                    self.logger.debug('COL %d - ROW %d (x %d - y %d) SKIPPED',
                                      column, row, x, y)

    def run(self, zoom_level, overlap_step, max_white_percentage, out_folder):
        self.logger.info('Starting job')
        target_level = self.dzi_wrapper.get_max_zoom_level() + zoom_level
        tiles_resolution = self.dzi_wrapper.get_level_grid(target_level)
        self.logger.info('Resolution for level %d --- ROWS: %d COLUMNS: %d', target_level,
                         tiles_resolution['rows'], tiles_resolution['columns'])
        try:
            os.mkdir(os.path.join(out_folder, self.slide_label))
        except OSError:
            pass
        finally:
            out_folder = os.path.join(out_folder, self.slide_label)
            self.logger.debug('Saving tile into folder %s', out_folder)
        # adding one extra row and one extra column to cover upper and left borders
        for row in xrange(-1, tiles_resolution['rows']):
            self.logger.debug('Processing row %d', row)
            for col in xrange(-1, tiles_resolution['columns']):
                self.logger.debug('Processing column %d', col)
                self._extract_tiles(target_level, col, row, overlap_step, max_white_percentage, out_folder)
        self.logger.info('Job completed')


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slide', type=str, required=True, help='slide path')
    parser.add_argument('--zoom-level', type=int, required=True,
                        help='zoom level for extraction (as a negative number where 0 is the slide\'s full resolution level)')
    parser.add_argument('--tile-size', type=int, required=True,
                        help='tile size in pixels (only one dimension required, tiles will be squared)')
    parser.add_argument('--overlap-step', type=float, default=0.5,
                        help='the overlap step expressed as a decimal number that will be applied to the tile size')
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
    tiles_extractor.run(args.zoom_level, args.overlap_step, args.max_white, args.out_folder)


if __name__ == '__main__':
    main(sys.argv[1:])
