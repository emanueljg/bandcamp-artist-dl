# from gevent import monkey
# monkey.patch_all()
import grequests
import asyncio
import aioimaplib
import aiohttp

import aiofile
from bs4 import BeautifulSoup
import re
import itertools
from copy import copy
import os
import shutil
from zipfile import ZipFile
from collections import namedtuple
from pprint import pprint
import click
import textwrap

from utils import Link, RatelimitException


VERBOSITY = 0


def iprint(s, indent=4):
    print(' ' * indent + s)


def vprint(s):
    if VERBOSITY:
        print(s)
        return True
    else:
        return False


def vvprint(s):
    if VERBOSITY >= 2:
        print(s)
        return True
    else:
        return False


def create_session():
    """Equivalent to aiohttp.ClientSession().

    Done so that implementations doesn't need to import aiohttp themselves and
    so, avoids gevent monkeypatching issues by too early imports.
    """
    return aiohttp.ClientSession()


class BandcampArtist:
    EMAIL_SEARCH = 'BODY https://bandcamp.com/download?from=email'

    DOWNLOAD_LINK_PATTERN = re.compile(
        r'"(https:\/\/bandcamp.com\/download\?from=email&id=(\d+)&payment_id=\d+&sig=\w+&type=\w+)"'
    )

    FLAC_LINK_PATTERN = re.compile(
        r'https:\/\/\w+\.bandcamp\.com\/download\/\w+\?enc=flac&amp;id=\d+&amp;payment_id=\d+&amp;sig=\w+'
    )

    def __init__(self, artist):
        self.artist = artist
        self.releases = None
        self._emails_left = None

    @property
    def emails_left(self):
        if not self._emails_left:
            self._emails_left = itertools.count(len(self.releases), -1)
        return self._emails_left

    @property
    def domain(self):
        return f'https://{self.artist}.bandcamp.com'

    @property
    def discography_url(self):
        return f'{self.domain}/music'

    @property
    def email_download_endpoint(self):
        return f'{self.domain}/email_download'

    def refresh_releases(self, email_address):
        reqs = (grequests.get(self.discography_url),)
        text = grequests.map(reqs)[0].text
        soup = BeautifulSoup(text, 'html.parser')
        elems = soup.find_all(lambda tag: tag.has_attr('data-item-id'))
        releases = {}
        for elem in elems:
            url = f"{self.domain}{elem.find('a')['href']}"
            release_type, release_id = elem['data-item-id'].split('-')
            releases[url] = {
                "item_id": release_id,
                "item_type": release_type,
                "address": email_address,
                "encoding_name": "none",
                "country": 'US',
                "postcode": '12345'
            }
        self.releases = releases

    def make_email_requests(self):
        requests = (
            grequests.post(self.email_download_endpoint, data=data)
            for data in self.releases.values()
        )

        for index, response in grequests.imap_enumerated(requests, size=None):
            print(response.json())
            if response.status_code == 429:
                raise RatelimitException
            if not (response.ok and response.json()['ok']):
                print('trig')
                next(self.emails_left)

    @classmethod
    async def get_download_link_from_page(cls, session, download_page):
        async with session.get(download_page) as response:
            text = await response.text()
            if (m := re.search(cls.FLAC_LINK_PATTERN, text)):
                url = m.group(0).replace('&amp;', '&')
                return url

    @staticmethod
    def file_info_of_headers(headers):
        filename = headers[aiohttp.hdrs.CONTENT_DISPOSITION] \
            .split('; ')[1] \
            .lstrip('filename=') \
            .strip('"')
        size = int(headers[aiohttp.hdrs.CONTENT_LENGTH])
        return namedtuple('FileInfo', ['filename', 'size'])(filename, size)

    async def download(self, session, dir, chunk_size, url):
        if url:
            async with session.get(url) as resp:
                if resp.status == 200:
                    filename, size = BandcampArtist.file_info_of_headers(resp.headers)
                    target = dir / filename
                    if target.exists():
                        existing = os.path.getsize(target)
                        if existing == size:
                            print(f'skipping {filename} ({size} == {existing})')
                            return target
                        else:
                            print(f'download and overwrite old {filename} ({size} != {existing})')
                    else:
                        print(f'download new {filename}')
                    async with aiofile.async_open(target, 'wb') as aiofb:
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            await aiofb.write(chunk)
                    print(f'{filename} done')
                    return target

    def _unzip_proc(self, dest, src):  # src needs to be last arg
        if src:
            print(f'unzipping/moving {src}')
            artist, album = src.stem.split(' - ', 1)
            artist_dir = dest / artist
            album_dir = artist_dir / album
            os.makedirs(artist_dir, exist_ok=True)
            print(artist_dir, album_dir)
            if src.suffix != '.zip':
                shutil.copy(src, artist_dir)
            else:
                shutil.unpack_archive(src, album_dir)
            print(f'DONE: unzipping {src}')

    async def unzip_coro(self, loop, pool, dest, src):
        await loop.run_in_executor(pool, self._unzip_proc, dest, src)


