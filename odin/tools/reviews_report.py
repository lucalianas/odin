from urlparse import urljoin

from promort_generic_tool import ProMortTool


class SendReviewReports(ProMortTool):

    def __init__(self, host, user, passwd, logger):
        super(SendReviewReports, self).__init__(host, user, passwd, logger)

    def _send_reports(self):
        url = urljoin(self.promort_host, 'api/odin/reviewers_report/send/')
        response = self.promort_client.get(url)
        return  response.json()

    def run(self):
        self._login()
        perm_ok = self._check_odin_permissions()
        if perm_ok:
            send_reports_result = self._send_reports()
        for reviewer, sent in send_reports_result.iteritems():
            self.logger.info('Reviewer %s --- report sent: %s', reviewer, sent)
        self._logout()


help_doc = """
add doc
"""


def implementation(host, user, passwd, logger, args):
    send_report = SendReviewReports(host, user, passwd, logger)
    send_report.run()


def make_parser(parser):
    pass


def register(registration_list):
    registration_list.append(('send_review_reports', help_doc, make_parser, implementation))
