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

from csv import DictReader, DictWriter
import os
from itertools import chain
from uuid import uuid4
import numpy as np
from shapely.errors import TopologicalError

from odin.libs.promort.client import ProMortClient
from odin.libs.promort.errors import ProMortAuthenticationError, UserNotAllowed
from odin.libs.regions_of_interest.shapes_manager import ShapesManager
from odin.libs.regions_of_interest.errors import InvalidPolygonError
from odin.libs.deepzoom.deepzoom_wrapper import DeepZoomWrapper
from odin.libs.deepzoom.errors import DZIBadTileAddress
from odin.libs.patches.patches_extractor import PatchesExtractor
from odin.libs.patches.utils import extract_white_mask
from odin.libs.masks_manager import utils as mmu


class RandomPatchesExtractor(object):

    def __init__(self, host, user, passwd, logger):
        self.promort_client = ProMortClient(host, user, passwd)
        self.shapes_manager = ShapesManager(self.promort_client)
        self.logger = logger

    def _build_data_mappings(self, focus_regions_list):
        dependencies_tree = dict()
        positive_focus_regions = set()
        negative_focus_regions = set()
        with open(focus_regions_list) as f:
            reader = DictReader(f)
            for row in reader:
                dependencies_tree.setdefault(row['slide_id'], dict())\
                    .setdefault(row['parent_core_id'], list()).append(row['focus_region_id'])
                if row['tissue_status'] == 'TUMOR':
                    positive_focus_regions.add(row['focus_region_id'])
                elif row['tissue_status'] == 'NORMAL':
                    negative_focus_regions.add(row['focus_region_id'])
        return dependencies_tree, positive_focus_regions, negative_focus_regions

    def _load_focus_regions(self, focus_regions, slide_id, positive_regions, negative_regions):
        fregions = {
            'positive': [],
            'negative': []
        }
        for region in focus_regions:
            if region in positive_regions:
                fregions['positive'].append((self.shapes_manager.get_focus_region(slide_id, region), region))
            elif region in negative_regions:
                fregions['negative'].append((self.shapes_manager.get_focus_region(slide_id, region), region))
            else:
                self.logger.critical('There is no classification for focus region %r of slide %s', region, slide_id)
        return fregions

    def _extract_patch(self, point, scaling, extractor):
        return extractor.get_patch((point.x, point.y), scaling)

    def _get_tissue_masks(self, patch_coordinates, core, scaling, tolerance):
        tissue_mask = core.get_intersection_mask(patch_coordinates, scaling, tolerance)
        not_tissue_mask = core.get_difference_mask(patch_coordinates, scaling, tolerance)
        return tissue_mask, not_tissue_mask

    def _get_regions_mask(self, patch_coordinates, regions, tile_size, scaling, tolerance):
        mask = np.zeros((tile_size, tile_size), np.uint8)
        for r in regions:
            m = r[0].get_intersection_mask(patch_coordinates, scaling, tolerance)
            mask = mmu.add_mask(mask, m)
        return mask

    def _get_positive_regions_mask(self, patch_coordinates, positive_regions, tile_size, scaling, tolerance):
        return self._get_regions_mask(patch_coordinates, positive_regions, tile_size, scaling, tolerance)

    def _get_negative_regions_mask(self, patch_coordinates, negative_regions, tile_size, scaling, tolerance):
        return self._get_regions_mask(patch_coordinates, negative_regions, tile_size, scaling, tolerance)

    def _build_masks(self, patch_coordinates, core, positive_regions, negative_regions, patch_image, tile_size,
                     scaling, tolerance, white_lower_bound):
        tissue_mask, not_tissue_mask = self._get_tissue_masks(patch_coordinates, core,
                                                              scaling, tolerance)
        return {
            'tissue': tissue_mask,
            'not_tissue': not_tissue_mask,
            'tumor': self._get_positive_regions_mask(patch_coordinates, positive_regions,
                                                     tile_size, scaling, tolerance),
            'not_tumor': self._get_negative_regions_mask(patch_coordinates, negative_regions,
                                                         tile_size, scaling, tolerance),
            'cv2_white': extract_white_mask(patch_image, white_lower_bound)
        }

    def _serialize_patch(self, patch_img, slide_id, output_folder):
        f_uuid = uuid4().hex
        try:
            os.makedirs(os.path.join(output_folder, slide_id))
        except OSError:
            pass
        out_file = os.path.join(output_folder, slide_id, '%s.jpeg' % f_uuid)
        patch_img.save(out_file)
        return f_uuid

    def _serialize_masks(self, masks, patch_uuid, slide_id, output_folder):
        out_file = os.path.join(output_folder, slide_id, '%s.npz' % patch_uuid)
        np.savez_compressed(out_file, tissue=masks['tissue'], not_tissue=masks['not_tissue'],
                            tumor=masks['tumor'], not_tumor=masks['not_tumor'],
                            cv2_white=masks['cv2_white'])

    def _serialize(self, patch, masks, slide_id, output_folder):
        patch_uuid = self._serialize_patch(patch, slide_id, output_folder)
        self._serialize_masks(masks, patch_uuid, slide_id, output_folder)
        return patch_uuid

    def _save_slide_map(self, slide_id, slide_map, output_folder):
        out_file = os.path.join(output_folder, slide_id, 'patches_map.csv')
        with open(out_file, 'w') as ofile:
            writer = DictWriter(ofile, ['slide_id', 'focus_region_id', 'patch_uuid'])
            writer.writeheader()
            for row in slide_map:
                writer.writerow(row)

    def _patches_folder_exists(self, slide_id, output_folder):
        return os.path.isdir(os.path.join(output_folder, slide_id))

    def run(self, focus_regions_list, slides_folder, tile_size, patches_count, scaling, tolerance,
            white_lower_bound, output_folder):
        try:
            self.promort_client.login()
            dependencies_tree, positive_regions, negative_regions = self._build_data_mappings(focus_regions_list)
            for slide, cores in dependencies_tree.iteritems():
                if not self._patches_folder_exists(slide, output_folder):
                    slide_path = os.path.join(slides_folder, '%s.mrxs' % slide)
                    slide_map = list()
                    self.logger.info('Processing file %s', slide_path)
                    patches_extractor = PatchesExtractor(DeepZoomWrapper(slide_path, tile_size))
                    for core, focus_regions in cores.iteritems():
                        core_shape = self.shapes_manager.get_core(slide, core)
                        self.logger.info('Loading core %s', core)
                        focus_regions_shapes = self._load_focus_regions(focus_regions, slide,
                                                                        positive_regions, negative_regions)
                        self.logger.info('Loaded %d positive shapes and %d negative',
                                         len(focus_regions_shapes['positive']),
                                         len(focus_regions_shapes['negative']))
                        for focus_region in chain(*focus_regions_shapes.values()):
                            try:
                                for point in focus_region[0].get_random_points(patches_count):
                                    processed = False
                                    tolerance_value = 0.0
                                    while not processed:
                                        try:
                                            patch, coordinates = self._extract_patch(point, scaling, patches_extractor)
                                            masks = self._build_masks(coordinates, core_shape, focus_regions_shapes['positive'],
                                                                      focus_regions_shapes['negative'], patch, tile_size,
                                                                      scaling, tolerance_value, white_lower_bound)
                                            patch_uuid = self._serialize(patch, masks, slide, output_folder)
                                            slide_map.append({
                                                'slide_id': slide,
                                                'focus_region_id': focus_region[1],
                                                'patch_uuid': patch_uuid
                                            })
                                            processed = True
                                        except TopologicalError:
                                            tolerance_value += tolerance
                                            self.logger.debug('Intersection failed, increasing tolerance to %f',
                                                              tolerance_value)
                                        except DZIBadTileAddress, e:
                                            self.logger.error(e.message)
                                            processed = True
                            except InvalidPolygonError:
                                self.logger.error('FocusRegion is not a valid shape, skipping it')
                    try:
                        self._save_slide_map(slide, slide_map, output_folder)
                    except IOError:
                        self.logger.warning('There is no output folder for slide %s, no focus regions map to save', slide)
                else:
                    self.logger.warning('There is already a patches folder for slide %s, skipping it', slide)
            self.promort_client.logout()
        except UserNotAllowed, e:
            self.logger.error('UserNotAllowedError: %r', e.message)
            self.promort_client.logout()
        except ProMortAuthenticationError, e:
            self.logger.error('AuthenticationError: %r', e.message)


