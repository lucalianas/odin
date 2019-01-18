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

import requests, csv

from odin.libs.promort.client import ProMortClient
from odin.libs.promort.errors import ProMortAuthenticationError, UserNotAllowed


class CasesOverallScoring(object):

    def __init__(self, host, user, passwd, logger):
        self.promort_client = ProMortClient(host, user, passwd)
        self.logger = logger

    def _get_cases(self):
        url = 'api/cases/'
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            return [(c['id'], c['laboratory']) for c in response.json()]
        return []

    def _get_case_overall_score(self, case_id):
        url = 'api/odin/reviews/%s/score/' % case_id
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            return response.json().values()
        return None

    def run(self, out_file):
        self.promort_client.login()
        try:
            cases = self._get_cases()
            with open(out_file, 'w') as output_file:
                writer = csv.DictWriter(output_file, ['case', 'laboratory', 'primary_score', 'secondary_score'])
                writer.writeheader()
                for case, lab in cases:
                    scores = self._get_case_overall_score(case)
                    if scores is not None:
                        for score in scores:
                            score['case'] = case
                            score['laboratory'] = lab
                            writer.writerow(score)
            self.promort_client.logout()
        except UserNotAllowed, e:
            self.logger.error(e.message)
            self.promort_client.logout()
        except ProMortAuthenticationError, e:
            self.logger.error(e.message)


cos_help_doc = """
add doc
"""


def cos_implementation(host, user, passwd, logger, args):
    case_scoring = CasesOverallScoring(host, user, passwd, logger)
    case_scoring.run(args.output_file)


# -------------------------------------------------------------
class DetailedCaseOverallScoring(CasesOverallScoring):

    def __init__(self, host, user, passwd, logger):
        super(DetailedCaseOverallScoring, self).__init__(host, user, passwd, logger)

    def _get_detailed_score(self, case_id):
        url = 'api/odin/reviews/%s/score/details/' % case_id
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            return response.json().values()
        return []

    def run(self, out_file):
        self.promort_client.login()
        try:
            cases = self._get_cases()
            with open(out_file, 'w') as output_file:
                writer = csv.DictWriter(output_file,
                                        ['case', 'laboratory', 'slide', 'core', 'primary_gleason', 'secondary_gleason'])
                writer.writeheader()
                for case, lab in cases:
                    score_details = self._get_detailed_score(case)
                    for review_details in score_details:
                        for slide, cores in review_details['slides_details'].iteritems():
                            for core in cores:
                                writer.writerow({
                                    'case': case,
                                    'laboratory': lab,
                                    'slide': slide,
                                    'core': core['core_label'],
                                    'primary_gleason': core['primary_gleason_score'],
                                    'secondary_gleason': core['secondary_gleason_score']
                                })
        except UserNotAllowed, e:
            self.logger.error(e.message)
            self.promort_client.logout()
        except ProMortAuthenticationError, e:
            self.logger.error(e)


dcos_help_doc = """
add doc
"""


def dcos_implementation(host, user, passwd, logger, args):
    detailed_case_scoring = DetailedCaseOverallScoring(host, user, passwd, logger)
    detailed_case_scoring.run(args.output_file)


# -------------------------------------------------------------
def make_parser(parser):
    parser.add_argument('--output-file', type=str, required=True, help='output file')


def register(registration_list):
    registration_list.append(('cases_overall_scoring', cos_help_doc, make_parser, cos_implementation))
    registration_list.append(('detailed_cases_scoring', dcos_help_doc, make_parser, dcos_implementation))
