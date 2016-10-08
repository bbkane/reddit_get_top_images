#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reddit Get Top Images
It is a Python script which allows you to download top images from
any subreddit.

It allows you to download top pics by categories
top_from_hour
top_from_day
top_from_week
top_from_month
top_from_year
top_from_all
"""

__author__    = "nagracks"
__date__      = "18-07-2016"
__license__   = "GPL3"
__copyright__ = "Copyright © 2016 nagracks"

import os
from argparse import ArgumentParser

# External modules
import argparse
import json
import praw
import requests
import tqdm
import sys
from bs4 import BeautifulSoup


class TopImageRetreiver(object):
    """TopImageRetreiver Class

    Constructor args:
    :subreddit: str, subreddit name
    :limit: int, max limit of getting urls, default set to 15
    :period: str, period of time

    method:
    * get_top_submissions
    """

    def __init__(self, subreddit='aww', limit=15, period='w', dst=''):
        r = praw.Reddit(user_agent="Get top images")
        self.subreddit = subreddit
        self.submissions = r.get_subreddit(subreddit, fetch=True)
        self.period = period
        self.dst = dst
        self.limit = limit
        self.timeframe = {'h': self.submissions.get_top_from_hour,
                          'd': self.submissions.get_top_from_day,
                          'w': self.submissions.get_top_from_week,
                          'm': self.submissions.get_top_from_month,
                          'y': self.submissions.get_top_from_year,
                          'a': self.submissions.get_top_from_all}

    def get_top_submissions(self):
        """Get top images from selected time period

        :returns: generator, urls
        """
        # Take first lower letter of a provided time period
        # `self.period` and generate urls. If letter not in the
        # self.timeframe, gets top from the week
        get_top = self.timeframe.get(self.period)(limit=self.limit)
        return _yield_urls(get_top)


# Add a config subparser to the parser passed in
# add a --config option that overwrites the defaults
# and is overwritten by the passed in arguments
class ArgumentConfig:
    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser

        self.parser.add_argument('--config', '-c',
                                 nargs='?',
                                 metavar='FILENAME')

        # TODO: put this in subparser
        self.parser.add_argument('--write_config', '-wc',
                                 nargs='?',
                                 metavar='FILENAME',
                                 const='stdout')

    def parse_args(self, *args, **kwargs):

        # parse an empty list to get the defaults
        defaults = vars(self.parser.parse_args([]))

        passed_args = vars(self.parser.parse_args(*args, **kwargs))

        # Only keep the args that aren't the default
        passed_args = {key: value for (key, value) in passed_args.items()
                       if (key in defaults and defaults[key] != value)}

        config_path = passed_args.pop('config', None)
        if config_path:
            with open(config_path, 'r') as config_file:
                configargs = json.load(config_file)
        else:
            configargs = dict()

        # override defaults with config with passed args
        options = {**defaults, **configargs, **passed_args}

        # remove the config options from options. They're not needed any more
        # and we don't want them serialized
        options.pop('config', None)
        options.pop('write_config', None)

        # print the options (to file) if needed
        config_dst = passed_args.pop('write_config', None)
        if config_dst:
            print(json.dumps(options, sort_keys=True, indent=4))
            if config_dst != 'stdout':
                with open(config_dst, 'w', encoding='utf-8') as config_file:
                    print(json.dumps(options, sort_keys=True, indent=4), file=config_file)
                    print('Current options saved to: %r' % config_dst)
            sys.exit(0)

        return argparse.Namespace(**options)


def download_it(url, tir):
    """Download the url

    Functions used:
    * _make_path(filename, dst='')

    :url: str, downloadable url address
    :tir: cls instance of TopImageRetreiver()
    :returns: None
    """
    # Splits url to get last 10 `characters` from `in-url filename`.
    # This helps to make random filename by joining `subreddit` name and
    # `in-url` filename characters
    table = str.maketrans('?&', 'XX')
    url_chars = (url.split('/')[-1][-10:]).translate(table)
    file_name = "{name}_{chars}".format(name=tir.subreddit, chars=url_chars)
    # Make save path with condition if user has specified destination
    # path or not
    save_path = _make_path(file_name, tir.dst)
    if os.path.exists(save_path):
        print("{file_name} already downloaded".format(file_name=file_name))
    else:
        print("Downloading to {save_path}".format(save_path=save_path))
        r = requests.get(url, stream=True)
        with open(save_path, 'wb') as f:
            for chunk in (tqdm.tqdm(r.iter_content(chunk_size=1024),
                          total=(int(r.headers.get('content-length', 0)) // 1024),
                          unit='KB')):
                if chunk:
                    f.write(chunk)
                else:
                    return


def _make_path(filename, dst='~/reddit_pics'):
    """Make download path

    :filename: str, name of file which ends the path
    :dst: str, destination path, default to ''
    :returns: str, full filename path
    """
    path = os.path.expanduser(dst)

    os.makedirs(path, exist_ok=True)
    save_path = os.path.join(path, filename)
    return save_path


def _yield_urls(submissions):
    """Generate image urls with various url conditions

    Functions used:
    * _links_from_imgur(url)

    :submissions: iterable, subreddit submissions
    :returns: generator, urls
    """
    for submission in submissions:
        url = submission.url
        # Needed image extensions
        img_ext = ('jpg', 'jpeg', 'png', 'gif')
        # If url ends with needed image extension then generate urls or
        # if URL contain `/gallery/` or `/a/` in it then generate urls
        # from `_links_from_imgur(url)`.
        # or else if url is without any image extension then guess url
        # extension by getting content-type headers
        if url.endswith(img_ext):
            yield url
        elif 'imgur' in url and ('/a/' in url or '/gallery/' in url):
            for link in _links_from_imgur(url):
                yield link
        else:
            raw_url = url + '.jpg'
            try:
                r = requests.get(raw_url)
                r.raise_for_status()
                extension = r.headers['content-type'].split('/')[-1]
            except Exception as e:
                extension = ''
            if extension in img_ext:
                link = "{url}.{ext}".format(url=url, ext=extension)
                yield link


def _links_from_imgur(url):
    """Get links from imgur.com/a/ and imgur.com/gallery/

    :url: str, url contain 'imgur.com/a/' or 'imgur.com/gallery/'
    :returns: generator, links
    """
    r = requests.get(url).text
    soup_ob = BeautifulSoup(r, 'html.parser')
    for link in soup_ob.find_all('div', {'class': 'post-image'}):
        try:
            img_link = link.img.get('src')
            # img_link comes as //imgur.com/id
            # Make it https://imgur.com/id
            full_link = 'https:' + img_link
            yield full_link
        except:
            pass


def _parse_args():
    """Parse args with argparse
    :returns: args
    """
    parser = ArgumentParser(description="Download top pics from any subreddit")

    parser.add_argument('--subreddit', '-s',
                        default=['earthporn', 'cityporn'],
                        nargs='+',
                        help="Name of the subreddit")

    parser.add_argument('--period', '-p',
                        default='w',
                        choices=['h', 'd', 'w', 'm', 'y', 'a'],
                        help="[h]our, [d]ay, [w]eek, [m]onth, [y]ear, or [a]ll. Period "
                             "of time from which you want images. Default to "
                             "'get_top_from_[w]eek'")

    parser.add_argument('--limit', '-l',
                        metavar='N',
                        type=int,
                        default=15,
                        help="Maximum URL limit per subreddit. Defaults to 15")

    parser.add_argument('--destination', '-d',
                        dest='dst',
                        default='~/reddit_pics',
                        help="Destination path. By default it saves to $HOME/reddit_pics")

    # Add the config stuff
    argconfig = ArgumentConfig(parser)

    return argconfig.parse_args()


if __name__ == "__main__":
    # Handle control+c nicely
    import signal

    def exit_(signum, frame):
        os.sys.exit(1)
    signal.signal(signal.SIGINT, exit_)

    # Commandline args
    args = _parse_args()

    for subreddit in args.subreddit:
        tir = TopImageRetreiver(subreddit, args.limit, args.period, args.dst)
        for url in tir.get_top_submissions():
            download_it(url, tir)