doc = """
add doc
"""


def implementation(host, user, passwd, logger, args):
    patches_extractor = RandomPatchesExtractor(host, user, passwd, logger)
    patches_extractor.run(args.focus_regions_list, args.slides_folder, args.tile_size, args.patches_count,
                          args.scaling, args.tolerance, args.white_lower_bound, args.output_folder)


def make_parser(parser):
    parser.add_argument('--focus-regions', dest='focus_regions_list', type=str, required=True,
                        help='the list of the focus regions as a CSV file')
    parser.add_argument('--slides-folder', type=str, required=True, help='the folder with the images files')
    parser.add_argument('--tile-size', type=int, default=256, help='the size of the output patches')
    parser.add_argument('--patches-count', type=int, required=True,
                        help='the number of patches that will be extracted for each focus region')
    parser.add_argument('--scaling', type=int, default=0, help='scaling level expressed as a negative number')
    parser.add_argument('--simplify-tolerance', dest='tolerance', type=float, default=10.,
                        help='the tolerance step that will be used to simplify shapes that fail in the intersection')
    parser.add_argument('--lower-white', dest='white_lower_bound', type=int, default=230,
                        help='the lower boundary used for automatic white identification')
    parser.add_argument('--output-folder', type=str, required=True, help='output folder for patches and masks')


def register(registration_list):
    registration_list.append(('extract_patches', doc, make_parser, implementation))
