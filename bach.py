#!/usr/bin/env python
from getpass import getpass
from mechanize import Browser, FormNotFoundError, HTTPError

# config
config = {
    'u': str(input('User Code: ')),
    'p': getpass('PIN: '),
    'n': str(input('Account Number: '))
}

# init
b = Browser()

# login
b.open('https://online.bankaustria.at/bach/de/login/login.html')
b.select_form('Frame_Login')
b.form.action = 'https://online.bankaustria.at/servlet/SSOLogin'
b['yzbks'] = config['u']
b['jklwd'] = config['p']
b.submit()

# open the content frame
b.follow_link(name='content')

# ignore the "please don't forget to logout" page
try:
    b.select_form('Main')
    b.submit()
except FormNotFoundError:
    pass

# navigate to detail page
b.select_form('Main')
link = b.find_link(text_regex=r'%s' % config['n'])
servlet = 'https://online.bankaustria.at/servlet/GiroKontoDetail'
sessionid = b['sessionid']
paramstr = dict(link.attrs)['onclick'].split(',')[1].strip("'")
b.open('%s?sessionid=%s&language=DE&mode=no%s' % (
        servlet, sessionid, paramstr))

# download csv
b.select_form('PrintDownload')
b.form.action = 'https://online.bankaustria.at/servlet/GiroKontoDetail'
b.form.set_all_readonly(False)
b['downloadfilename'] = 'records.csv'
b['downloadmode'] = 'csvyes'
b['printmode'] = 'no'
r = b.submit()

# print csv
print r.read(),

# logout
try:
    b.open('https://online.bankaustria.at/servlet/Logout')
except HTTPError:
    pass
