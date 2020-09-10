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

import sys, argparse, logging, cv2, pickle
import numpy as np
from math import sqrt, log
try:
    import simplejson as json
except ImportError:
    import json

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.regions_of_interest.shapes_manager import Shape

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class AutomaticCoresExtractor(object):

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

    def _load_mask(self, tissue_mask_file, format='json'):
        if format == 'json':
            with open(tissue_mask_file) as f:
                data = json.loads(f.read())
                data['mask'] = np.uint8(np.array(data['mask']))
        elif format == 'pkl':
            with open(tissue_mask_file, 'rb') as f:
                data = pickle.load(f)
        else:
            raise ValueError('Unsupported file format %s' % format)
        return data['mask'], data['dimensions']

    def _contour_to_shape(self, contour):
        normalize_contour = list()
        for x in contour:
            normalize_contour.append(tuple(x[0]))
        try:
            return Shape(normalize_contour)
        except ValueError:
            return None

    def _get_cores(self, tissue_mask):
        contours, _ = cv2.findContours(tissue_mask, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_SIMPLE)
        contours = filter(None, [self._contour_to_shape(c) for c in contours])
        return contours

    def _filter_cores(self, cores, slide_area, core_min_area=0.02):
        accepted_cores = list()
        for core in cores:
            if (core.get_area()*100 / slide_area) >= core_min_area:
                accepted_cores.append(core)
        return accepted_cores

    def _get_scale_factor(self, slide_resolution, mask_resolution):
        scale_factor = sqrt((slide_resolution[0]*slide_resolution[1]) / (mask_resolution[0]*mask_resolution[1]))
        self.logger.info('Scale factor is %r', scale_factor)
        return scale_factor

    def _get_sorted_cores_map(self, cores):
        cores_map = dict()
        for c in cores:
            bounds = c.get_bounds()
            cores_map.setdefault((bounds['y_min'], bounds['y_max']), []).append(c)
        sorted_y_coords = cores_map.keys()
        sorted_y_coords.sort(key=lambda x: x[0])
        return cores_map, sorted_y_coords

    def _group_nearest_cores(self, cores, slide_height, height_tolerance=0.01):
        cores_map, sorted_y_coords = self._get_sorted_cores_map(cores)
        cores_groups = list()
        tolerance = slide_height*height_tolerance
        current_group = cores_map[sorted_y_coords[0]]
        for i, yc in enumerate(sorted_y_coords[1:]):
            if yc[0] <= sorted_y_coords[i][1] + tolerance:
                current_group.extend(cores_map[yc])
            else:
                cores_groups.append(current_group)
                current_group = cores_map[yc]
        cores_groups.append(current_group)
        return cores_groups

    def _get_slice(self, cores_group):
        x_min = min([c.get_bounds()['x_min'] for c in cores_group])
        y_min = min([c.get_bounds()['y_min'] for c in cores_group])
        x_max = max([c.get_bounds()['x_max'] for c in cores_group])
        y_max = max([c.get_bounds()['y_max'] for c in cores_group])
        return Shape([(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)])

    def _build_slide_json(self, cores_group, scale_factor):
        scale_factor = log(scale_factor, 2)
        slide_shapes = list()
        for group in cores_group:
            slice = self._get_slice(group)
            slice_map = {
                'coordinates': slice.get_coordinates(scale_factor),
                'cores': [
                    {'coordinates': c.get_coordinates(scale_factor),
                     'length': c.get_length(scale_factor),
                     'area': c.get_area(scale_factor)}
                    for c in group]
            }
            slide_shapes.append(slice_map)
        return slide_shapes

    def run(self, mask_file, output_file):
        img_mask, original_resolution = self._load_mask(mask_file)
        cores = self._filter_cores(self._get_cores(img_mask), img_mask.size)
        grouped_cores = self._group_nearest_cores(cores, img_mask.shape[0])
        scale_factor = self._get_scale_factor(original_resolution, img_mask.shape)
        slide_json = self._build_slide_json(grouped_cores, scale_factor)
        with open(output_file, 'w') as ofile:
            ofile.write(json.dumps(slide_json))


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tissue-mask', type=str, required=True,
                        help='the file containing the tissue mask')
    parser.add_argument('--output-file', type=str, required=True, help='output JSON file')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    cores_extractor = AutomaticCoresExtractor(args.log_level, args.log_file)
    cores_extractor.run(args.tissue_mask, args.output_file)


if __name__ == '__main__':
    main(sys.argv[1:])
