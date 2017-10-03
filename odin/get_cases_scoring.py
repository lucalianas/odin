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
        return []

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
                    for score in scores:
                        score['case'] = case
                        score['laboratory'] = lab
                        writer.writerow(score)
        self._logout()


help_doc = """
add doc
"""


def make_parser(parser):
    parser.add_argument('--output-file', type=str, required=True, help='output file')


def implementation(host, user, passwd, logger, args):
    case_scoring = CasesOverallScoring(host, user, passwd, logger)
    case_scoring.run(args.output_file)


def register(registration_list):
    registration_list.append(('cases_overall_scoring', help_doc, make_parser, implementation))
