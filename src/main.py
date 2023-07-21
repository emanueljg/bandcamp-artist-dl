from gevent import monkey
monkey.patch_all(thread=False, select=False)
import argparse
import os
import asyncio
from concurrent.futures import ProcessPoolExecutor
from pprint import pprint
from pathlib import Path
import itertools

import lib

WORKERS_OPTIONS = {
    worker: (f'--max-{worker}-workers', f'max_{worker}_workers')
    for worker in ('page_parser', 'download', 'unzip')
}

parser = argparse.ArgumentParser(
    prog='bandcamp-artist-dl',
    description='Download all releases from a Bandcamp artist',
)
parser.add_argument(
    'artist',
    help='The artist to target',
)
parser.add_argument(
    'email-address',
    help='The email address download receipts should be sent to.'
)
parser.add_argument(
    'password-file',
    help='Path to a file containing the email password.'
)
parser.add_argument(
    '--download-dir', '-d',
    help='Where zipfiles/single files are downloaded. Defaults to the current directory.',
    default=os.getcwd(),
)
parser.add_argument(
    '--unzip-dir', '-u',
    help='Where zipfiles/single files are unzipped/copied to. Defaults to the current directory.',
    default=os.getcwd(),
)
parser.add_argument(
    '--format', '-f',
    help='The format to target.',
    choices=('flac',),
    default='flac',
)
parser.add_argument(
    '--max-workers',
    help='How many concurrent workers should be used by default for a worker. Defaults to 5.',
    type=int,
    default=5,
)
passed_first = False
for cli_option, _ in list(WORKERS_OPTIONS.values()):
    parser.add_argument(
        cli_option,
        help=f'How many concurrent {cli_option} workers should be used. Overrides --max-workers.',
        type=int,
        default=None
    )
parser.add_argument(
    '--download-chunk-size', '-z',
    help='How big the download chunks should be, in kb. Defaults to 1024 (1mB)',
    default=1024,
)
parser.add_argument(
    '--override-email-host',
    help="Optional override of the email host to connect to. Inferred from email-address if not specified.",
)
parser.add_argument(
    '--override-email-user',
    help='Optional override of the email user. Defaults to the email address.'
)
parser.add_argument(
    '--verbose', '-v',
    help="Increase verbosity of program output",
    action='count',
)


args = parser.parse_args()
lib.VERBOSITY = args.verbose
chunk_size = args.download_chunk_size * 1024


async def main():
    loop = asyncio.get_event_loop()

    artist = lib.BandcampArtist(args.artist)
    mail_wrapper = lib.MailWrapper(
        email_address=vars(args)['email-address'],
        password_file=vars(args)['password-file'],
        host=args.override_email_host,
        user=args.override_email_user,
    )

    async with mail_wrapper as mail, lib.create_session() as sesh:
        with ProcessPoolExecutor() as pool:
            artist.refresh_releases(mail.email_address)
            workers = (
                lib.Worker('mail_fetcher', mail.get_download_pages, artist),
                lib.Worker('page_parser',  lib.BandcampArtist.get_download_link_from_page, sesh),
                lib.Worker('download', artist.download,  sesh,  Path(args.download_dir), chunk_size),
                lib.Worker('unzip', artist.unzip_coro, loop, pool, Path(args.unzip_dir))
            )

            for worker, (cli, arg) in zip(workers[1:], WORKERS_OPTIONS.values()):
                worker.no_of_workers = vars(args)[arg] or args.max_workers

            assembly_line = lib.Worker.seq(*workers)
            assembly_line.start()
            artist.make_email_requests()
            await assembly_line.finish()


if __name__ == '__main__':
    asyncio.run(main())
