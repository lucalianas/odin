from odin.libs.promort.client import ProMortClient
from odin.libs.promort.errors import ProMortAuthenticationError, UserNotAllowed


class SendReviewReports(object):

    def __init__(self, host, user, passwd, logger):
        self.promort_client = ProMortClient(host, user, passwd)
        self.logger = logger

    def _send_reports(self):
        url = 'api/odin/reviewers_report/send/'
        response = self.promort_client.get(url)
        return response.json()

    def run(self):
        self.promort_client.login()
        try:
            send_reports_result = self._send_reports()
            for reviewer, sent in send_reports_result.iteritems():
                self.logger.info('Reviewer %s --- report sent: %s', reviewer, sent)
        except UserNotAllowed, e:
            self.logger.error(e.message)
            self.promort_client.logout()
        except ProMortAuthenticationError, e:
            self.logger.error(e)


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
