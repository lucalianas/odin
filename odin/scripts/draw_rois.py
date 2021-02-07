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

import os, sys, argparse, logging, json, PIL
from PIL import Image, ImageDraw

from shapely.geometry import mapping

# TODO: install.py for odin lib and remove this abomination
sys.path.append('../../')

from odin.libs.promort.client import ProMortClient
from odin.libs.regions_of_interest.shapes_manager import Shape

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


class ROIsApplier(object):

    def __init__(self, host, user, password, cookie, log_level='INFO', log_file=None):
        PIL.Image.MAX_IMAGE_PIXELS = None
        self.promort_client = ProMortClient(host, user, password, cookie)
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

    def _get_slide_label(self, slide_path):
        slide_fname = slide_path.split('/')[-1]
        return slide_fname.split('.')[0]

    def _get_rois_points(self, roi_json):
        return [(s['point']['x'], s['point']['y']) for s in roi_json]

    def _load_rois(self, query_url):
        response = self.promort_client.get(query_url, None)
        if response.status_code == 200:
            rois = [(
                self._get_rois_points(json.loads(fr['roi_json'])['segments']),
                fr.get('tissue_status')
                )
                for fr in response.json()]
        else:
            self.logger.error('ERROR %d while retrieving ROIs', response.status_code)
            rois = []
        return rois

    def _load_slices(self, slide_id):
        self.logger.info('Retrieving slices')
        return self._load_rois('api/odin/rois/%s/slices/' % slide_id)

    def _load_cores(self, slide_id):
        self.logger.info('Retrieving cores')
        return self._load_rois('api/odin/rois/%s/cores/' % slide_id)

    def _load_focus_regions(self, slide_id):
        self.logger.info('Retrieving focus regions')
        return self._load_rois('api/odin/rois/%s/focus_regions/' % slide_id)

    def _get_scaled_shape(self, roi_json, scale_factor):
        self.logger.debug('Rescaling ROI')
        shape = Shape(roi_json)
        scaled_shape = shape._rescale_polygon(scale_factor)
        return mapping(scaled_shape)['coordinates']

    def _save_new_image(self, image, slide_label, output_path):
        out_path = os.path.join(output_path, '%s.png' % slide_label)
        self.logger.debug('Saving image to %s', out_path)
        image.save(out_path)

    def _draw_roi(self, image, roi_json, zoom_level, line_color, line_width=5):
        scaled_roi = self._get_scaled_shape(roi_json[0], zoom_level)
        image.line(list(scaled_roi[0]), fill=line_color, width=line_width)

    def _apply_rois(self, original_slide, slices, cores, focus_regions, zoom_level, slide_label, output_path):
        image = Image.open(original_slide)
        draw = ImageDraw.Draw(image)
        self.logger.info('Applying slices')
        for rj in slices:
            self._draw_roi(draw, rj, zoom_level, 'black')
        self.logger.info('Applying cores')
        for rj in cores:
            self._draw_roi(draw, rj, zoom_level, 'blue')
        self.logger.info('Applying focus regions')
        tissue_color_map = {
            'TUMOR': 'red',
            'NORMAL': 'green',
            'STRESSED': 'orange'
        }
        for rj in focus_regions:
            self._draw_roi(draw, rj, zoom_level, tissue_color_map[rj[1]])
        self._save_new_image(image, slide_label, output_path)

    def run(self, original_slide, zoom_level, output_path):
        slide_label = self._get_slide_label(original_slide)
        self.logger.info('Processing ROIs for slide %s', slide_label)
        self.promort_client.login()
        slices = self._load_slices(slide_label)
        cores = self._load_cores(slide_label)
        focus_regions = self._load_focus_regions(slide_label)
        self.promort_client.logout()
        self._apply_rois(original_slide, slices, cores, focus_regions, zoom_level, slide_label, output_path)
        self.logger.info('Job completed')


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--promort-host', type=str, required=True, help='ProMort host')
    parser.add_argument('--promort-user', type=str, required=True, help='ProMort user')
    parser.add_argument('--promort-passwd', type=str, required=True, help='ProMort password')
    parser.add_argument('--promort-cookie', type=str, default='promort_sessionid',
                        help='ProMort session cookie name')
    parser.add_argument('--original-slide', type=str, required=True,
                        help='slide (rendered as image) file path')
    parser.add_argument('--zoom-level', type=int, required=True,
                        help='zoom level for extraction (as a negative number where 0 is the slide\'s full resolution level)')
    parser.add_argument('--output-path', type=str, required=True,
                        help='path for the files containing the slide with overprinted ROIs (one file for ROIs review)')
    parser.add_argument('--log-level', type=str, default='INFO', help='log level (default=INFO)')
    parser.add_argument('--log-file', type=str, default=None, help='log file (default=stderr)')
    return parser


def main(argv):
    parser = get_parser()
    args = parser.parse_args(argv)
    rois_applier = ROIsApplier(args.promort_host, args.promort_user, args.promort_passwd, args.promort_cookie,
                               args.log_level, args.log_file)
    rois_applier.run(args.original_slide, args.zoom_level, args.output_path)


if __name__ == '__main__':
    main(sys.argv[1:])
