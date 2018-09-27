try:
    import simplejson as json
except ImportError:
    import json

from errors import InvalidPolygonError

from random import randint
from requests import codes as rc
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.affinity import scale
import numpy as np
import cv2


class Shape(object):

    def __init__(self, segments):
        self.polygon = Polygon(segments)

    def get_bounds(self):
        bounds = self.polygon.bounds
        try:
            return {
                'x_min': bounds[0],
                'y_min': bounds[1],
                'x_max': bounds[2],
                'y_max': bounds[3]
            }
        except IndexError:
            raise InvalidPolygonError()

    def get_random_point(self):
        bounds = self.get_bounds()
        point = Point(
            randint(int(bounds['x_min']), int(bounds['x_max'])),
            randint(int(bounds['y_min']), int(bounds['y_max']))
        )
        while not self.polygon.contains(point):
            point = Point(
                randint(int(bounds['x_min']), int(bounds['x_max'])),
                randint(int(bounds['y_min']), int(bounds['y_max']))
            )
        return point

    def get_random_points(self, points_count):
        points = [self.get_random_point() for _ in xrange(points_count)]
        return points

    def _box_to_polygon(self, box):
        return Polygon([box['down_left'], box['down_right'], box['up_right'], box['up_left']])

    def _rescale_polygon(self, scale_level):
        scaling = pow(2, scale_level)
        return scale(self.polygon, xfact=scaling, yfact=scaling, origin=(0, 0))

    def get_intersection_mask(self, box, scale_level=0, tolerance=0):
        if scale_level < 0:
            polygon = self._rescale_polygon(scale_level)
        else:
            polygon = self.polygon
        if tolerance > 0:
            polygon = polygon.simplify(tolerance, preserve_topology=False)
        box_polygon = self._box_to_polygon(box)
        box_height = int(box['down_left'][1] - box['up_left'][1])
        box_width = int(box['down_right'][0] - box['down_left'][0])
        if not polygon.intersects(box_polygon):
            return np.zeros((box_width, box_height), dtype=np.uint8)
        else:
            if polygon.contains(box_polygon):
                return np.ones((box_width, box_height), dtype=np.uint8)
            else:
                mask = np.zeros((box_width, box_height), dtype=np.uint8)
                intersection = polygon.intersection(box_polygon)
                if type(intersection) is MultiPolygon:
                    intersection_paths = list(intersection)
                else:
                    intersection_paths = [intersection]
                for path in intersection_paths:
                    ipath = path.exterior.coords[:]
                    ipath = [(int(x - box['up_left'][0]), int(y - box['up_left'][1])) for x, y in ipath]
                    cv2.fillPoly(mask, np.array([ipath,]), 1)
                return mask

    def get_full_mask(self, scale_level=0, tolerance=0):
        if scale_level < 0:
            polygon = self._rescale_polygon(scale_level)
            scale_factor = pow(2, scale_level)
        else:
            polygon = self.polygon
            scale_factor = 1
        if tolerance > 0:
            polygon = polygon.simplify(tolerance, preserve_topology=False)
        bounds = self.get_bounds()
        box_height = int((bounds['y_max']-bounds['y_min'])*scale_factor)
        box_width = int((bounds['x_max']-bounds['x_min'])*scale_factor)
        mask = np.zeros((box_height, box_width), dtype=np.uint8)
        polygon_path = polygon.exterior.coords[:]
        polygon_path = [(int(x - bounds['x_min']*scale_factor),
                         int(y - bounds['y_min']*scale_factor)) for x, y in polygon_path]
        cv2.fillPoly(mask, np.array([polygon_path,]), 1)
        return mask

    def get_difference_mask(self, box, scale_level=0, tolerance=0):
        return 1 - self.get_intersection_mask(box, scale_level, tolerance)


class ShapesManager(object):

    def __init__(self, promort_client):
        self.promort_client = promort_client

    def _get_roi(self, slide_id, roi_type, roi_id):
        # the second 's' character related to the 'roi_type' parameter is needed because the URL required
        # the plural form of the ROI type (slices, cores, focus_regions)
        url = 'api/odin/rois/%s/%ss/%s/' % (slide_id, roi_type, roi_id)
        response = self.promort_client.get(url)
        if response.status_code == rc.OK:
            roi_segments = json.loads(response.json()['roi_json'])['segments']
            return Shape([(seg['point']['x'], seg['point']['y']) for seg in roi_segments])
        else:
            return None

    def get_slice(self, slide_id, roi_id):
        return self._get_roi(slide_id, 'slice', roi_id)

    def get_core(self, slide_id, roi_id):
        return self._get_roi(slide_id, 'core', roi_id)

    def get_focus_region(self, slide_id, roi_id):
        return self._get_roi(slide_id, 'focus_region', roi_id)
