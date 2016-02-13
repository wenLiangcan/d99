#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# Batch download comic books from:
#
# - 99manga.com
# - 99comic.com
# - 99mh.com
#

import argparse
import json
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
    @staticmethod
    def _prepare(this):
        this._DOMAINS = {
            '99manga.com': 0,
            '99comic.com': 1,
            '99mh.com': 2,
        }

        this._KEYS = ('gsanuxoewrm', 'zhangxoewrm', '',)

        this._DECODE_ALG = (
            this._decode_piclst_0_1,
            this._decode_piclst_0_1,
            this._decode_piclst_2,
        )

        this._CHARSET = ('gb2312', 'gb2312', 'utf-8')

        this._PATTERNS = (
            r'var\s+PicListUrl\s*=\s*"(.*?)";',
            r'var\s+PicListUrls\s*=\s*"(.*?)";',
            r'var\s+sFiles\s*=\s*"(.*?)";',
        )

        this._SERVERS_0_1 = (
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

        this._GET_SERVER = (
            this._get_server_0_1,
            this._get_server_0_1,
            this._get_server_2,
        )

        this._GET_VOLS = (
            this._get_volumes_0_1,
            this._get_volumes_0_1,
            this._get_volumes_2,
        )

        this._GET_BOOK_NAMES = (
            this._get_book_name_0_1,
            this._get_book_name_0_1,
            this._get_book_name_2,
        )

    def __init__(self, url):
        self._prepare(self)

        self.domain = urlparse.urlsplit(url).netloc
        assert self.domain in self._DOMAINS.keys()

        index = self._DOMAINS[self.domain]
        self._get_server = self._GET_SERVER[index]
        self.key = self._KEYS[index]
        self._decode_piclst = self._DECODE_ALG[index]
        self.charset = self._CHARSET[index]
        self.pattern = re.compile(self._PATTERNS[index])
        self.get_volumes = self._GET_VOLS[index]
        self.get_book_name = self._GET_BOOK_NAMES[index]

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

    def get_html(self, url):
        return get_html(url, self.charset)

    def get_piclst(self, resp):
        server = self._get_server(resp)

        html = resp.text
        encoded_piclst = self._extract_encoded_piclst(html)
        piclst = self._decode_piclst(encoded_piclst)
        return [server + l for l in piclst]


class Book(object):
    def __init__(self, url):
        self.site = Site99(url)
        html = self.site.get_html(url)

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
        self.pics = None
        self.book = book
        self.name = name
        self.url = url
        self.charset = self.book.charset

        self.folder = p.join(self.book.name, self.name).replace(' ', '_')

    def get_pics(self):
        if self.pics is None:
            resp = http_get(self.url, self.charset)

            piclst = self.book.get_piclst(resp)

            width = cal_num_width(len(piclst))
            self.pics = {
                p.join(self.folder, str(i).zfill(width) + p.splitext(l)[-1]): l
                for i, l in enumerate(piclst)
            }

        return self.pics


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


def batch_download(name_url_pairs, destdir=None):
    if destdir is None:
        destdir = os.getcwd()
    destdir = p.abspath(destdir)
    with ThreadPoolExecutor(THREADS_NUM) as executor:
        for n, l in name_url_pairs.items():
            n = p.join(destdir, n)
            mkdirp(p.dirname(n))
            executor.submit(download_pic, l, n)


def aria2_batch_download(name_url_pairs, destdir=None, rpc=None):
    if rpc is None:
        rpc = 'http://127.0.0.1:6800/jsonrpc'

    jdict = {
        'jsonrpc': '2.0',
        'id': 'qwer',
        'method': 'system.multicall',
        'params': [],
    }

    default_opts = {
        'continue': 'true',
        'max-connection-per-server': '5',
        'split': '5',
        'header': ['User-Agent: {}'.format(HEAD['User-Agent'])]
    }

    def build_adduri_call(name, url, dest=None):
        opts = dict(default_opts)
        opts['out'] = name
        if dest:
            opts['dir'] = dest
        return {
            'methodName': 'aria2.addUri',
            'params': [[url], opts]
        }

    calls = [build_adduri_call(n, l, destdir) for n, l in name_url_pairs.items()]
    data = dict(jdict)
    data['params'].append(calls)
    r = requests.post(rpc, data=json.dumps(data))
    return r.status_code == 200


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
    app = argparse.ArgumentParser(
        description='Batch download comic books from 99*.com sites')
    app.add_argument('url', help="Comic book's url")
    app.add_argument('-o', '--out', help="Output directory")
    app.add_argument('-a', '--aria2', action='store_true',
                     help="Call Aria2 by JSON RPC to download files")
    app.add_argument('-r', '--rpc', type=str, help='Aria2 JSON RPC address')
    args = app.parse_args()

    url = args.url
    try:
        book = Book(url)
    except AssertionError:
        print('Unsupported link!')
        return

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
        pics = vol.get_pics()
        print()
        if args.aria2:
            print('Start to download {} pictures in 《{}》by aria2 ...'.format(len(pics.keys()), vol.name))
            if aria2_batch_download(pics, args.out, args.rpc):
                print('Finished')
            else:
                print('Failed to call Aria2')
        else:
            print('Start to download {} pictures in 《{}》...'.format(len(pics.keys()), vol.name))
            batch_download(pics, args.out)
            print('Finished')


if __name__ == '__main__':
    main()

