from openslide import OpenSlide
from openslide.deepzoom import DeepZoomGenerator

from cStringIO import StringIO
from PIL import Image

from odin.libs.deepzoom.errors import DZILevelOutOfBounds


class DeepZoomWrapper(object):

    def __init__(self, image_path, tile_size, tile_overlap=0, limit_bounds=True):
        slide = OpenSlide(image_path)
        self.dzi_wrapper = DeepZoomGenerator(slide, tile_size=tile_size, overlap=tile_overlap,
                                             limit_bounds=limit_bounds)
        self.tile_size = tile_size

    def _check_level(self, level):
        if level > self.get_max_zoom_level() or level < 1:
            raise DZILevelOutOfBounds('Level %d not valid (valid range is 1-%d)' % (level, self.get_max_zoom_level()))

    def get_max_zoom_level(self):
        return self.dzi_wrapper.level_count

    def _scale_to_level(self, value, level):
        self._check_level(level)
        scale_factor = float(pow(2, self.get_max_zoom_level() - level))
        return value / scale_factor

    def scale_point_to_level(self, x, y, level):
        self._check_level(level)
        return self._scale_to_level(x, level), self._scale_to_level(y, level)

    def get_level_resolution(self, level):
        self._check_level(level)
        return {
            'width': self.dzi_wrapper.level_dimensions[level-1][0],
            'height': self.dzi_wrapper.level_dimensions[level-1][1]
        }

    def get_slide_original_resolution(self):
        return self.get_level_resolution(self.get_max_zoom_level())

    def get_level_grid(self, level):
        return {
            'columns': self.dzi_wrapper.level_tiles[level-1][0],
            'rows': self.dzi_wrapper.level_tiles[level-1][1]
        }

    def get_slide_original_grid(self):
        return self.get_level_grid(self.get_max_zoom_level())

    # polygon must be a shapely Polygon object
    def get_polygon_grid_bounds(self, polygon_bounds, level):
        self._check_level(level)
        x_min = self._scale_to_level(polygon_bounds['x_min'], level)
        x_max = self._scale_to_level(polygon_bounds['x_max'], level)
        y_min = self._scale_to_level(polygon_bounds['y_min'], level)
        y_max = self._scale_to_level(polygon_bounds['y_max'], level)
        return {
            'x_min': int(x_min / self.tile_size),
            'x_max': int(x_max / self.tile_size),
            'y_min': int(y_min / self.tile_size),
            'y_max': int(y_max / self.tile_size)
        }

    def get_tile_coordinates(self, level, column, row):
        return self.dzi_wrapper.get_tile_coordinates(level-1, (column, row))

    def get_tile_size(self):
        return self.tile_size

    def get_tile(self, level, column, row, format='jpeg', quality=90):
        self._check_level(level)
        tile = self.dzi_wrapper.get_tile(level-1, (column, row))
        tile_buffer = StringIO()
        tile.save(tile_buffer, format=format, quality=quality)
        return Image.open(tile_buffer)

    def get_tile_by_point(self, level, point, format='jpeg', quality=90):
        point_row = int(point[1] / self.tile_size)
        point_column = int(point[0] / self.tile_size)
        return self.get_tile(level, point_column, point_row, format, quality), \
               (point_column, point_row)
