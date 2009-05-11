#!/usr/bin/env python
"""A scraper for Bank Austria's online banking"""

__license__ = '''
Copyright (C) 2009 Andreas Bolka

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

__version__ = '0.0.0'

from mechanize import Browser, FormNotFoundError, HTTPError, LinkNotFoundError
from urllib import urlencode

class BachError(Exception): pass
class AccountNotFoundError(BachError): pass

class BachBrowser(object):
    def __init__(self):
        self._b = Browser()

    def login(self, user, pin):
        # submit login form
        login_data = urlencode({'yzbks': user, 'jklwd': pin})
        self._b.open(servlet_url('SSOLogin'), login_data)

        # open the content frame
        self._b.follow_link(name='content')

        # ack the "please don't forget to logout" form (if present)
        try:
            self._b.select_form('Main')
            self._b.submit()
        except FormNotFoundError:
            pass

        # store current session id
        self._b.select_form('Main')
        self._session_id = self._b['sessionid']

        # store the url of the "overview" page
        self._root_url = self._b.geturl()

    def logout(self):
        try:
            self._b.open(servlet_url('Logout'))
        except HTTPError, e:
            if e.code != 503:
                raise e

    def _open_root(self):
        self._b.open(self._root_url)

    def _find_account(self, account_re):
        # assumes that the browser is on the proper page (root)
        try:
            link = self._b.find_link(text_regex=account_re,
                                     predicate=is_account_link)
        except LinkNotFoundError, e:
            raise AccountNotFoundError(account_re)
        args = dict(link.attrs)['onclick'].split("'")
        return args[1], args[3].replace(' ', '%20')

    def _open_account(self, account_re):
        # assumes that the browser is on the proper page (root)
        servlet, params = self._find_account(account_re)
        self._b.open('%s?sessionid=%s&language=DE&mode=no%s' % (
                servlet_url(servlet), self._session_id, params))

    def _open_download(self, mode='csv'):
        # assumes that the browser is on the proper page (account detail)
        self._b.select_form('PrintDownload')
        self._b.form.action = self._b.geturl()
        self._b.form.set_all_readonly(False)
        self._b['downloadfilename'] = 'records.%s' % mode
        self._b['downloadmode'] = '%syes' % mode
        self._b['printmode'] = 'no'
        self._b.submit()

    def read_account(self, account, mode='csv'):
        self._open_root()
        self._open_account(account)
        self._open_download(mode)
        r = self._b.response()
        t = r.info().get('content-type')
        return r.read() if t and not t.startswith('text/html') else None

    def list_accounts(self):
        self._open_root()
        return [link.text for link in self._b.links(predicate=is_account_link)]

def servlet_url(name):
    return 'https://online.bankaustria.at/servlet/%s' % name

def is_account_link(link):
    onclick = dict(link.attrs).get('onclick')
    return onclick and onclick.startswith('javascript:submit_detail(')


def configure():
    import getpass, json, optparse, os, os.path, stat, sys
    optp = optparse.OptionParser(usage='usage: %prog [options]')
    optp.add_option('-c', dest='config', metavar='FILE',
            help='use config options from FILE (default: %default)')
    optp.add_option('-u', dest='user',
            help='set user code to USER')
    optp.add_option('-p', dest='pin',
            help='set pin to PIN')
    optp.add_option('-a', dest='accounts', metavar='ACCOUNT', action='append',
            help='fetch details for ACCOUNT. may be used more than once ' +
                 '(default: all accounts)')
    optp.set_defaults(config='~/.bachrc', accounts=[])
    (options, args) = optp.parse_args()
    if len(args) != 0:
        optp.error('no arguments expected')

    config_path = os.path.expanduser(options.config)
    config = {}
    if os.path.exists(config_path):
        if 0600 != stat.S_IMODE(os.stat(config_path)[stat.ST_MODE]):
            optp.error('config file %s must have permissions 600' % config_path)
        config.update(json.load(open(config_path)))
    for option, value in options.__dict__.items():
        config.setdefault(option, value)

    if not config['user'] or not config['pin']:
        if not os.isatty(sys.stdin.fileno()):
            optp.error('missing USER and/or PIN')
    config['user'] = config['user'] or str(input('User: '))
    config['pin'] = config['pin'] or getpass.getpass('PIN: ')
    return config

if __name__ == '__main__':
    try:
        c = configure()
        b = BachBrowser()
        b.login(c['user'], c['pin'])
        try:
            for acct in c.get('accounts') or b.list_accounts():
                print b.read_account(acct),
        finally:
            b.logout()
    except KeyboardInterrupt:
        pass
