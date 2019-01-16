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

import requests
from urlparse import urljoin

from odin.libs.promort.errors import ProMortAuthenticationError, UserNotAllowed, UserNotLoggedIn


class ProMortClient(object):

    def __init__(self, host, user, passwd):
        self.promort_host = host
        self.promort_user = user
        self.promort_passwd = passwd
        self.promort_client = requests.Session()
        self.csrf_token = None
        self.session_id = None

    def _update_payload(self, payload):
        auth_payload = {
            'csrfmiddlewaretoken': self.csrf_token,
            'promort_sessionid': self.session_id
        }
        payload.update(auth_payload)

    def login(self):
        url = urljoin(self.promort_host, 'api/auth/login/')
        payload = {'username': self.promort_user, 'password': self.promort_passwd}
        response = self.promort_client.post(url, json=payload)
        if response.status_code == requests.codes.OK:
            self.csrf_token = self.promort_client.cookies.get('csrftoken')
            self.session_id = self.promort_client.cookies.get('promort_sessionid')
        else:
            raise ProMortAuthenticationError('Authentication failed')

    def logout(self):
        payload = {}
        self._update_payload(payload)
        url = urljoin(self.promort_host, 'api/auth/logout/')
        self.promort_client.post(url, payload)
        self.csrf_token = None
        self.session_id = None

    def _logged_in(self):
        return self.csrf_token is not None and  self.session_id is not None

    def _check_permissions(self):
        url = urljoin(self.promort_host, 'api/odin/check_permissions/')
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.FORBIDDEN:
            raise UserNotAllowed('User %s is not a member of ODIN group', self.promort_user)

    def get(self, api_url):
        if self._logged_in():
            self._check_permissions()
            request_url = urljoin(self.promort_host, api_url)
            return self.promort_client.get(request_url)
        else:
            raise UserNotLoggedIn('Login not performed')
