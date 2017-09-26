import os, sys, requests
from collections import Counter
from urlparse import urljoin


class CasesScoringCalculator(object):

    def __init__(self, host, user, passwd, logger):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.logger = logger
        self.promort_client = requests.Session()
        self.csrf_token = None
        self.session_id = None