#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# Batch download comic books from:
#
# - 99manga.com
# - 99comic.com
# - 99mh.com
#

import os
import re
import shutil
import string
import sys
from concurrent.futures import ThreadPoolExecutor
from os import path as p
from urllib import parse as urlparse

from bs4 import BeautifulSoup as bs4

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 5.1; rv:19.0) Gecko/20100101 Firefox/19.0",
}

THREADS_NUM = 10


def http_get(url, charset='utf-8', **args):
    r = requests.get(url, headers=HEAD, **args)
    r.encoding = charset
    return r


def get_html(url, charset='utf-8', **args):
    r = http_get(url, charset=charset, **args)
    return r.text


def mkdirp(dirname):
    if not p.exists(dirname):
        os.makedirs(dirname)


def cal_num_width(num):
    return len(str(num))


class ParseSelectionException(Exception):
    pass


class Site99(object):

    def __new__(cls, _):
        cls._DOMAINS = {
            '99manga.com': 0,
            '99comic.com': 1,
            '99mh.com': 2,
        }

        cls._KEYS = ('gsanuxoewrm', 'zhangxoewrm', '',)

        cls._DECODE_ALG = (
            Site99._decode_piclst_0_1,
            Site99._decode_piclst_0_1,
            Site99._decode_piclst_2,
        )

        cls._CHARSET = ('gb2312', 'gb2312', 'utf-8')

        cls._PATTERNS = (
            r'var\s+PicListUrl\s*=\s*"(.*?)";',
            r'var\s+PicListUrls\s*=\s*"(.*?)";',
            r'var\s+sFiles\s*=\s*"(.*?)";',
        )

        cls._SERVERS_0_1 = (
            "http://2.{}:9393/dm01/",
            "http://2.{}:9393/dm02/",
            "http://2.{}:9393/dm03/",
            "http://2.{}:9393/dm04/",
            "http://2.{}:9393/dm05/",
            "http://2.{}:9393/dm06/",
            "http://2.{}:9393/dm07/",
            "http://2.{}:9393/dm08/",
            "http://2.{}:9393/dm09/",
            "http://2.{}:9393/dm10/",
            "http://2.{}:9393/dm11/",
            "http://2.{}:9393/dm12/",
            "http://2.{}:9393/dm13/",
            "http://2.{}:9393/dm14/",
            "http://2.{}:9393/dm15/",
            "http://2.{}:9393/dm16/",
        )

        cls._GET_SERVER = (
            Site99._get_server_0_1,
            Site99._get_server_0_1,
            Site99._get_server_2,
        )

        cls._GET_VOLS = (
            Site99._get_volumes_0_1,
            Site99._get_volumes_0_1,
            Site99._get_volumes_2,
        )

        cls._GET_BOOK_NAMES = (
            Site99._get_book_name_0_1,
            Site99._get_book_name_0_1,
            Site99._get_book_name_2,
        )

        return super(Site99, cls).__new__(cls)

    def __init__(self, url):
        self.domain = urlparse.urlsplit(url).netloc
        assert self.domain in self._DOMAINS.keys()

        def obj_method_proxy(method):
            return lambda *arg, **args: method(self, *arg, **args)

        index = self._DOMAINS[self.domain]
        self._get_server = obj_method_proxy(self._GET_SERVER[index])
        self.key = self._KEYS[index]
        self._decode_piclst = obj_method_proxy(self._DECODE_ALG[index])
        self.charset = self._CHARSET[index]
        self.pattern = re.compile(self._PATTERNS[index])
        self.get_volumes = obj_method_proxy(self._GET_VOLS[index])
        self.get_book_name = obj_method_proxy(self._GET_BOOK_NAMES[index])

    def _extract_encoded_piclst(self, html):
        return self.pattern.findall(html)[0]

    @staticmethod
    def _decode_piclst_base(encoded_lst, key, sep):
        for i, c in enumerate(key):
            encoded_lst = encoded_lst.replace(c, str(i))

        ss = encoded_lst.split(sep)
        return ''.join(map(chr, map(int, ss))).split('|')

    def _decode_piclst_0_1(self, encoded_lst):
        *key, sep = self.key

        return self._decode_piclst_base(encoded_lst, key, sep)

    def _decode_piclst_2(self, encoded_lst):
        d = string.ascii_lowercase.index(encoded_lst[-1]) + 1
        lst_len = len(encoded_lst)
        e = encoded_lst[lst_len - d - 12:lst_len - d - 1]
        new_lst = encoded_lst[0:lst_len -d - 12]
        *key, sep = e
        return self._decode_piclst_base(new_lst, key, sep)

    def _get_server_0_1(self, resp):
        query = urlparse.urlparse(resp.url).query
        server = urlparse.parse_qs(query)['s'][0]
        server = int(server) - 1
        return self._SERVERS_0_1[server].format(self.domain)

    def _get_server_2(self, resp):
        ptn = re.compile(r'var\s+sPath\s*=\s*"(.*?)";')
        spath = ptn.findall(resp.text)[0]
        return 'http://images.99mh.com/' + spath

    @staticmethod
    def _sort_vol_by_title(vols):
        def get_volno(title):
            ptn = re.compile('.* (\d+)集.*')
            result = ptn.findall(title)
            if len(result) == 0:
                return sys.maxsize
            else:
                return int(result[0])

        return sorted(vols, key=lambda p: get_volno(p[0]))

    def _get_volumes_0_1(self, html):
        soup = bs4(html, 'lxml')
        lis = soup.select_one('.vol > .bl').find_all('li')
        vols = [
            (li.a.text, 'http://{}{}'.format(self.domain, li.a.attrs['href']))
            for li in lis
        ]
        return self._sort_vol_by_title(vols)

    def _get_volumes_2(self, html):
        soup = bs4(html, 'lxml')
        a_s = soup.select_one('#subBookListAct').find_all('a')
        vols = [(a.text, a.attrs['href']) for a in a_s]
        return self._sort_vol_by_title(vols)

    def _get_book_name_0_1(_, html):
        ptn = re.compile('>> (.*) 集')
        return ptn.findall(html)[0]

    def _get_book_name_2(_, html):
        soup = bs4(html, 'lxml')
        title = soup.select_one('.cTitle').text
        return ' '.join(title.strip().split())

    def get_piclst(self, resp):
        server = self._get_server(resp)

        html = resp.text
        encoded_piclst = self._extract_encoded_piclst(html)
        piclst = self._decode_piclst(encoded_piclst)
        return [server + l for l in piclst]


