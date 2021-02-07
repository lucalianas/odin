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

#!/bin/bash

SLIDE_LABEL="${1}"
SLIDES_FOLDER="${2}"
TILES_FOLDER="${3}"
ORIGIN_IMG_FOLDER="${4}"
ROIS_IMG_FOLDER="${5}"

ZOOM_LEVEL="${6}"

PROMORT_HOST="${7}"
PROMORT_USER="${8}"
PROMORT_PASSWD="${9}"
PROMORT_COOKIE="${10}"


echo "### PROCESSING SLIDE $SLIDE_LABEL ###"
echo "--- TILES EXTRACTION"
python slide_to_tiles.py --slide $SLIDES_FOLDER/$SLIDE_LABEL.mrxs --zoom-level $ZOOM_LEVEL --tile-size 1024 --out-folder $TILES_FOLDER --max-white 100
echo "--- BUILDING PNG IMAGE"
python tiles_to_slide.py --tiles-folder $TILES_FOLDER/$SLIDE_LABEL --output-file $ORIGIN_IMG_FOLDER/$SLIDE_LABEL.png
echo "--- PRINTING ROIS"
python draw_rois.py --promort-host $PROMORT_HOST --promort-user $PROMORT_USER --promort-passwd $PROMORT_PASSWD --promort-cookie $PROMORT_COOKIE --original-slide $ORIGIN_IMG_FOLDER/$SLIDE_LABEL.png --zoom-level $ZOOM_LEVEL --output-path $ROIS_IMG_FOLDER
echo "### JOB COMPLETED FOR SLIDE $SLIDE_LABEL ###"
