import argparse
import random

import certifi
import requests
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.playlist import Playlist
from plexapi.exceptions import NotFound
import tvdb_api
import re
import logging
import urllib3

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

args = None

# list of series to never include
BLACKLIST = ['Downton Abbey',
             'Poldark (2015)'
             ]


def get_args():
    parser = argparse.ArgumentParser(description='Create playlist of unwatched episodes from random shows '
                                                 'but in correct episode order.')
    parser.add_argument('--name', help='Playlist Name', default='Random Season, Next Unwatched')
    parser.add_argument('--number', '-n', help='Number of episodes to add to play list', type=int, default=10)
    group_server = parser.add_argument_group('Server Connection Method')
    group_server.add_argument('--server', action='store_true', help='Server connection Method')
    group_server.add_argument('--baseurl', '-b', help='Base URL of Server')
    group_server.add_argument('--token', '-t', help='Authentication Token')
    group_account = parser.add_argument_group('Plex Account Connection Method')
    group_account.add_argument('--account', action='store_true', help='Account Connection Method')
    group_account.add_argument('--username', '-u', help='Plex Account Username')
    group_account.add_argument('--password', '-p', help='Plex AccountPassword')
    group_account.add_argument('--resource', '-r', help='Resource Name (Plex Server Name)')
    group_account.add_argument('--tvdb-api-key', help='TVDB API Key)')
    group_behaviour = parser.add_argument_group('Episode Selection Behaviour')
    group_behaviour.add_argument('--ignore-skipped', action='store_true', help="Don't test for missing episodes")
    group_behaviour.add_argument('--randomize', action='store_true', help='Randomize selected episodes, not next unwatched')
    group_behaviour.add_argument('--include-watched', action='store_true', help='include watched episodes (use with --randomize')
    parser.add_argument('--debug', '-d', help='Debug Logging', action="store_true")
    return parser.parse_args()


def get_random_episodes(all_shows, n=10):
    show_episodes = dict()
    for show in all_shows.all():
        if args.include_watched is True:
            if args.randomize is False:
                logger.warning("Setting --randomized flag, or playlist will always start at Episode 1 for each series")
                args.randomize = True
            if args.ignore_skipped is False:
                logger.warning("Setting --ignore-skipped flag, missing episode check is not compatible with --randomized option flag")
                args.ignore_skipped = True

        if show.isWatched and args.include_watched is not True:
            continue
        if show.title in BLACKLIST:
            logger.debug(f'GET_EPISODES: Show Blacklisted: {show.title}')
            continue
        if args.include_watched is True:
            show_episodes[show.title] = show.episodes()
        else:
            show_episodes[show.title] = show.unwatched()
        # remove series 0 specials
        while show_episodes[show.title][0].seasonNumber == 0:
            season_episode = show_episodes[show.title][0].seasonEpisode
            episode_title = show_episodes[show.title][0].seasonEpisode
            show_episodes[show.title].pop(0)
            logger.debug(f'get_random_episodes: Series 0 Episode Removed '
                         f'{show.title} - {episode_title} - {season_episode}')
    next_n = []
    while len(next_n) < n:
        show_name = random.choice(list(show_episodes.keys()))
        if len(show_episodes[show_name]) >0:
            if args.ignore_skipped is False:
                if skipped_missing(all_shows.get(title=show_name), show_episodes[show_name][0]):
                    continue
            if args.randomize:
                random.shuffle(show_episodes[show_name])
            next_n.append(show_episodes[show_name].pop(0))
        else:
            logger.debug(f'GET_EPISODES: No more unwatched episodes for {show_name}')
            continue
    return next_n


def tvdb_season_count(show, season):
    tvdb_id = None
    try:
        logger.debug(f'TVDB: Getting show "{show.title}"')
        tvdb_id = int(re.search('thetvdb://([0-9]+)?', show.guid).group(1))
        if args.tvdb_api_key is None:
            raise RuntimeError(f'TVDB now requires an API key.  Instructions on how to set it up are here:\n\n'
                               f'https://koditips.com/create-tvdb-api-key-tv-database/')
        tv = tvdb_api.Tvdb(language='en', apikey=args.tvdb_api_key)
        season_list = tv[tvdb_id][season]
        logger.debug(f'TVDB: Previous Season Length = {len(season_list)}')
        return len(season_list)
    except tvdb_api.tvdb_seasonnotfound:
        logger.warning(f'TVDB: Unable to look up "{show.title}" ({tvdb_id})')
        return None


def skipped_missing(show, episode):
    try:
        season_num = episode.seasonNumber
        episode_num = episode.index

        if episode.index > 1:
            logger.debug(f'SKIP_CHECK: Check same Season for {show.title} S{season_num}E{episode_num-1}')
            show.get(season=episode.seasonNumber, episode=episode.index-1)
            logger.debug(f'SKIP_CHECK: Passed')
            return False
        elif episode.seasonNumber > 1:
            previous_season_count = tvdb_season_count(show, season_num - 1)
            if previous_season_count is None:
                return False
            logger.debug(f'SKIP_CHECK: Check previous Season for {show.title} S{season_num-1}E{previous_season_count}')
            # check last episode of previous season
            show.get(season=episode.seasonNumber - 1, episode=previous_season_count)
            logger.debug(f'SKIP_CHECK: Passed')
            return False
        else:
            logger.debug(f'SKIP_CHECK: First Episode of First Season. {show.title} {season_num}')
            return False
    except NotFound:
        logger.info(f'SKIP_CHECK: Previous Episode not Found for {show.title} S{season_num}E{episode_num}')
        return True


def main():
    global args
    args = get_args()
    plex = None
    if args.debug:
        logger.setLevel(logging.DEBUG)
    if args.account:
        # ## Connect via Account
        account = MyPlexAccount(args.username, args.password)
        plex = account.resource(args.resource).connect()
    elif args.server:
        # ## Connect via Direct URL
        baseurl = args.baseurl
        token = args.token
        session = requests.session()
        session.verify = False
        logger.debug(session.verify)
        plex = PlexServer(baseurl, token, session)
    else:
        exit(1)

    all_shows = plex.library.section('TV Shows')

    # shows = get_unwatched_shows(all_shows.all())
    episodes = get_random_episodes(all_shows, n=args.number)
    for episode in episodes:
        season_episode = episode.seasonEpisode
        # skipped = skipped_missing(all_shows.get(title=episode.grandparentTitle), episode)
        print(f'{episode.grandparentTitle} - {episode.parentTitle} - '
              f'{episode.index}. {episode.title}')

    # playlist = Playlist(plex, )
    try:
        plex.playlist(title=args.name).delete()
    except NotFound as e:
        logger.debug(f"Playlist {args.name} does not exist to delete.")
    Playlist.create(server=plex, title=args.name, items=episodes)


if __name__ == '__main__':
    main()
