#!/usr/bin/env python
from getpass import getpass
from mechanize import Browser, FormNotFoundError, HTTPError, LinkNotFoundError
from urllib import urlencode

config = {
    'u': str(input('User Code: ')),
    'p': getpass('PIN: '),
    'n': str(input('Account Number: '))
}

def servlet_url(name):
    return 'https://online.bankaustria.at/servlet/%s' % name

def is_account_link(link):
    onclick = dict(link.attrs).get('onclick')
    return onclick and onclick.startswith('javascript:submit_detail(')

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

    def _read_response(self):
        return self._b.response().read()

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
        return args[1], args[3]

    def _open_account(self, account_re):
        # assumes that the browser is on the proper page (root)
        servlet, params = self._find_account(account_re)
        self._b.open('%s?sessionid=%s&language=DE&mode=no%s' % (
                servlet_url(servlet), self._session_id, params))

    def _open_download(self, mode='csv'):
        # assumes that the browser is on the proper page (account detail)
        self._b.select_form('PrintDownload')
        self._b.form.action = servlet_url('GiroKontoDetail')
        self._b.form.set_all_readonly(False)
        self._b['downloadfilename'] = 'records.%s' % mode
        self._b['downloadmode'] = '%syes' % mode
        self._b['printmode'] = 'no'
        self._b.submit()

    def read_account(self, account, mode='csv'):
        self._open_root()
        self._open_account(account)
        self._open_download(mode)
        return self._read_response()


if __name__ == '__main__':
    b = BachBrowser()
    b.login(config['u'], config['p'])
    try:
        print b.read_account(config['n']),
    finally:
        b.logout()
