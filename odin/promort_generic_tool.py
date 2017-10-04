import requests, sys
from urlparse import urljoin


class ProMortTool(object):

    def __init__(self, host, user, passwd, logger):
        self.promort_host = host
        self.user = user
        self.passwd = passwd
        self.logger = logger
        self.promort_client = requests.Session()
        self.csrf_token = None
        self.session_id = None

    def _update_payload(self, payload):
        auth_payload = {
            'csrfmiddlewaretoken': self.csrf_token,
            'promort_sessionid': self.session_id
        }
        payload.update(auth_payload)

    def _login(self):
        self.logger.info('Logging as "%s"', self.user)
        url = urljoin(self.promort_host, 'api/auth/login/')
        payload = {'username': self.user, 'password': self.passwd}
        response = self.promort_client.post(url, json=payload)
        if response.status_code == requests.codes.OK:
            self.csrf_token = self.promort_client.cookies.get('csrftoken')
            self.session_id = self.promort_client.cookies.get('promort_sessionid')
            self.logger.info('Successfully logged in')
        else:
            self.logger.critical('Unable to perform login with given credentials')
            sys.exit('Unable to perform login with given credentials')

    def _logout(self):
        payload = {}
        self._update_payload(payload)
        url = urljoin(self.promort_host, 'api/auth/logout/')
        response = self.promort_client.post(url, payload)
        self.logger.info('Logout response code %r', response.status_code)

    def _check_odin_permissions(self):
        self.logger.info('Checking if user has proper permissions')
        url = urljoin(self.promort_host, 'api/odin/check_permissions/')
        response = self.promort_client.get(url)
        if response.status_code == requests.codes.NO_CONTENT:
            return True
        else:
            self.logger.warn('User didn\'t passed permissions check: response code %s', response.status_code)
            return False

    def _load_ome_seadragon_info(self):
        url = urljoin(self.promort_host, 'api/utils/omeseadragon_base_urls/')
        response = self.promort_client.get(url)
        return response.json()['base_url']
