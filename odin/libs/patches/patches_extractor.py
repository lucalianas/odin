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

from PIL import Image

from odin.libs.patches.errors import InvalidScaleFactor


class PatchesExtractor(object):

    def __init__(self, dzi_wrapper):
        self.slide_wrapper = dzi_wrapper
        self.tiles_cache = dict()

    def _get_scale_level(self, scale_factor):
        max_level = self.slide_wrapper.get_max_zoom_level()
        if scale_factor > 0 or scale_factor < -max_level:
            raise InvalidScaleFactor('Scale factor of %d is not valid' % scale_factor)
        else:
            return max_level + scale_factor

    def _get_patch_coordinates(self, center, scale_factor):
        center = self.slide_wrapper.scale_point_to_level(center[0], center[1],
                                                         self._get_scale_level(scale_factor))
        tile_size = self.slide_wrapper.get_tile_size()
        upper_left_x = center[0] - tile_size/2
        upper_left_y = center[1] - tile_size/2
        return {
            'up_left': (upper_left_x, upper_left_y),
            'down_left': (upper_left_x, upper_left_y + tile_size),
            'down_right': (upper_left_x + tile_size, upper_left_y + tile_size),
            'up_right': (upper_left_x + tile_size, upper_left_y)
        }

    def _load_tile(self, point, scale_factor):
        if point not in self.tiles_cache:
            level = self._get_scale_level(scale_factor)
            tile, grid_coordinates = self.slide_wrapper.get_tile_by_point(level, point)
            self.tiles_cache[grid_coordinates] = tile
            return grid_coordinates

    def _get_patch_grid(self, patch_vertices, scale_factor):
        patch_grid = dict()
        for k, v in patch_vertices.iteritems():
            patch_grid[k] = self._load_tile(v, scale_factor)
        # clean the grid
        if patch_grid['down_right'] == patch_grid['down_left'] or patch_grid['down_right'] == patch_grid['up_right']:
            patch_grid.pop('down_right')
        if patch_grid['down_left'] == patch_grid['up_left']:
            patch_grid.pop('down_left')
        if patch_grid['up_right'] == patch_grid['up_left']:
            patch_grid.pop('up_right')
        return patch_grid

    def _get_context_img_resolution(self, patch_grid):
        width, height = self.tiles_cache[patch_grid['up_left']].size
        try:
            width += self.tiles_cache[patch_grid['up_right']].width
        except KeyError:
            pass
        try:
            height += self.tiles_cache[patch_grid['down_right']].height
        except KeyError:
            pass
        return width, height

    def _get_context_img(self, patch_grid):
        tile_size = self.slide_wrapper.get_tile_size()
        context_img_width, context_img_height = self._get_context_img_resolution(patch_grid)
        context_img = Image.new('RGB', (context_img_width, context_img_height))
        context_img.paste(self.tiles_cache[patch_grid['up_left']], (0, 0))
        try:
            context_img.paste(self.tiles_cache[patch_grid['up_right']], (tile_size, 0))
        except KeyError:
            pass
        try:
            context_img.paste(self.tiles_cache[patch_grid['down_left']], (0, tile_size))
        except KeyError:
            pass
        try:
            context_img.paste(self.tiles_cache[patch_grid['down_right']], (tile_size, tile_size))
        except KeyError:
            pass
        return context_img

    def _new_patch_coordinates(self, patch_vertices):
        tile_size = self.slide_wrapper.get_tile_size()
        new_up_left = (
            patch_vertices['up_left'][0] % tile_size,
            patch_vertices['up_left'][1] % tile_size
            )
        new_patch_grid = {
            'up_left': new_up_left,
            'down_left': (new_up_left[0], new_up_left[1] + tile_size),
            'down_right': (new_up_left[0] + tile_size, new_up_left[1] + tile_size),
            'up_right': (new_up_left[0] + tile_size, new_up_left[1])
        }
        return new_patch_grid

    def _extract_patch(self, context_image, patch_vertices):
        tile_size = self.slide_wrapper.get_tile_size()
        patch_ctx_coordinates = self._new_patch_coordinates(patch_vertices)
        cropped_image = context_image.crop((
            patch_ctx_coordinates['up_left'][0],
            patch_ctx_coordinates['up_left'][1],
            patch_ctx_coordinates['up_left'][0] + tile_size,
            patch_ctx_coordinates['up_left'][1] + tile_size
        ))
        return cropped_image

    def get_patch(self, patch_center, scale_factor=0):
        patch_vertices = self._get_patch_coordinates(patch_center, scale_factor)
        patch_grid = self._get_patch_grid(patch_vertices, scale_factor)
        context_image = self._get_context_img(patch_grid)
        return self._extract_patch(context_image, patch_vertices), patch_vertices
