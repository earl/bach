#!/usr/bin/env python
from mechanize import Browser, FormNotFoundError, HTTPError, LinkNotFoundError
from urllib import urlencode

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


if __name__ == '__main__':
    import getpass, json, os.path
    p = os.path.expanduser('~/.bachrc')
    c = json.load(open(p)) if os.path.exists(p) else {}
    b = BachBrowser()
    b.login(c.get('user') or str(input('User: ')),
            c.get('pin') or getpass.getpass('PIN: '))
    try:
        for acct in c.get('accounts') or b.list_accounts():
            print b.read_account(acct),
    finally:
        b.logout()
