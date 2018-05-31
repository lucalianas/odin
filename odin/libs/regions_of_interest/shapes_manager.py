try:
    import simplejson as json
except ImportError:
    import json

from random import randint
from requests import codes as rc
from shapely.geometry import Polygon, Point
from shapely.affinity import scale
import numpy as np
import cv2


class Shape(object):

    def __init__(self, roi_segments):
        self.polygon = Polygon([(seg['point']['x'], seg['point']['y']) for seg in roi_segments])

    def get_bounds(self):
        bounds = self.polygon.bounds
        return {
            'x_min': bounds[0],
            'y_min': bounds[1],
            'x_max': bounds[2],
            'y_max': bounds[3]
        }

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
        points = set()
        while len(points) < points_count:
            points.add(self.get_random_point())
        return points

    def _box_to_polygon(self, box):
        return Polygon([box['down_left'], box['down_right'], box['up_right'], box['up_left']])

    def _rescale_polygon(self, scale_level):
        scaling = pow(2, scale_level)
        return scale(self.polygon, xfact=scaling, yfact=scaling, origin=(0, 0))

    # def get_intersection_mask(self, box, scale_level=0):
    #     if scale_level < 0:
    #         polygon = self._rescale_polygon(scale_level)
    #     else:
    #         polygon = self.polygon
    #     box_polygon = self._box_to_polygon(box)
    #     box_height = int(box['down_left'][1] - box['up_left'][1])
    #     box_width = int(box['down_right'][0] - box['down_left'][0])
    #     if not polygon.intersects(box_polygon):
    #         return np.zeros((box_width, box_height), dtype=np.uint8)
    #     else:
    #         if polygon.contains(box_polygon):
    #             return np.ones((box_width, box_height), dtype=np.uint8)
    #         else:
    #             mask = np.zeros((box_width, box_height), dtype=np.uint8)
    #             for x in xrange(int(box['up_left'][0]), int(box['up_right'][0])):
    #                 for y in xrange(int(box['up_left'][1]), int(box['down_right'][1])):
    #                     if polygon.contains(Point(x, y)):
    #                         mask[y % int(box['up_left'][1])][x % int(box['up_left'][0])] = 1
    #             return mask

    def get_intersection_mask(self, box, scale_level=0):
        if scale_level < 0:
            polygon = self._rescale_polygon(scale_level)
        else:
            polygon = self.polygon
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
                intersection = polygon.intersection(box_polygon).exterior.coords[:]
                intersection = [(int(x - box['up_left'][0]), int(y - box['up_left'][1])) for x, y in intersection]
                cv2.fillPoly(mask, np.array([intersection,]), 1)
                return mask

    def get_difference_mask(self, box, scale_level=0):
        return 1 - self.get_intersection_mask(box, scale_level)


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
            return Shape(roi_segments)
        else:
            return None

    def get_slice(self, slide_id, roi_id):
        return self._get_roi(slide_id, 'slice', roi_id)

    def get_core(self, slide_id, roi_id):
        return self._get_roi(slide_id, 'core', roi_id)

    def get_focus_region(self, slide_id, roi_id):
        return self._get_roi(slide_id, 'focus_region', roi_id)
