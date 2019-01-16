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
