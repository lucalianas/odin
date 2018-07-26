from odin.libs.promort.client import ProMortClient
from odin.libs.promort.errors import ProMortAuthenticationError, UserNotAllowed

import os
from requests import codes as rc

try:
    import simplejson as json
except ImportError:
    import json


class DumpROIS(object):

    def __init__(self, host, user, passwd, logger):
        self.promort_client = ProMortClient(host, user, passwd)
        self.logger = logger

    def _load_rois_by_type(self, slide_id, roi_type):
        url = 'api/odin/rois/%s/%ss/' % (slide_id, roi_type)
        response = self.promort_client.get(url)
        if response.status_code == rc.OK:
            return response.json()
        else:
            return []

    def _load_slices(self, slide_id):
        return self._load_rois_by_type(slide_id, 'slice')

    def _load_cores(self, slide_id):
        return self._load_rois_by_type(slide_id, 'core')

    def _load_focus_regions(self, slide_id):
        return self._load_rois_by_type(slide_id, 'focus_region')

    def _save_rois(self, output_path, roi_type, rois_list):
        if len(rois_list) > 0:
            out_path = os.path.join(output_path, '%ss' % roi_type)
            try:
                os.makedirs(out_path)
            except OSError:
                pass
            for r in rois_list:
                with open(os.path.join(out_path, '%s.json' % r['id']), 'w') as f:
                    json.dump(json.loads(r['roi_json'])['segments'], f)

    def _save_slices(self, output_path, slices_list):
        self._save_rois(output_path, 'slice', slices_list)

    def _save_cores(self, output_path, cores_list):
        self._save_rois(output_path, 'core', cores_list)

    def _save_focus_regions(self, output_path, focus_regions_list):
        self._save_rois(output_path, 'focus_region', focus_regions_list)

    def run(self, slides_list, output_folder):
        try:
            self.promort_client.login()
            with open(slides_list) as sf:
                slides = [x.replace('\n', '') for x in sf.readlines()]
                for s in slides:
                    out_path = os.path.join(output_folder, s)
                    slices = self._load_slices(s)
                    self._save_slices(out_path, slices)
                    cores = self._load_cores(s)
                    self._save_cores(out_path, cores)
                    focus_regions = self._load_focus_regions(s)
                    self._save_focus_regions(out_path, focus_regions)
            self.promort_client.logout()
        except UserNotAllowed, e:
            self.logger.error('UserNotAllowed Error: %r', e.message)
            self.promort_client.logout()
        except ProMortAuthenticationError, e:
            self.logger.error('ProMortAuthenticationError: %r', e.message)


help_doc = """
add doc
"""


def implementation(host, user, passwd, logger, args):
    dump_rois = DumpROIS(host, user, passwd, logger)
    dump_rois.run(args.slides_list, args.output_folder)


def make_parser(parser):
    parser.add_argument('--slides-list', type=str, required=True, help='list of slides')
    parser.add_argument('--output-folder', type=str, required=True, help='output folder')


def register(registration_list):
    registration_list.append(('dump_rois', help_doc, make_parser, implementation))
