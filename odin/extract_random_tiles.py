try:
    import simplejson as json
except ImportError:
    import json

from openslide import OpenSlide
from openslide.deepzoom import DeepZoomGenerator

import os, requests
from uuid import  uuid4
from random import sample
from urlparse import urljoin
from cStringIO import StringIO
from PIL import Image
from shapely.geometry import Polygon

from promort_generic_tool import ProMortTool


class DiskImageReader(object):

    def __init__(self, image_path, tile_size, tile_overlap, logger):
        self.image_path = image_path
        self.tile_size = tile_size
        self.tile_overlap = tile_overlap
        self.slide = self._get_slide_wrapper(image_path)
        self.logger = logger

    def _get_slide_wrapper(self, image_path):
        slide = OpenSlide(image_path)
        return DeepZoomGenerator(slide, tile_size=self.tile_size,
                                 overlap=self.tile_overlap, limit_bounds=True)

    def get_max_zoom_level(self):
        return self.slide.level_count - 1

    def get_slide_dimensions(self):
        return {
            'width': self.slide.level_dimensions[-1][0],
            'height': self.slide.level_dimensions[-1][1]
        }

    def get_slide_grid_infos(self):
        slide_dimensions = self.get_slide_dimensions()
        columns = (slide_dimensions['width'] / self.tile_size) + bool(slide_dimensions['width'] % self.tile_size)
        rows = (slide_dimensions['height'] / self.tile_size) + bool(slide_dimensions['height'] % self.tile_size)
        return {
            'columns': columns,
            'rows': rows
        }

    def get_roi_bounds(self, roi_path):
        roi_polygon = Polygon(roi_path)
        x_min, y_min, x_max, y_max = roi_polygon.bounds
        return {
            'x_min': int(x_min / self.tile_size),
            'x_max': int(x_max / self.tile_size),
            'y_min': int(y_min / self.tile_size),
            'y_max': int(y_max / self.tile_size)
        }

    def _tile_to_points(self, tile):
        x_min = tile[0] * self.tile_size
        x_max = x_min + self.tile_size
        y_min = tile[1] * self.tile_size
        y_max = y_min + self.tile_size
        return [(x_min, y_min), (x_min, y_max), (x_max, y_max), (x_max, y_min)]

    def _check_tile_inclusion(self, roi_path, tile):
        roi_polygon = Polygon(roi_path)
        tile_polygon = Polygon(self._tile_to_points(tile))
        return roi_polygon.contains(tile_polygon)

    def filter_tiles(self, roi_path, tiles_list):
        return set((tile for tile in tiles_list if self._check_tile_inclusion(roi_path, tile)))

    def get_tile(self, level, column, row):
        tile = self.slide.get_tile(level, (column, row))
        tile_buffer = StringIO()
        tile.save(tile_buffer, format='jpeg', quality=90)
        return Image.open(tile_buffer)


class RandomTilesExtractor(ProMortTool):

    def __init__(self, host, user, passwd, logger):
        super(RandomTilesExtractor, self).__init__(host, user, passwd, logger)

    def _check_slide_file(self, images_folder, slide_id):
        return os.path.exists(os.path.join(images_folder, '%s.mrxs' % slide_id))

    def _check_output_folder(self, path):
        return os.path.exists(path) and os.path.isdir(path)

    def _get_roi_path(self, slide_id, roi_id, roi_type):
        # the second 's' character related to the 'roi_type' parameter is needed because the URL required
        # the plural form of the ROI type (slices, cores, focus_regions)
        url = urljoin(self.promort_host, 'api/odin/rois/%s/%ss/%s/' % (slide_id, roi_type, roi_id))
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            roi_segments = json.loads(response.json()['roi_json'])['segments']
            return [(seg['point']['x'], seg['point']['y']) for seg in roi_segments]
        else:
            self.logger.error(response.status_code)
            return None

    def _get_tiles_list(self, roi_bounds):
        tiles = set()
        for col in xrange(roi_bounds['x_min'], roi_bounds['x_max'] + 1):
            for row in xrange(roi_bounds['y_min'], roi_bounds['y_max'] + 1):
                tiles.add((col, row))
        return tiles

    def _save_tile(self, slide_id, output_folder, tile_img):
        if not os.path.exists(os.path.join(output_folder, slide_id)):
            os.makedirs(os.path.join(output_folder, slide_id))
        tile_uuid = uuid4().hex
        with open(os.path.join(output_folder, slide_id, '%s.jpeg' % tile_uuid), 'w') as ofile:
            tile_img.save(ofile)
        return tile_uuid


    def run(self, images_folder, slide_id, roi_id, roi_type, tile_size, tiles_count, output_folder):
        self._login()
        perm_ok = self._check_odin_permissions()
        file_exists = self._check_slide_file(images_folder, slide_id)
        out_folder_exists = self._check_output_folder(output_folder)
        if perm_ok and file_exists and out_folder_exists:
            # right now force tile overlap to 0
            # TODO: add to argument parser tiles-overlap parameter
            slide_reader = DiskImageReader(os.path.join(images_folder, '%s.mrxs' % slide_id),
                                           tile_size, 1, self.logger)
            roi_path = self._get_roi_path(slide_id, roi_id, roi_type)
            roi_bounds = slide_reader.get_roi_bounds(roi_path)
            tiles_list = self._get_tiles_list(roi_bounds)
            tiles_list = slide_reader.filter_tiles(roi_path, tiles_list)
            max_zoom_level = slide_reader.get_max_zoom_level()
            # avoid "sample larger than population" error
            if len(tiles_list) < tiles_count:
                tiles_count = len(tiles_list)
            for tile in sample(tiles_list, tiles_count):
                self.logger.info('--- LOADING TILE %d::%d (zoom: %d) ---', tile[0], tile[1], max_zoom_level)
                img = slide_reader.get_tile(max_zoom_level, tile[0], tile[1])
                tile_uuid = self._save_tile(slide_id, output_folder, img)
        else:
            if not file_exists:
                self.logger.critcal('File %s/%s.mrxs does not exist', images_folder, slide_id)
            if not out_folder_exists:
                self.logger.critical('Output folder %s does not exist', output_folder)
        self._logout()


help_doc = """
add doc
"""


def make_parser(parser):
    parser.add_argument('--images-folder', type=str, required=True,
                        help='folder containing the files of the digital slides')
    parser.add_argument('--slide-id', type=str, required=True, help='ID of the digital slide')
    parser.add_argument('--roi-id', type=str, required=True,
                        help='ID of the ROI used to extract random tiles')
    parser.add_argument('--roi-type', type=str, choices=['slice', 'core', 'focus_region'], required=True,
                        help='the type of the ROI that will be extracted from the slide')
    parser.add_argument('--tile-size', type=int, default=256, help='size of the extracted tiles')
    parser.add_argument('--tiles-count', type=int, required=True,
                        help='the number of tiles that will be retrieved')
    parser.add_argument('--output-folder', type=str, required=True,
                        help='output folder for random tiles extracted by given ROI and slide')


def implementation(host, user, passwd, logger, args):
    tiles_extractor = RandomTilesExtractor(host, user, passwd, logger)
    tiles_extractor.run(args.images_folder, args.slide_id, args.roi_id, args.roi_type,
                        args.tile_size, args.tiles_count, args.output_folder)


def register(registration_list):
    registration_list.append(('extract_random_tiles', help_doc, make_parser, implementation))
