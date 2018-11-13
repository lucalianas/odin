import os, sys, argparse, logging
from PIL import Image

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class SlideBuilder(object):

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

    def _get_tile_dimensions(self, tile_file):
        img = Image.open(tile_file)
        return img.width, img.height

    def _get_pixel_coordinates(self, column, row, width, height):
        return column * width, row * height

    def _get_tiles_map(self, tiles_folder):
        tiles_list = os.listdir(tiles_folder)
        tile_width, tile_height = self._get_tile_dimensions(os.path.join(tiles_folder, tiles_list[0]))
        tiles_map = dict()
        for t in tiles_list:
            _, _, row, col = t.split('.')[0].split('_')
            tiles_map[self._get_pixel_coordinates(int(col), int(row), tile_width, tile_height)] =\
                os.path.join(tiles_folder, t)
        return tiles_map

    def _get_output_image_size(self, tiles_coordinates, tile_width, tile_height):
        img_width = max([k[0] for k in tiles_coordinates])
        img_height = max([k[1] for k in tiles_coordinates])
        return img_width+tile_width, img_height+tile_height

    def _prepare_slide(self, slide_width, slide_height, background=(255, 255, 255)):
        return Image.new('RGB', (slide_width, slide_height), background)

    def _build_slide(self, slide_img, tiles_map, output_file):
        for coordinates, tile in tiles_map.iteritems():
            tile_img = Image.open(tile)
            slide_img.paste(tile_img, coordinates)
        slide_img.save(output_file)

    def run(self, tiles_folder, output_file):
        tiles = self._get_tiles_map(tiles_folder)
        tw, th = self._get_tile_dimensions(tiles.values()[0])
        slide_img = self._prepare_slide(*self._get_output_image_size(tiles.keys(), tw, th))
        self._build_slide(slide_img, tiles, output_file)


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tiles-folder', type=str, required=True,
                        help='the folder containing the tiles that will be merged')
    parser.add_argument('--output-file', type=str, required=True, help='output file')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    slide_builder = SlideBuilder(args.log_level, args.log_file)
    slide_builder.run(args.tiles_folder, args.output_file)


if __name__ == '__main__':
    main(sys.argv[1:])