class MailWrapper:
    def __init__(
        self,
        email_address,
        password_file,
        mailbox,
        user=None,
        host=None,
        clear_at_aenter=True,
        clear_at_aexit=False
    ):
        self.email_address = email_address
        if user:
            inferred_user = False
            self.user = user
        if not user:
            inferred_user = True
            self.user = self.email_address
        if host:
            inferred_host = False
            self.host = host
        if not host:
            inferred_host = True
            self.host = host or self.email_address.split('@')[1]
        self.mail = aioimaplib.IMAP4_SSL(host=self.host)
        self.mailbox = mailbox
        self.password_file = password_file
        self.clear_at_aenter = clear_at_aenter
        self.clear_at_aexit = clear_at_aexit

        with open(self.password_file, 'r') as f:
            self.password = f.read()

        if VERBOSITY >= 2:
            print('MailWrapper initialized:')
            iprint(f'{self.email_address = }')
            iprint(f'{self.user = } (inferred: {inferred_user})')
            iprint(f'{self.host = } (inferred: {inferred_host})')
            iprint(f'{self.password_file = }')
            iprint(f'{self.password = }')

    async def clear_inbox(self, request_confirmation=False):
        if VERBOSITY:
            print('clearing inbox...')
        messages = await self.mail.search('SUBJECT "Your download from"')
        receipts = messages[1][0].decode('utf-8').split()
        if request_confirmation and receipts:
            click.confirm(
                f'{len(receipts)} old Bandcamp receipts in mailbox {self.mailbox} '
                '(emails with the subject "Your download from...") will be deleted. '
                'Is that okay?'
            , default=False, abort=True)
        for num in receipts:
            vvprint(f'deleting old download receipt #{num}...')
            await self.mail.store(num, '+FLAGS', '\\Deleted')
        await self.mail.expunge()

    async def idle_start(self):
        print('started idling, waiting for new mail...')
        await self.mail.idle_start(timeout=10)

    def idle_done(self):
        vvprint('idling finished.')
        self.mail.idle_done()

    async def logout(self):
        vprint('logging out...')
        return await self.mail.logout()

    async def __aenter__(self):
        vvprint('waiting for mail hello...')
        await self.mail.wait_hello_from_server()
        vvprint('got mail hello!')
        vprint('logging in to mail...')
        await self.mail.login(self.user, self.password)
        vprint('logged in!') or vvprint(f'logged in! ({self.user}, {self.password})')
        await self.mail.select(mailbox=self.mailbox)
        if self.clear_at_aenter:
            await self.clear_inbox()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.mail.has_pending_idle():
            self.idle_done()
        if self.clear_at_aexit:
            await self.clear_inbox()
        await self.logout()

    async def get_download_pages(self, artist: BandcampArtist):
        last_uid = 0
        while (emails_left := next(copy(artist.emails_left))) > 0:
            vprint(f'{emails_left} emails left')
            await self.idle_start()
            msg = await self.mail.wait_server_push()
            vvprint(f'IMAP: {msg}')
            self.idle_done()
            if 'EXISTS' in (exists := msg[0].decode('utf-8')):
                current_uid = int(exists.split()[0])
                fetch_cmd = f'{last_uid + 1}:{current_uid}'
                vvprint(f'IMAP: fetching range {fetch_cmd}')
                resp = await self.mail.fetch(fetch_cmd, 'BODY[TEXT]')
                for i in range(current_uid - last_uid):
                    msg_index = i * 3 + 1
                    msg = resp.lines[msg_index].decode('utf-8')
                    match = re.search(BandcampArtist.DOWNLOAD_LINK_PATTERN, msg)
                    vvprint(f'found match {match}')
                    if match:
                        download_page, release_id = match.groups()
                        next(artist.emails_left)
                        vprint(f'download page GOT: {download_page}')
                        yield download_page
                last_uid = current_uid
        vprint('no emails left.')


class Worker(Link):
    def __init__(self, name, worker_func, *args, no_of_workers=5, **kwargs):
        self.name = name
        self.worker_func = worker_func
        self._no_of_workers = no_of_workers
        self.args = args
        self.kwargs = kwargs

        self.output = asyncio.Queue()

        self.tasks = []

    @property
    def no_of_workers(self):
        if self.is_first:
            return 1
        else:
            return self._no_of_workers

    @no_of_workers.setter
    def no_of_workers(self, value):
        self._no_of_workers = value

    @property
    def input(self):
        if not self.is_first:
            return self.prev_link.output

    def assembly_func(self, *args, **kwargs):
        return self.worker_func(*self.args, *args, **self.kwargs, **kwargs)

    async def work(self):
        if self.is_only_one:
            return await self.assembly_func()
        elif self.is_first:
            async for product in self.assembly_func():
                await self.output.put(product)
        elif self.is_in_middle:
            while 1:
                material = await self.input.get()
                product = await self.assembly_func(material)
                await self.output.put(product)
                self.input.task_done()
        elif self.is_last:
            while 1:
                material = await self.input.get()
                product = await self.assembly_func(material)
                self.input.task_done()

    def start(self):
        for worker in self:
            for i in range(worker.no_of_workers):
                worker.tasks.append(
                    asyncio.create_task(worker.work(), name=f'{worker.name}-{i}')
                )

    async def finish(self):
        assert bool(self.tasks)

        for worker in self:
            if worker.is_first:
                await asyncio.gather(*worker.tasks)

            if not worker.is_last:
                await worker.output.join()
                print(f'worker {worker.name} finished, canceling consumer tasks...')
                for consumer in worker.next_link.tasks:
                    print(f'cancel {consumer.get_name()}')
                    consumer.cancel()

        for worker in self:
            pprint(worker.tasks)

