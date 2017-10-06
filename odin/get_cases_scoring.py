import requests, csv
from urlparse import urljoin


from promort_generic_tool import ProMortTool


class CasesOverallScoring(ProMortTool):

    def __init__(self, host, user, passwd, logger):
        super(CasesOverallScoring, self).__init__(host, user, passwd, logger)

    def _get_cases(self):
        url = urljoin(self.promort_host, 'api/cases/')
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            return [(c['id'], c['laboratory']) for c in response.json()]
        return []

    def _get_case_overall_score(self, case_id):
        url = urljoin(self.promort_host, 'api/odin/reviews/%s/score/' % case_id)
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            return response.json().values()
        return None

    def run(self, out_file):
        self._login()
        perm_ok = self._check_odin_permissions()
        if perm_ok:
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
        self._logout()


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
        url = urljoin(self.promort_host, 'api/odin/reviews/%s/score/details/' % case_id)
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.OK:
            return response.json().values()
        return []

    def run(self, out_file):
        self._login()
        perm_ok = self._check_odin_permissions()
        if perm_ok:
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
        self._logout()


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