class Book(object):
    def __init__(self, site, html):
        self.site = site
        self.volumes = self.site.get_volumes(html)
        self.name = self.site.get_book_name(html)
        self.charset = self.site.charset

        self._current = 0

    def get_piclst(self, resp):
        return self.site.get_piclst(resp)

    def _build_vol(self, index):
        name, url = self.volumes[index]
        return Volume(self, name, url)

    def __len__(self):
        return len(self.volumes)

    def __getitem__(self, key):
        return self._build_vol(key)

    def __iter__(self):
        return self

    def __next__(self):
        if self._current == len(self):
            self._current = 0
            raise StopIteration()
        else:
            self._current += 1
            return self._build_vol(self._current - 1)


class Volume(object):
    def __init__(self, book, name, url):
        self.book = book
        self.name = name
        self.url = url
        self.charset = self.book.charset

        self.folder = p.join(self.book.name, self.name).replace(' ', '_')

    def get_pics(self, resp):
        piclst = self.book.get_piclst(resp)

        width = cal_num_width(len(piclst))
        pairs = {
            p.join(self.folder, str(i).zfill(width) + p.splitext(l)[-1]): l
            for i, l in enumerate(piclst)
        }

        return pairs


def download_pic(url, name=None):
    if name is None:
        name = url.split('/')[-1]
    r = http_get(url, stream=True)
    if r.status_code == 200:
        with open(name, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
    else:
        print('Request failed')


def batch_download(name_url_pairs):
    with ThreadPoolExecutor(THREADS_NUM) as executor:
        for n, l in name_url_pairs.items():
            mkdirp(p.dirname(n))
            executor.submit(download_pic, l, n)


def parse_selection(volumes_cnt, selection):
    selection = selection.split()
    vnos = []
    try:
        for field in selection:
            field = field.split('-')
            cnt = len(field)
            assert cnt in (1, 2), "Invalid field: {}".format('-'.join(field))

            if cnt == 1:
                vnos += [int(field[0])]
            else:
                l, h = map(int, field)
                assert l < h, "{} should be smaller than {}".format(l, h)
                vnos += list(range(l, h+1))
        assert max(vnos) <= volumes_cnt, "Index out of range"
        assert min(vnos) >= 1, "Index out of range"
    except AssertionError as e:
        raise ParseSelectionException(e)
    except ValueError as e:
        raise ParseSelectionException(e)

    return sorted(set(vnos))


def main():
    url = sys.argv[1]
    try:
        site = Site99(url)
    except AssertionError:
        print('Unsupported link!')
        return

    html = get_html(url, site.charset)
    book = Book(site, html)
    vol_cnt = len(book)
    print('Found {} volumes in 《{}》:'.format(vol_cnt, book.name))
    print()
    vol_cnt_width = cal_num_width(vol_cnt)
    index_start = 1
    for i, v in enumerate(book, start=index_start):
        print(' {}. '.format(i).ljust(vol_cnt_width + 3) + v.name)
    print()
    print('Enter n° of volumes to be downloaded (ex: 1 2 3 or 1-3 or 1 2-5 8)')
    print('------------------------------------------------------------------')
    try:
        selection = input()
        if selection == '':
            return
        else:
            selection = parse_selection(vol_cnt, selection)
    except ParseSelectionException as e:
        print('Invalid input: {}'.format(e))
        return

    for i in selection:
        vol = book[i-index_start]
        resp = http_get(vol.url, vol.charset)
        pics = vol.get_pics(resp)
        print()
        print('Start to download {} pictures in 《{}》...'.format(len(pics.keys()), vol.name))
        batch_download(pics)
        print('Finished')


if __name__ == '__main__':
    main()
