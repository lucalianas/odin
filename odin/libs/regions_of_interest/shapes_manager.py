try:
    import simplejson as json
except ImportError:
    import json

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

    def get_coordinates(self, scale_level=0):
        if scale_level != 0:
            polygon = self._rescale_polygon(scale_level)
        else:
            polygon = self.polygon
        return list(polygon.exterior.coords)

    def get_area(self, scale_level=0):
        if scale_level != 0:
            polygon = self._rescale_polygon(scale_level)
        else:
            polygon = self.polygon
        return polygon.area

    def get_length(self, scale_level=0):
        if scale_level != 0:
            polygon = self._rescale_polygon(scale_level)
        else:
            polygon = self.polygon
        polygon_path = np.array(polygon.exterior.coords[:])
        _, radius = cv2.minEnclosingCircle(polygon_path.astype(int))
        return radius*2

    def get_bounding_box(self, x_min=None, y_min=None, x_max=None, y_max=None):
        p1, p2, p3, p4 = self.get_bounding_box_points(x_min, y_min, x_max, y_max)
        return self._box_to_polygon({
                'up_left': p1,
                'up_right': p2,
                'down_right': p3,
                'down_left': p4
            })

    def get_bounding_box_points(self, x_min=None, y_min=None, x_max=None, y_max=None):
        bounds = self.get_bounds()
        xm = x_min if not x_min is None else bounds['x_min']
        xM = x_max if not x_max is None else bounds['x_max']
        ym = y_min if not y_min is None else bounds['y_min']
        yM = y_max if not y_max is None else bounds['y_max']
        return [(xm, ym), (xM, ym), (xM, yM), (xm, yM)]

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
        if scale_level != 0:
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
        if scale_level != 0:
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
        cv2.fillPoly(mask, np.array([polygon_path, ]), 1)
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
