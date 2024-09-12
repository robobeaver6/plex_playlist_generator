#!/usr/bin/python3.8

import argparse
import random

import certifi
import requests
import time

#Additional import
import random
import xmltodict

from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.playlist import Playlist
from plexapi.exceptions import NotFound
from plexapi.exceptions import Unauthorized
from plexapi.exceptions import BadRequest

import tvdb_api
import re
import logging
import urllib3

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

args = None

#string seperators
colon = ':'
comma = ','

# list of series to never include
BLACKLIST = ['Downton Abbey',
             'Poldark (2015)'
             ]


##################################################################################################################################################
###                                                       Before running this script                                                           ###
##################################################################################################################################################
#  [Requirements]                                                                                                                                #
#       The Library section names (same library type) for you're plex libraries must be unique.                                                  #
#                                                                                                                                                #
#                                                                                                                                                #
#  [ChangeLog]                                                                                                                                   #
#       07/19/2024 - [Improvements] Greatly reduced runtime of the script by reducing number of calls to plex                                    #
#                    by generating the playlist and filling it at the same time.                                                                 #
#                  - [Added Feature] Additional episodes of the same series will increment within the playlist.                                  #
#                  - [Added Feature] Added blacklisting for Movie Selections.                                                                    #
#                  - [Bug Fixes] Fixed a bug where passing a value into the --number argument that was larger than                               #
#                    total possible number of media in the provided libraries would cause an infinite loop.                                      #
#                  - [Removed] Removed default values for excludusion list (--exclude-library).                                                  #
#                  - [Bug Fixes] Fixed a bug causing index out of bounds errors                                                                  #
#                    in the code for excluding special episodes/seasons.                                                                         #
#                  - [Removed] Removed no longer needed code.                                                                                    #
#                                                                                                                                                #
#       07/20/2024 - [Bug Fixes] Fixed a bug that caused the special episodes removal code to not work properly                                  #
#                    when all episodes after special episodes have been watched.                                                                 #
#                                                                                                                                                #
#       07/27/2024 - [Improvements] Updated script to remove usage of plex elements (I.E. <MyPlexUser:123456789:TestUser>) data using .split()   #
#                                                                                                                                                #
#       07/28/2024 - [Improvements] Added more error checking when selecting all Home Users. Added exceptions for Bad Requests.                  #
#                                                                                                                                                #
#       07/31/2024 - [Bug Fixes] Fixed a bug that caused home users to not be selected in certain instances.                                     #
#                                                                                                                                                #
#       09/10/2024 - [Bug Fixes] Fixed a bug that resulted in a NameError when the provided users are invalid.                                   #
#                  - [Added Feature] Resource argument is now required for server connection method (due to the switching of users).             #
#                                                                                                                                                #
#       09/11/2024 - [Bug Fixes] Fixed a bug that caused an error when all movies or movie selections were selected with "--include-watched"     #
#                    as a paramater an error would occur.                                                                                        #
#                  - [Bug Fixes] Fixed a bug where some movies would be prevented from being added to a playlist due to an already added item    #
#                    being attemptedly added multiple times; however, since it is already in the playlist it was not added again                 #
#                    but still caused the playlist count to be lower than expected at times due to this.                                         #
#                  - [Enhancements] Added a check to make sure a user entered either a --adminuser argument or a --homeusers argument.           #
#                  - [Enhancements] Added the ability to purge a playlist without providing the --select-library, --allshows,                    #
#                    or --allmovies arguments.                                                                                                   #
##################################################################################################################################################



def get_args():
    parser = argparse.ArgumentParser(description='Create playlist of unwatched episodes from random shows '
                                                 'but in correct episode order.')
    parser.add_argument('--name', help='Playlist Name', default='[Auto-Generated]')
    parser.add_argument('--number', '-n', help='Number of episodes or Movies to add to play list', type=int, default=10)
    parser.add_argument('--debug', '-d', help='Debug Logging', action="store_true")
    group_server = parser.add_argument_group('Server Connection Method')
    group_server.add_argument('--server', action='store_true', help='Server connection Method')
    group_server.add_argument('--baseurl', '-b', help='Base URL of Server (I.E \"http://10.1.1.8:32400\" or \"https://your.domain.com:32400\")', type=str, default="http://localhost:32400")
    group_server.add_argument('--token', '-t', help='Authentication Token')
    group_account = parser.add_argument_group('Plex Account Connection Method')
    group_account.add_argument('--account', action='store_true', help='Account Connection Method')
    group_account.add_argument('--username', '-u', help='Plex Account Username')
    group_account.add_argument('--password', '-p', help='Plex Account Password')
    group_account.add_argument('--resource', '-r', help='Resource Name (Plex Server Name)')
    group_account.add_argument('--tvdb-api-key', help='TVDB API Key)')
    group_behavior = parser.add_argument_group('Episode/Movie Selection Behavior')
    group_behavior.add_argument('--ignore-skipped', action='store_true', help="Don't test for missing episodes", default=True)
    group_behavior.add_argument('--randomize', action='store_true', help='Randomize selected episodes, not next unwatched')
    group_behavior.add_argument('--include-watched', action='store_true', help='include watched movies or episodes (use with --randomize)')  
    group_libraries = parser.add_argument_group('Library Selection Behavior')    
    group_libraries.add_argument('--allshows', help='Grab All Shows in all Library sections From Plex', action='store_true', default=False)
    group_libraries.add_argument('--allmovies', help='Grab All Movies in all Library sections From Plex', action='store_true', default=False)
    group_libraries.add_argument('--select-library', '-l', help='Choose between library sections of both TV Shows or Movies to build a playlist from (comma seperated within quotes if multiple users)')
    #The Exclude data will be used in conjuction with either --allshows or --allmovies
    group_libraries.add_argument('--exclude-library', '-e', help='Comma seperated list (if selecting multiple users) of sections to exclude (I.E. "Test Videos,Workout,Home Videos" ) there should be no space between the comma and the first character of the next value', type=str, default="")
    group_libraries.add_argument('--purge', help='Remove a playlist from plex for the provided user(s)', action='store_true', default=False)  
    group_users = parser.add_argument_group('User Profile Selection')    
    #Used for Entering the Admin user(s) 
    group_users.add_argument('--adminuser', '-a', help='Generate playlist for the Plex Admin user profile name that was used to login.', action='store_true', default=False)
    #The Plex Profile Names for the home users
    group_users.add_argument('--homeusers', help='Generate playlist for the provided Plex home users (comma seperated within quotes if multiple users). For all plex home users type \"all\"', type=str)
    

    return parser.parse_args()


def get_random_episodes_or_movies(plex, all_provided_sections, requested_playlist_items=10):

    #The name of the library sections type IE (MovieSection, ShowSection, MusicSection, PhotoSection) its used to query the type of data too grab from the plex API
    getMovieSection = 'MovieSection'
    getShowSection = 'ShowSection'
    
    #use to query and find show sections from the for command if statement
    getShowSectionSearcher = '<' + getShowSection + colon
    getMovieSectionSearcher = '<' + getMovieSection + colon

    all_shows_or_movies_from_provided_sections = list()
    all_shows_from_provided_sections = list()
    all_movies_from_provided_sections = list()
    
    #Used to determine whether to append to a empty library section all content, or add to concatinate an existing set of data
    count = 0
    

    for provided_section in all_provided_sections:
        if count == 0:
            if(args.include_watched == True):
                all_shows_or_movies_from_provided_sections = plex.library.section(provided_section).all()
                logger.debug(f'\nall_shows_or_movies_from_provided_sections[{count}] = {all_shows_or_movies_from_provided_sections}')
            else:
                all_shows_or_movies_from_provided_sections = plex.library.section(provided_section).all(unwatched=True)
                logger.debug(f'\nall_shows_or_movies_from_provided_sections[{count}] = {all_shows_or_movies_from_provided_sections}')
                
            if getShowSectionSearcher in str(plex.library.section(provided_section)):
                all_shows_from_provided_sections = plex.library.section(provided_section).all()
                
            elif getMovieSectionSearcher in str(plex.library.section(provided_section)):
                if(args.include_watched == True):
                    logger.debug(f'\nIncluding Watched Movies...\n')
                    all_movies_from_provided_sections = plex.library.section(provided_section).all()
                    
                else:
                    logger.debug(f'\nExcluding Watched Movies...\n')
                    all_movies_from_provided_sections = plex.library.section(provided_section).all(unwatched=True)
                
            count += 1
        else:
            if(args.include_watched == True):
                all_shows_or_movies_from_provided_sections = all_shows_or_movies_from_provided_sections + plex.library.section(provided_section).all()
                logger.debug(f'\nall_shows_or_movies_from_provided_sections[{count}] = {all_shows_or_movies_from_provided_sections}')
            else:
                all_shows_or_movies_from_provided_sections = all_shows_or_movies_from_provided_sections + plex.library.section(provided_section).all(unwatched=True)
                logger.debug(f'\nall_shows_or_movies_from_provided_sections[{count}] = {all_shows_or_movies_from_provided_sections}')

   
            if getShowSectionSearcher in str(plex.library.section(provided_section)):
                all_shows_from_provided_sections = all_shows_from_provided_sections + plex.library.section(provided_section).all()
                logger.debug(f'\nall_shows_from_provided_sections = {all_shows_from_provided_sections}')
                
            elif getMovieSectionSearcher in str(plex.library.section(provided_section)):
                if(args.include_watched == True):
                    #If the user did select to include watched movies with --include-watched
                    logger.debug(f'\nIncluding Watched Movies...\n')
                    all_movies_from_provided_sections = all_movies_from_provided_sections + plex.library.section(provided_section).all()
                    
                else:
                    #If the user did not select to include watched movies with --include-watched
                    logger.debug(f'\nExcluding Watched Movies...\n')
                    all_movies_from_provided_sections = all_movies_from_provided_sections + plex.library.section(provided_section).all(unwatched=True)

                logger.debug(f'\nall_movies_from_provided_sections = {all_movies_from_provided_sections}')
                
            count += 1


    if len(all_shows_from_provided_sections) > 0:
        show_episodes = dict()
        for show in all_shows_from_provided_sections:
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
                #Grab Watched Episodes but ignore Season 0 (Specials)
                show_episodes[show.title] = show.episodes(parentIndex__gt=0)
            else:
                show_episodes[show.title] = show.unwatched()
              

            #Get the Season number of the Show
            getSeasonNumber = show_episodes[show.title][0].seasonNumber
            
            # remove series 0 specials
            while getSeasonNumber == 0:
                #If the Season Number is 0 remove it from the list of shows and episodes
                if getSeasonNumber == 0:
                    season_episode = show_episodes[show.title][0].seasonEpisode
                    episode_title = show_episodes[show.title][0].title

                    logger.debug(f'get_random_episodes: Series 0 Episode Removed '
                                 f'{show.title} - {season_episode} - {episode_title} \n')
                
                    show_episodes[show.title].pop(0)
    
                logger.debug(f'getSeasonNumber [before] = {getSeasonNumber}')

                try:
                    #The position of the new data after applying the pop has not been tested to see if it is a special season yet.
                    # So rewind the Season count to the beginning in order to test it in the next go around.
                    # When the new data's season number is equal to 0, it will run the loop again, otherwise it will exit the loop for this iteration.
                    getSeasonNumber = show_episodes[show.title][0].seasonNumber
                    logger.debug(f'getSeasonNumber [after] = {getSeasonNumber}')
                    
                except IndexError as e:
                    #If the Index is out of range (this can occur if the seasons after the special seasons have all been watched).
                    print(f'\nIndex that Procceeds \"{show.title} - {season_episode} - {episode_title}\" is out of Range :: {e}\n')
                    break


    #Used to randomly choose between show or movies if both are supplied
    get_show = "show"
    get_movie = "movie"
    mediaTypeSelector = None
    get_show_or_movie = [ get_show, get_movie ]
    
    #Used to determine if the show or movies was empty. If not then they are valid selections for get_show_or_movie variable
    shows_available = False
    movies_available = False

    
    #If the playlist item count passed in by the user is larger than the total item count of the selected content then update the value of the playlist to be that of the maximum number of contents passed in to the script
    if(len(all_shows_or_movies_from_provided_sections)) < requested_playlist_items:
        requested_playlist_items = len(all_shows_or_movies_from_provided_sections)
        
    #Takes the initial value of the  
    length_of_requested_playlist_items = requested_playlist_items

    playlist = []
    while len(playlist) < requested_playlist_items:
        #Using The list of Shows
        if len(all_shows_from_provided_sections) > 0:
            show_or_movie_name = random.choice(list(show_episodes.keys()))
            shows_available = True
            
        #Using The list of Movies.
        if (all_movies_from_provided_sections):                
            show_or_movie_name = random.choice(all_movies_from_provided_sections)
            movies_available = True
        
        if(shows_available == True) and (movies_available == True):
            mediaTypeSelector = random.choice(get_show_or_movie)
            
        elif(shows_available == False) and (movies_available == True):
            mediaTypeSelector = get_movie
            
        elif(shows_available == True) and (movies_available == False):
            mediaTypeSelector = get_show
        
        else:
            print(f'No available movies or TV Shows available to choose from.')
            exit(1)

        #For TV Shows Only
        if (mediaTypeSelector == get_show):
            show_name = random.choice(list(show_episodes.keys()))
            
            if len(show_episodes[show_name]) >0:
                if args.ignore_skipped is False:
                    if skipped_missing(all_shows.get(title=show_name), show_episodes[show_name][0]):
                        continue
                if args.randomize:
                    random.shuffle(show_episodes[show_name])
                    
                playlist.append(show_episodes[show_name].pop(0))

            else:
                logger.debug(f'GET_EPISODES: No more unwatched episodes for {show_name}')
                continue
        
        #For Movies Only      
        elif (mediaTypeSelector == get_movie):
            
            #If a list of Blacklisted Media was supplied
            if(BLACKLIST != None):
                
                total_blacklisted_item_count = len(BLACKLIST)
                blacklistCounter = 0
        
                #Try 3 times to add data without it being blacklisted before giving up
                try_at_least_three_times = 3

                #Three Consecutive attempts. Used for determining how many times consecutively something has been tried to be blackllisted and skipped in the while loop
                three_consecutive_attempts = 1
                increment_consecutive_count_one = False
                increment_consecutive_count_two = False
                increment_consecutive_count_three = False

            
                #if all_movies.title in BLACKLIST:
                for movie in all_movies_from_provided_sections:
                    if movie.title in BLACKLIST:
                    
                        logger.debug(f'GET_EPISODES: Movie Blacklisted: {movie.title}')
                        blacklistCounter += 1

                        #If the number of times we reach here is greater than BLACKLISTED items count, we are likely in a continuous loop so break pout
                        if (three_consecutive_attempts >= try_at_least_three_times) and (blacklistCounter > total_blacklisted_item_count):
                            print(f'Too many attempts being Blacklisted, exiting the loop... ')
                            break
                        
                        else:
                            #if (increment_consecutive_count_one == False):
                            if (increment_consecutive_count_one == False):
                                increment_consecutive_count_one = True
                                three_consecutive_attempts += 1
                                continue
                                
                            elif (increment_consecutive_count_two == False):
                                increment_consecutive_count_two = True
                                three_consecutive_attempts += 1
                                continue
                            elif (increment_consecutive_count_three == False):
                                increment_consecutive_count_three = True
                                three_consecutive_attempts += 1
                                print(f'Too many attempts being Blacklisted, exiting the loop... ')
                                break
                        
                    else:
                        #Reset All counters since it was not either not a blacklisted media item or the blacklist counter was not consecutive
                        three_consecutive_attempts = 0
                        increment_consecutive_count_one = False
                        increment_consecutive_count_two = False
                        increment_consecutive_count_three = False

            if(args.include_watched == True):
                #If the user selects to include watched movies
                logger.debug(f'\nIncluding Watched Movies...\n')
                movie = random.choice(all_movies_from_provided_sections)
                
                #Check if the Movie is already in the list, if it is continue
                if (movie in playlist) and (len(playlist) < requested_playlist_items):
                    continue

            else:
                #If the user did not select to include watched movies with --include-watched
                logger.debug(f'\nExcluding Watched Movies...\n')
                movie = random.choice(all_movies_from_provided_sections)

                #Check if the Movie is already in the list, if it is continue
                if (movie in playlist) and (len(playlist) < requested_playlist_items):
                    continue

            #Append unique movies
            playlist.append(movie)
    return playlist



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


def delete_playlist(plex, account, playlistName):
    try:
        print(f'deleting playlist \"{playlistName}\"...')
        plex.playlist(title=playlistName).delete()
        print(f'\nplaylist \"{playlistName}\" deleted successfully.\n')
        
        #If the user is deleting all instances of the playlist then sleeps are added to avoid hitting the too many request exception
        if(args.purge):
            time.sleep(5)

    except NotFound:
        logger.debug(f"Playlist {playlistName} does not exist to delete.")
        
        #If the user is deleting all instances of the playlist (whether it exist or not on a users account) then sleeps are added to avoid hitting the too many request exception
        if(args.purge):
            time.sleep(10)

    except BadRequest as e:
        print(f'\nError - BadRequest: {e}\n')
        exit(1)


#Loops through and builds the playlist
#Arguments are the plex connection, the name of the user we are acting as for playlist generation, the formatted plex library sections, and the Excluded List of Library Sections
def build_playlist(plex, userName, plex_refined_library_sections, selectionsToExclude_List):  
    #The plex_refined_library_sections is the library sections after removing the excluded list
    #The librarySelection is the selected library that was passed in whether from using --allshows, --allmovies, or --selectlibrary

    #number of Media items added to the library.
    libraryCount = 0 
    
    #Use to compare if the Video item is a plex Movie object or a plex Show object
    getShow = "episode"
    getMovie = "movie"
    
    #Check to see if any of the selected Library names supplied are valid. If not then Error out.
    if(len(plex_refined_library_sections) <= 0):
        print(f'\nError - Unable to find any valid library selections from your entry.\n')
        exit(1)


    #If the user selected libraries with the --selectlibrary argument
    if(args.select_library != None):
        randomSelectedLibrary = random.choice(plex_refined_library_sections)
    else:
        randomSelectedLibrary = random.choice(plex_refined_library_sections)


    getPlexLibrarySection = plex.library.section(randomSelectedLibrary)

    randomSelectedLibrary = random.choice(plex_refined_library_sections)
    
    logger.debug(f'\nSelected Library: \"{randomSelectedLibrary}\"\n')

    getPlexLibrarySection = plex.library.section(randomSelectedLibrary)
    logger.debug(f'getPlexLibrarySection = {getPlexLibrarySection}')       
        
    if (args.select_library != None) or ((args.allshows == True) and (args.allmovies == True)):

        episode_or_movie = get_random_episodes_or_movies(plex, plex_refined_library_sections, args.number)
        
        try:
            #If a playlist with the same name already exist, delete it
            if plex.playlist(title=args.name):
                print(f'The playlist "{args.name}" already exist.')
                print(f'deleting playlist "{args.name}" ...')
                plex.playlist(title=args.name).delete()

        except NotFound as e: 
            logger.debug(f"Playlist {args.name} does not exist to delete.")

        #Create Playlist, and fill it immediately 
        createdPlaylist = Playlist.create(server=plex, title=args.name, items=episode_or_movie, section=None, smart=False, limit=None, libtype=None, sort=None, filters=None, m3ufilepath=None)
        
        #If the created playlist was not actually created, Error and exist the script.
        if(not createdPlaylist):
            print(f'Error - Unable to generate the Playlist \"{args.name}\"')
            exit(1)

        #Print the Episode added to the playlist
        for episode_movie in episode_or_movie:
            #If the media type is show then print the output for the show details
            if episode_movie.TYPE in getShow:
                print('\n-----------------------------------')
                print('[RANDOMIZED EPISODES]')
                print(f'Username: {userName}')
                print(f'Library Selection: {episode_movie.librarySectionTitle}')  

                #If no library sections are to be excluded print None for the excluded Library sections
                if (not selectionsToExclude_List) or (args.exclude_library == ''):
                    print(f'\nExcluded Library Sections: None')

                else:
                    #Remove Empty strings from the list
                    selectionsToExclude_List = list(filter(None, selectionsToExclude_List))
                    print(f'\nExcluded Library Sections: {selectionsToExclude_List}')
        
                season_episode = episode_movie.seasonEpisode
                logger.debug(f'\n\nEpisode [label] = {(episode_movie.TYPE)}\n\n')
                print(f'\nAdded to Playlist [{args.name}]: \"{episode_movie.grandparentTitle} - {episode_movie.parentTitle} - '
                      f'Ep.0{episode_movie.index} - {episode_movie.title}\"')
                  
                libraryCount += 1
                print(f'Number of Items in Playlist: {libraryCount}\n')
                
            #If the media type is movie then print the output for the movie details
            elif episode_movie.TYPE in getMovie:
                print('\n-----------------------------------')
                print('[RANDOMIZED MOVIES]')
                print(f'Username: {userName}')
                print(f'Library Selection: {episode_movie.librarySectionTitle}')
                
                #If no library sections are to be excluded print None for the excluded Library sections
                if (not selectionsToExclude_List) or (args.exclude_library == ''):
                    print(f'\nExcluded Library Sections: None')

                else:
                    #Remove Empty strings from the list
                    selectionsToExclude_List = list(filter(None, selectionsToExclude_List))
                    print(f'\nExcluded Library Sections: {selectionsToExclude_List}')

                logger.debug(f'\n\nMovie [label] = {(episode_movie.TYPE)}\n\n')
                print(f'\nAdded to Playlist [{args.name}]: \"{episode_movie.title}\"')
                
                libraryCount += 1
                print(f'Number of Items in Playlist: {libraryCount}\n')


    #For TV Shows Only
    elif (args.allshows == True) and (args.allmovies == False):
        episode_or_movie = get_random_episodes_or_movies(plex, plex_refined_library_sections, args.number)
              
        try:
            #If a playlist with the same name already exist, delete it
            if plex.playlist(title=args.name):
                print(f'The playlist "{args.name}" already exist.')
                print(f'deleting playlist "{args.name}" ...')
                plex.playlist(title=args.name).delete()

        except NotFound as e: 
            logger.debug(f"Playlist {args.name} does not exist to delete.")
            
            
        #Create Playlist, and fill it immediately 
        createdPlaylist = Playlist.create(server=plex, title=args.name, items=episode_or_movie, section=None, smart=False, limit=None, libtype=None, sort=None, filters=None, m3ufilepath=None)
        
        #If the created playlist was not actually created, Error and exist the script.
        if(not createdPlaylist):
            print(f'Error - Unable to generate the Playlist \"{args.name}\"')
            exit(1)
        

        #Print the Episode added to the playlist
        for episode_movie in episode_or_movie:
            #If the media type is show then print the output for the show details
            if episode_movie.TYPE in getShow:
                print('\n-----------------------------------')
                print('[RANDOMIZED EPISODES]')
                print(f'Username: {userName}')
                print(f'Library Selection: {episode_movie.librarySectionTitle}')  

                #If no library sections are to be excluded print None for the excluded Library sections
                if (not selectionsToExclude_List) or (args.exclude_library == ''):
                    print(f'\nExcluded Library Sections: None')

                else:
                    #Remove Empty strings from the list
                    selectionsToExclude_List = list(filter(None, selectionsToExclude_List))
                    print(f'\nExcluded Library Sections: {selectionsToExclude_List}')
        
                logger.debug(f'\n\nEpisode [label] = {(episode_movie.TYPE)}\n\n')
                season_episode = episode_movie.seasonEpisode      
                print(f'\nAdded to Playlist [{args.name}]: \"{episode_movie.grandparentTitle} - {episode_movie.parentTitle} - '
                      f'Ep.0{episode_movie.index} - {episode_movie.title}\"')
                  
                libraryCount += 1
                print(f'Number of Items in Playlist: {libraryCount}\n')

           
    #For Movies Only      
    elif (args.allshows == False) and (args.allmovies == True):
        episode_or_movie = get_random_episodes_or_movies(plex, plex_refined_library_sections, args.number)
        
        try:
            #If a playlist with the same name already exist, delete it
            if plex.playlist(title=args.name):
                print(f'The playlist "{args.name}" already exist.')
                print(f'deleting playlist "{args.name}" ...')
                plex.playlist(title=args.name).delete()

        except NotFound as e: 
            logger.debug(f"Playlist {args.name} does not exist to delete.")
            
            
        #Create Playlist, and fill it immediately 
        createdPlaylist = Playlist.create(server=plex, title=args.name, items=episode_or_movie, section=None, smart=False, limit=None, libtype=None, sort=None, filters=None, m3ufilepath=None)
        
        #If the created playlist was not actually created, Error and exist the script.
        if(not createdPlaylist):
            print(f'Error - Unable to generate the Playlist \"{args.name}\"')
            exit(1)

        
        #Print the Episode added to the playlist
        for episode_movie in episode_or_movie:
            #If the media type is movie then print the output for the movie details
            if episode_movie.TYPE in getMovie:
                print('\n-----------------------------------')
                print('[RANDOMIZED MOVIES]')
                print(f'Username: {userName}')
                print(f'Library Selection: {episode_movie.librarySectionTitle}')
                
                #If no library sections are to be excluded print None for the excluded Library sections
                if (not selectionsToExclude_List) or (args.exclude_library == ''):
                    print(f'\nExcluded Library Sections: None')

                else:
                    #Remove Empty strings from the list
                    selectionsToExclude_List = list(filter(None, selectionsToExclude_List))
                    print(f'\nExcluded Library Sections: {selectionsToExclude_List}')

                logger.debug(f'\n\nMovie [label] = {(episode_movie.TYPE)}\n\n')
                print(f'\nAdded to Playlist [{args.name}]: \"{episode_movie.title}\"')
                
                libraryCount += 1
                print(f'Number of Items in Playlist: {libraryCount}\n')



def create_playlist(plex, account):
    #Group All Shows in different Library Sections together (does not include excluded)
    #Group All Movies in different Library Sections together  (does not include excluded)

    #If the user passed something into the argument selectlibrary to select their desired libraries
    if(args.select_library != None):
        #Use a regex to remove spaces between commas in the users entry.
        space_remover_regex = r'(^\s+|\s*,\s*|\s+$)'
        getLibrarySection = re.sub(space_remover_regex,',', args.select_library)
        librarySelection_List = (getLibrarySection).split(comma)

    #The name of the library sections type IE (MovieSection, ShowSection, MusicSection, PhotoSection) its used to query the type of data too grab from the plex API
    getMovieSection = 'MovieSection'
    getShowSection = 'ShowSection'
    #These two are only used for exluding sections within the script since they are neither Shows or Movies
    getMusicSection = 'MusicSection'
    getPhotoSection = 'PhotoSection'


    allSections_List = list()
    #Loop through each plex library section and return the title and append it to a list of library section names
    for section in plex.library.sections():
        #get the title element from the library section
        allSections_List.append(section.title)
    
    #for the section in allSections (converted to String):
    allShowSections_String = str()
    allMovieSections_String = str()
    
    
    #Use a regex to remove spaces between commas in the users entry.
    space_remover_regex = r'(^\s+|\s*,\s*|\s+$)'
    getExcludeSection = re.sub(space_remover_regex,',', args.exclude_library)
    #Split the selections entered by the user by commas (using a regex to remove spaces between comma seperated entries)
    selectionsToExclude_List = (getExcludeSection).split(comma)

    #Obtain All Library Selections (and format it to only have the names of the libraries as they appear in Plex)
    plex_all_library_sections = allSections_List

    
    #If the user Selected The library selection (--select-library), default plex_all_tv_and_movie_library_sections_minus_exluded to a Default of an empty list in order to build the list from the users entry
    if (args.select_library != None):
        plex_all_tv_and_movie_library_sections_minus_exluded = list()
        
        #Used to build a list of everything that was excluded by using the --selectedlibrary.
        #Anything not selected will be added to this exclusion list.
        selectionsToExcludeBasedOnWhatUserSelected_List = list()
        
    #If the user did NOT Select The library selection, default plex_all_tv_and_movie_library_sections_minus_exluded to a Default of the full list of sections in order to remove from the list anything that is in the excluded list
    else:
        plex_all_tv_and_movie_library_sections_minus_exluded = list()
        
        #Used to build a list of everything that was excluded 
        #Anything added to the original exclusion list plus additional exclusions based on whether --allmovies or --allshows were used.
        selectionsToExcludeBasedOnWhatUserSelected_List = selectionsToExclude_List
    
    
    #use to query and find show sections from the for command if statement
    getShowSectionSearcher = '<' + getShowSection + colon
    getMovieSectionSearcher = '<' + getMovieSection + colon
    
    #Use to Avoid Music or Photo section content
    getMusicSectionSearcher = '<' + getMusicSection + colon
    getPhotoSectionSearcher = '<' + getPhotoSection + colon
    
    #Used to determine if a comma should be placed between the string concatination
    countShows = 0
    countMovies = 0

    #Used to hold a list of only Show sections
    allShowSectionsFull_List = list()
    #Used to hold a list of only Movies sections
    allMovieSectionsFull_List = list()
    #Used to hold a list of only Music sections
    allMusicSectionsFull_List = list()
    #Used to hold a list of only Photo sections
    allPhotoSectionsFull_List = list()
    
    
    #Build the Full Library Sections for TV Shows and also Movies
    for section in plex.library.sections():
        #Grab the List of all possible Shows sections
        if getShowSectionSearcher in str(section):
            allShowSectionsFull_List.append(section.title)
            #if(args.allshows == True):
            if(args.select_library == None):
                plex_all_tv_and_movie_library_sections_minus_exluded.append(section.title)

        #Grab the List of all possible Movies sections
        elif getMovieSectionSearcher in str(section):
            allMovieSectionsFull_List.append(section.title)
            
            if(args.select_library == None):
                plex_all_tv_and_movie_library_sections_minus_exluded.append(section.title)
            
        #Grab the List of all possible Music sections
        elif getMusicSectionSearcher in str(section):
            allMusicSectionsFull_List.append(section.title)
            
        #Grab the List of all possible Photos sections
        elif getPhotoSectionSearcher in str(section):
            allPhotoSectionsFull_List.append(section.title)
            
        else:
            print(f'\n\"{section}\" is NOT a result of the 4 possible Sections (MovieSection, ShowSection, MusicSection, PhotoSection)!\n')
            logger.warning(f'\nIf a new Plex Library Section Type was added, this script may need to be updated!\n')
            
    
    #Holds the Formatted Array for both All Movies and Shows only 
    allSections_Formatted_List = list()
    movieSections_Formatted_List = list()
    tvShowsSections_formatted_List = list()
    
    get_library_sections = plex.library.sections()
    
    #Formatted to only contain the Names of the library sections
    for getSection_data in get_library_sections:        
        if getShowSectionSearcher in str(getSection_data):
            tvShowsSections_formatted_List.append(getSection_data.title)
            
        elif getMovieSectionSearcher in str(getSection_data):
            movieSections_Formatted_List.append(getSection_data.title)
            
        elif getMusicSectionSearcher in str(getSection_data):
            logger.debug(f'\nThis script does not currently support the library section type \"{getMusicSection}\" for section \"{getSection_data.title}\".\n')
            
        elif getPhotoSectionSearcher in str(getSection_data):
            logger.debug(f'\nThis script does not currently support the library section type \"{getPhotoSection}\" for section \"{getSection_data.title}\".\n')
            
        else:
            print(f'\nError - Unknown section type for section \"{getSection_data.title}\".\n')
            exit(1)
            

    logger.debug(f'tvShowsSections_formatted_List = {tvShowsSections_formatted_List}')
    logger.debug(f'movieSections_Formatted_List = {movieSections_Formatted_List}')

    
    getAllShows = args.allshows
    getAllMovies = args.allmovies
    
    loopCount = 0  
    
    for library in plex_all_library_sections:

        #Use a regex to match exactly the library sections, otherwise it will find any library containing the library variable 
        library_exact_matcher_regex = '^' + re.escape(library) + '$'
        library_regex = re.compile(library_exact_matcher_regex)

        #Build a Regex from the library value in the loop, and check if the library is in the list of Excluded Libraries from command line "--exclude-library" argument
        foundMatchInExclude = list(filter(library_regex.match, selectionsToExclude_List))
        
        #if the library is in the combined list of movie libraries or TV Libraries
        foundInLibrarySectionMovieOrShow = list(filter(library_regex.match, plex_all_tv_and_movie_library_sections_minus_exluded))
 
        #If the list of excluded libraries is equal to the all library sections
        if set(plex_all_library_sections) == set(selectionsToExclude_List):
            print(f'ERROR - All Library Sections were selected to be excluded')
            exit(1)
        #If the list of library selections by the user from the commandline is equal to the list of libraries to exclude
        elif (args.select_library != None) and (set(librarySelection_List) == set(selectionsToExclude_List)):
            print(f'ERROR - All Selected Libraries entered were selected to be excluded')
            exit(1)


        #If the user is selecting there libraries manually then remove anything not in the selection    
        if (args.select_library != None):

            #Use Regex to find the exact match of the section
            foundMatchInUSerSelection = list(filter(library_regex.match, librarySelection_List))
            
            if not foundMatchInExclude and not foundMatchInUSerSelection:
                logger.debug(f'Adding library \"{library}\" to List of selectionsToExcludeBasedOnWhatUserSelected_List')

                #Add the library to the Full list of what was excluded library sections for everything that is not in --selectlibrary argument passed in by the user
                selectionsToExcludeBasedOnWhatUserSelected_List.append(library)
                
            # #if library is one of the selected sections requested by the user, add it.
            elif foundMatchInUSerSelection:
                #If it this is one of the entries entered by the user on the command line (--select-library)
                logger.debug(f'Adding {library} to plex_all_tv_and_movie_library_sections_minus_exluded ...')
                plex_all_tv_and_movie_library_sections_minus_exluded.append(library)

            else:
                logger.debug(f'Adding library \"{library}\" to List of selectionsToExcludeBasedOnWhatUserSelected_List')
                
                #Add the library to the Full list of what was excluded library sections for everything that is not in --selectlibrary argument passed in by the user
                selectionsToExcludeBasedOnWhatUserSelected_List.append(library)

        else:
            foundMatchInAllShowsSection = list(filter(library_regex.match, allShowSectionsFull_List))
            foundMatchInAllMoviesSection = list(filter(library_regex.match, allMovieSectionsFull_List))
            foundMatchInAllMusicSection = list(filter(library_regex.match, allMusicSectionsFull_List))
            foundMatchInAllPhotoSection = list(filter(library_regex.match, allPhotoSectionsFull_List))

            if foundMatchInExclude and foundInLibrarySectionMovieOrShow:
                logger.debug(f'Removing library \"{library}\" from plex_all_tv_and_movie_library_sections_minus_exluded')
                plex_all_tv_and_movie_library_sections_minus_exluded.remove(library)
                
            elif (foundMatchInAllMusicSection or foundMatchInAllPhotoSection) and foundInLibrarySectionMovieOrShow:
                plex_all_tv_and_movie_library_sections_minus_exluded.remove(library)               
                logger.debug(f'Removing library \"{library}\" from plex_all_tv_and_movie_library_sections_minus_exluded')
                
                selectionsToExcludeBasedOnWhatUserSelected_List.append(library)                   
                logger.debug(f'Adding library \"{library}\" to selectionsToExcludeBasedOnWhatUserSelected_List')
                
            elif (args.allshows == True) and (args.allmovies == False):
                if not foundMatchInAllShowsSection and foundInLibrarySectionMovieOrShow:
                    plex_all_tv_and_movie_library_sections_minus_exluded.remove(library)
                    logger.debug(f'Removing library \"{library}\" from plex_all_tv_and_movie_library_sections_minus_exluded')
                    
                    selectionsToExcludeBasedOnWhatUserSelected_List.append(library)                   
                    logger.debug(f'Adding library \"{library}\" to selectionsToExcludeBasedOnWhatUserSelected_List')

            elif (args.allshows == False) and (args.allmovies == True):
                if not foundMatchInAllMoviesSection and foundInLibrarySectionMovieOrShow:
                    plex_all_tv_and_movie_library_sections_minus_exluded.remove(library)                    
                    logger.debug(f'Removing library \"{library}\" from plex_all_tv_and_movie_library_sections_minus_exluded')
                    
                    selectionsToExcludeBasedOnWhatUserSelected_List.append(library)                   
                    logger.debug(f'Adding library \"{library}\" to selectionsToExcludeBasedOnWhatUserSelected_List')
            
            #Else remove sections that are not in either movie or shows, because all shows and all movies must have been selected
            else:
                if (foundMatchInAllMusicSection or foundMatchInAllPhotoSection) and foundInLibrarySectionMovieOrShow:
                    plex_all_tv_and_movie_library_sections_minus_exluded.remove(library)               
                    logger.debug(f'Removing library \"{library}\" from plex_all_tv_and_movie_library_sections_minus_exluded')
                    
                    selectionsToExcludeBasedOnWhatUserSelected_List.append(library)                   
                    logger.debug(f'Adding library \"{library}\" to selectionsToExcludeBasedOnWhatUserSelected_List')
                
   
    logger.debug(f'\n\nplex_all_tv_and_movie_library_sections_minus_exluded = {plex_all_tv_and_movie_library_sections_minus_exluded}\n')    
    logger.debug(f'\n\nselectionsToExcludeBasedOnWhatUserSelected_List = {selectionsToExcludeBasedOnWhatUserSelected_List}\n')   


    #If user did not choose to group together all Shows or Movies
    if args.select_library != None:
        #Build the playlist, first generates a playlist, then fills it.
        build_playlist(plex, account, plex_all_tv_and_movie_library_sections_minus_exluded, selectionsToExcludeBasedOnWhatUserSelected_List)
    
    #If only TV Shows were selected
    elif args.allshows == True and args.allmovies == False:
        #Build the playlist, first generates a playlist, then fills it.
        build_playlist(plex, account, plex_all_tv_and_movie_library_sections_minus_exluded, selectionsToExcludeBasedOnWhatUserSelected_List)
    
    #If only Movies were selected
    elif args.allshows == False and args.allmovies == True:
        #Build the playlist, first generates a playlist, then fills it.
        build_playlist(plex, account, plex_all_tv_and_movie_library_sections_minus_exluded, selectionsToExcludeBasedOnWhatUserSelected_List)
     
    #-----Else if both TV Shows and Movies were selected-----
    else: 
        #Build the playlist, first generates a playlist, then fills it.
        build_playlist(plex, account, plex_all_tv_and_movie_library_sections_minus_exluded, selectionsToExcludeBasedOnWhatUserSelected_List)

    return plex

    

def fetch_plex_api(path='', method='GET', plextv=False, **kwargs):
    """Fetches data from the Plex API"""

    url = 'https://plex.tv' if plextv else PLEX_URL.rstrip('/')


    headers = {'X-Plex-Token': args.token,
               'Accept': 'application/json'}

    params = {}
    if kwargs:
        params.update(kwargs)

    try:
        if method.upper() == 'GET':
            r = requests.get(url + path,
                             headers=headers, params=params, verify=False)
        elif method.upper() == 'POST':
            r = requests.post(url + path,
                              headers=headers, params=params, verify=False)
        elif method.upper() == 'PUT':
            r = requests.put(url + path,
                             headers=headers, params=params, verify=False)
        elif method.upper() == 'DELETE':
            r = requests.delete(url + path,
                                headers=headers, params=params, verify=False)
        else:
            print("Invalid request method provided: {method}".format(method=method))
            return

        if r and len(r.content):
            if 'application/json' in r.headers['Content-Type']:
                return r.json()
            elif 'application/xml' in r.headers['Content-Type']:
                return xmltodict.parse(r.content)
            else:
                return r.content
        else:
            return r.content

    except Exception as e:
        print("Error fetching from Plex API: {err}".format(err=e))


def get_user_tokens(server_id):
    api_users = fetch_plex_api('/api/users', plextv=True)

    api_shared_servers = fetch_plex_api('/api/servers/{server_id}/shared_servers'.format(server_id=server_id), plextv=True)
    user_ids = {user['@id']: user.get('@username', user.get('@title')) for user in api_users['MediaContainer']['User']}
    users = {user_ids[user['@userID']]: user['@accessToken'] for user in api_shared_servers['MediaContainer']['SharedServer']}
 
    #Return the Profile Name
    return users
    
def get_user_id(server_id):
    api_users = fetch_plex_api('/api/users', plextv=True)

    api_shared_servers = fetch_plex_api('/api/servers/{server_id}/shared_servers'.format(server_id=server_id), plextv=True)
    user_ids = {user['@id']: user.get('@username', user.get('@title')) for user in api_users['MediaContainer']['User']}
    users = {user_ids[user['@userID']]: user['@accessToken'] for user in api_shared_servers['MediaContainer']['SharedServer']}
 
    #Return the ids
    return user_ids


#Generate the users playlist for Server Method
def generate_all_users_playlist_via_server_method(base_url, authToken, homeUsers=None):

    try:
        plex_server = PlexServer(baseurl=base_url, token=authToken, session=None)
        logger.debug('\nGetting Library Sections...\n')
        
        plex_library_sections = plex_server.library.sections()
        logger.debug(f'Plex Sections: {plex_library_sections}\n')

    except Unauthorized:
        print(f'The Server details could not be authenticated.')
        exit(1)

    #If Home Users was selected check to see if it contains 'all'
    if(args.homeusers != None):
        
        getAllUsers = 'all'
    
        try:
            #list of All plex users
            allHomeUsers = list()
            get_plex_users = plex_server.myPlexAccount().users()
            
            print('Retrieving All Home Users ...\n')
            
            for plex_user in get_plex_users:
                allHomeUsers.append(plex_user.title)
            
            logger.debug(f'list home users: {homeUsers}')
            logger.debug(f'\nplex_library_sections = {plex_library_sections}\n')
            
            #If there are no HomeUsers even though the user supplied the argument to use homeUsers
            if not allHomeUsers:
                print(f'\nError - No Home Users available for \"{args.resource}\".\n')
                exit(1)
            
        except NotFound:
            print(f'\nError - No Home Users available for \"{args.resource}\".\n')
            exit(1)
        
                    
        #If the User passed in the string 'all' (case incensitive) into the argument --homeusers.
        #Regardless of if it is the only entry or within the list, then set the variable setAllHomeUsers to true.
        if getAllUsers.lower() in (homeUser.lower() for homeUser in homeUsers):
            print(f'\nFull List of Home Users Requested. \n')
            logger.debug(f'\nAll Home Users: {allHomeUsers}\n')
            setAllHomeUsers = True
          
        else:
            setAllHomeUsers = False
            
    else:
        setAllHomeUsers = False


    #If the user selected the --adminuser argument the script will also add the library to the admin account
    if(args.adminuser == True):
        try:
        #if plex_user in homeUsers: 
            print('\nChecking if the user is the Plex Home Admin...')
            
            #If the account is the Plex Home admin (True if it is, false if not).
            isHomeAdmin = plex_server.myPlexAccount().homeAdmin
            
            if (isHomeAdmin == True):
                print('\nThis is indeed the Home Admin\n')
            else:
                print('\nThis is NOT the Home Admin!\nExiting...\n')
                exit(1)

            adminUser = plex_server.myPlexAccount()
            #Get the Admin User Account Name
            adminUsername = adminUser.title

            print(f'\n-----------[BEGIN]-------------- {adminUsername} -------------[BEGIN]--------------')
            
            print(f'\nCurrent User [Admin]: {adminUsername}')

            #If the --purge argument was passed in then delete the playlist if it exist
            if(args.purge == True):
                delete_playlist(plex_server, adminUsername, args.name)
            else:
                print(f'Creating playlist \"{args.name}\" ...')
                create_playlist(plex_server, adminUsername)
                print(f'\nPlaylist creation for user [{adminUsername}] - COMPLETED\n')
            print(f'------------[END]------------- {adminUsername} --------------[END]-------------\n')  

        except Unauthorized:
            print(f'User \"{adminUsername}\" is Unauthorized to access the Plex Home \"{args.resource}\"')

        except NotFound:
            print(f'User \"{adminUsername}\" is not in the Plex Home \"{args.resource}\"')
            
        except BadRequest as e:
            print(f'\nError - BadRequest: {e}\n')
            exit(1)            
    
    if setAllHomeUsers == True:
        print('\n###Obtaining Home Users [ALL USERS]###\n\n')
        for plex_user in allHomeUsers:
            try:
                logger.debug('\nChecking if the current user is a Plex Home guest...\n')
                logger.debug(f'Switching to user: [{plex_user}] ...\n')
                
                print(f'\n-----------[BEGIN]-------------- {plex_user} -------------[BEGIN]--------------')         
                
                runningAsUser = plex_server.myPlexAccount().switchHomeUser(user=plex_user, pin=None).resource(args.resource).connect()
                
                print(f'\nCurrent User [Home User]: {plex_user}\n')

                #If the --purge argument was passed in then delete the playlist if it exist
                if(args.purge == True):
                    delete_playlist(runningAsUser, plex_user, args.name)
                else:
                    print(f'Creating playlist \"{args.name}\" ...')
                    create_playlist(runningAsUser, plex_user) 
                    print(f'\nPlaylist creation for user [{plex_user}] - COMPLETED\n')
                print(f'------------[END]------------- {plex_user} --------------[END]-------------')
                    
                if(args.purge != None):
                    time.sleep(5)
                                            
            except Unauthorized:
                print(f'User \"{plex_user}\" is Unauthorized to access the Plex Home \"{args.resource}\"')

            except NotFound:
                print(f'User \"{plex_user}\" is not in the Plex Home \"{args.resource}\"')
                
            except BadRequest as e:
                print(f'\nError - BadRequest: {e}\n')
                exit(1)
                
    else:
        #Used to count the number of valid Home Users entered by the user.
        numberValidHomeUsersEntered = 0
        
        for homeUser in homeUsers:
            if homeUser in allHomeUsers:
                try:
                    #if plex_user in homeUsers: 
                    logger.debug('\nChecking if the user is a Plex Home guest...\n')
                    logger.debug(f'\nHome User [matched]: {homeUser}\n')      
                    logger.debug(f'Switching to user: [{homeUser}] ...\n')
                    
                    print(f'-----------[BEGIN]-------------- {homeUser} -------------[BEGIN]--------------')
                                   
                    runningAsUser = plex_server.myPlexAccount().switchHomeUser(user=homeUser, pin=None).resource(args.resource).connect()
                    
                    print(f'\nCurrent User: {homeUser}\n')

                    #If the --purge argument was passed in then delete the playlist if it exist
                    if(args.purge == True):
                        delete_playlist(runningAsUser, homeUser, args.name)
                        
                        #Increment the valid entered user count
                        numberValidHomeUsersEntered += 1
                    else:
                        print(f'Creating playlist \"{args.name}\" ...')
                        create_playlist(runningAsUser, homeUser)
                        print(f'\nPlaylist creation for user [{homeUser}] - COMPLETED\n')
                        
                        #Increment the valid entered user count
                        numberValidHomeUsersEntered += 1
                    print(f'------------[END]------------- {homeUser} --------------[END]-------------')  
                    
                    if(args.purge != None):
                        time.sleep(5)
                        
                                            
                except Unauthorized:
                    print(f'User \"{homeUser}\" is Unauthorized to access the Plex Home \"{args.resource}\"')

                except NotFound:
                    print(f'User \"{homeUser}\" is not in the Plex Home \"{args.resource}\"')
                    
                except BadRequest as e:
                    print(f'\nError - BadRequest: {e}\n')
                    exit(1)
                    
            else:
                continue
                
        #If none of the users entered by the user are valid
        if((args.homeusers != None) and (numberValidHomeUsersEntered <= 0)):
            print(f'\nError - No Valid Home Users Submitted.\n')
            exit(1)


def generate_all_users_playlist_via_account_method(plexConnection, accountInfo, homeUsers):

    try:
        plex_library_sections = plexConnection.library.sections()
        logger.debug(f'Plex Sections: {plex_library_sections}\n')

    except Unauthorized:
        print(f'The Server details could not be authenticated.')
        exit(1)

    #If Home Users was selected, check to see if it contains 'all'
    if(args.homeusers != None):
    
        getAllUsers = 'all'
        
        try:           
            #list of All plex users
            allHomeUsers = list()
            get_plex_users = plexConnection.myPlexAccount().users()
            
            print('Retrieving All Home Users ...\n')
            
            for plex_user in get_plex_users:
                allHomeUsers.append(plex_user.title)
            
            logger.debug(f'list home users: {homeUsers}')
            logger.debug(f'\nplex_account = {accountInfo}\n')
            logger.debug(f'\nplex_library_sections = {plex_library_sections}\n')
            
            #If there are no HomeUsers even though the user supplied the argument to use homeUsers
            if not allHomeUsers:
                print(f'\nError - No Home Users available for \"{args.resource}\".\n')
                exit(1)

        except NotFound:
            print(f'\nError - No Home Users available for \"{args.resource}\".\n')
            exit(1)

        #If the User passed in the string 'all' (case incensitive) into the argument --homeusers.
        #Regardless of if it is the only entry or within the list, then set the variable setAllHomeUsers to true.
        if getAllUsers.lower() in (homeUser.lower() for homeUser in homeUsers):
            print(f'\nFull List of Home Users Requested. {homeUsers}\n')
            logger.debug(f'\nAll Home Users: {allHomeUsers}\n')                  
            setAllHomeUsers = True

        else:
            setAllHomeUsers = False

    else:
        setAllHomeUsers = False
    
    #If the user selected the --adminuser argument the script will also add the library to the admin account
    if(args.adminuser == True):
        try:
        #if plex_user in homeUsers: 
            print('\nChecking if the user is the Plex Home Admin...')
            
            #If the account is the Plex Home admin (True if it is, false if not).
            isHomeAdmin = plexConnection.myPlexAccount().homeAdmin
            
            if (isHomeAdmin == True):
                print('\nThis is indeed the Home Admin\n')
            else:
                print('\nThis is NOT the Home Admin!\nExiting...\n')
                exit(1)

            adminUser = plexConnection.myPlexAccount()
            #Get the Admin User Account Name
            adminUsername = adminUser.title

            print(f'\n-----------[BEGIN]-------------- {adminUsername} -------------[BEGIN]--------------')
            
            print(f'\nCurrent User [Admin]: {adminUsername}\n')

            #If the --purge argument was passed in then delete the playlist if it exist
            if(args.purge == True):
                delete_playlist(plexConnection, adminUser, args.name)
            else:
                print(f'Creating playlist \"{args.name}\" ...')
                create_playlist(plexConnection, adminUsername)
                print(f'\nPlaylist creation for user [{adminUsername}] - COMPLETED\n')
            print(f'------------[END]------------- {adminUsername} --------------[END]-------------\n')  

        except Unauthorized:
            print(f'User \"{adminUsername}\" is Unauthorized to access the Plex Home \"{args.resource}\"')

        except NotFound:
            print(f'User \"{adminUsername}\" is not in the Plex Home \"{args.resource}\"')
            
        except BadRequest as e:
            print(f'\nError - BadRequest: {e}\n')
            exit(1)            
                
    
    #If the user passed in the word "all" as a home user the script will run for every home user profile
    if setAllHomeUsers == True:
        print('\n###Obtaining Home Users [ALL USERS]###\n\n')
        for plex_user in allHomeUsers:
            try:
                logger.debug('\nChecking if the current user is a Plex Home guest...\n')
                logger.debug(f'Switching to user: [{plex_user}] ...\n')
                
                print(f'\n-----------[BEGIN]-------------- {plex_user} -------------[BEGIN]--------------')         
                
                runningAsUser = plexConnection.myPlexAccount().switchHomeUser(user=plex_user, pin=None).resource(args.resource).connect()
                
                print(f'\nCurrent User [Home User]: {plex_user}\n\n')

                #If the --purge argument was passed in then delete the playlist if it exist
                if(args.purge == True):
                    delete_playlist(runningAsUser, plex_user, args.name)
                else:
                    print(f'Creating playlist \"{args.name}\" ...')
                    create_playlist(runningAsUser, plex_user) 
                    print(f'\nPlaylist creation for user [{plex_user}] - COMPLETED\n')
                print(f'------------[END]------------- {plex_user} --------------[END]-------------')
                    
                if(args.purge != None):
                    time.sleep(5)
                    
            except Unauthorized:
                print(f'User \"{plex_user}\" is Unauthorized to access the Plex Home \"{args.resource}\"')

            except NotFound:
                print(f'User \"{plex_user}\" is not in the Plex Home \"{args.resource}\"')
                
            except BadRequest as e:
                print(f'\nError - BadRequest: {e}\n')
                exit(1)
                
    else:
        #Used to count the number of valid Home Users entered by the user.
        numberValidHomeUsersEntered = 0
        
        for homeUser in homeUsers:        
            if homeUser in allHomeUsers:
                try:
                    #if plex_user in homeUsers: 
                    logger.debug('\nChecking if the user is a Plex Home guest...\n')
                    logger.debug(f'\nHome User [matched]: {homeUser}\n')    
                    logger.debug(f'Switching to user: [{homeUser}] ...\n')
                    
                    print(f'-----------[BEGIN]-------------- {homeUser} -------------[BEGIN]--------------')
                                   
                    runningAsUser = plexConnection.myPlexAccount().switchHomeUser(user=homeUser, pin=None).resource(args.resource).connect()
                    
                    print(f'\nCurrent User: {homeUser}\n')

                    #If the --purge argument was passed in then delete the playlist if it exist
                    if(args.purge == True):
                        delete_playlist(runningAsUser, homeUser, args.name)

                        #Increment the valid entered user count
                        numberValidHomeUsersEntered += 1                        
                    else:
                        print(f'Creating playlist \"{args.name}\" ...')
                        create_playlist(runningAsUser, homeUser)
                        print(f'\nPlaylist creation for user [{homeUser}] - COMPLETED\n')
                        
                        #Increment the valid entered user count
                        numberValidHomeUsersEntered += 1                        
                    print(f'------------[END]------------- {homeUser} --------------[END]-------------')  
                    
                    if(args.purge != None):
                        time.sleep(5)
                        
                except Unauthorized:
                    print(f'User \"{homeUser}\" is Unauthorized to access the Plex Home \"{args.resource}\"')

                except NotFound:
                    print(f'User \"{homeUser}\" is not in the Plex Home \"{args.resource}\"')
                    
                except BadRequest as e:
                    print(f'\nError - BadRequest: {e}\n')
                    exit(1)
                    
            else:
                continue

        #If none of the users entered by the user are valid
        if((args.homeusers != None) and (numberValidHomeUsersEntered <= 0)):
            print(f'\nError - No Valid Home Users Submitted.\n')
            exit(1)
            

def main():
    global args
    args = get_args()
    plex = None

    #If the user enters the selectLibrary argument
    if(args.select_library != None) and (args.allshows == True):
        print(f'\nERROR - The \"selectLibrary\" argument cannot be used in conjunction with the \"allShows\" argument.\n')
        exit(1)
    elif(args.select_library != None) and (args.allmovies == True):
        print(f'\nERROR - The \"selectLibrary\" argument cannot be used in conjunction with the \"allmovies\" argument.\n')
        exit(1)
    
    #If the user does not provide a user to apply the playlist creation/deletion to, print an Error, and exit.
    if(args.adminuser != True) and (args.homeusers == None):
        print(f'\nERROR - The script requires the use of at least one User.\n\nAvailable options:\n [1] - adminuser (--adminuser) \n [2] - homeusers (--homeusers "Username1,Username2,...")\n')
        exit(1)

    #If the user does not pass in either of the following arguments: --selectlibrary, --allshows, or --allmovies, or --purge
    if(args.select_library == None) and (args.allshows == False) and (args.allmovies == False) and (args.purge == False):
        print('\nERROR - One of the required arguments must be selected.')
        print(f'        Rerun your command with one of the following required Arguments:')
        print(f'        --selectlibrary\n        --allshows\n        --allmovies\n        --purge\n')
        time.sleep(3)
        exit(1)

    #If the Playlist Name is empty
    if(args.name == None) or (args.name == ""):
        print(f'\nThe argument \"--name\" cannot be empty.\nPlease provide the name argument and try again.\n')
        exit(1)
    elif(args.name == False):
        print(f'The argument \"--name\" is required and cannot be ommitted.\nPlease provide the name argument and try again.\n')
        exit(1)
       
    if(args.number > 0):
        #Select home Users
        if(args.homeusers):
            #Use a regex to remove spaces between commas in the users entry.
            space_remover_regex = r'(^\s+|\s*,\s*|\s+$)'
            getHomeUsers = re.sub(space_remover_regex,',', args.homeusers)
            homeUsers = (getHomeUsers).split(comma)
        else:
            homeUsers = list()
        
        #Split each Library selection and each excluded library to build a list
        if (args.select_library != None):
            if(args.select_library == ""):
                print(f'\nError - The selected library argument cannot be empty.\n')
                exit(1)
            else:
                #Use a regex to remove spaces between commas in the users entry.
                space_remover_regex = r'(^\s+|\s*,\s*|\s+$)'
                getLibrarySection = re.sub(space_remover_regex,',', args.select_library)
                selectedLibrariesList = (getLibrarySection).split(comma)
            
        if (args.exclude_library != None):
            #Use a regex to remove spaces between commas in the users entry.
            space_remover_regex = r'(^\s+|\s*,\s*|\s+$)'
            getExcludeSection = re.sub(space_remover_regex,',', args.exclude_library)
            excludedLibrariesList = (getExcludeSection).split(comma)
        
        if (args.select_library != None) and (args.exclude_library != None):
            #Verify that the selected Library is not in the excluded libraries list
            for selectedLibrary in selectedLibrariesList:
                if selectedLibrary in excludedLibrariesList:
                    print(f'\nThe selected Library \"{selectedLibrary}\" cannot be included in the \"--excluded-library\" argument.\n')
                    exit(1)
        
        #print the excluded library generated by --exclude-library argument to the user in case they used the default value and did know that libraries are being excluded without passing it in as an argument manually.
        if(args.exclude_library != None):
            print(f'\nLibrary Sections to exclude [--exclude-library]: {excludedLibrariesList}\n')
             
        if args.debug:
            logger.setLevel(logging.DEBUG)
            
        #If the authorization method is Account
        if (args.account == True) and (args.server == False):
        
            #If the username argument is empty or missing
            if(args.username == None) or (args.username == ""):
                print(f'\nThe argument \"--username\" is required and cannot be empty.\n')
                exit(1)
                
            #If the password argument is empty or missing
            elif(args.password == None) or (args.password == ""):
                print(f'\nThe argument \"--password\" is required and cannot be empty.\n')
                exit(1)
            
            #If the resource argument is empty or missing
            elif(args.resource == None) or (args.resource == ""):
                print(f'\nThe argument \"--resource\" is required for the account connection method, and cannot be empty.\n')
                exit(1)
            
            try:
                # ## Connect via Account
                account = MyPlexAccount(args.username, args.password)
                plex = account.resource(args.resource).connect()
                
            except NotFound:
                print(f'The Resource \"{args.resource}\" could not be found.')
                exit(1)
                
            except Unauthorized:
                print(f'The Username and password could not be authenticated.')
                exit(1)
            
            except BadRequest as e:
                print(f'\nError - BadRequest: {e}\n')
                exit(1)            
                    
            #Generate Playlist for the requested Account (Method) Users
            if (args.homeusers != False):
                generate_all_users_playlist_via_account_method(plex, account, homeUsers)
            else:
                generate_all_users_playlist_via_account_method(plex, account)
        
        #If the authorization method is Server
        elif (args.server == True) and (args.account == False):
            #If the baseurl argument is empty or missing
            if(args.baseurl == None) or (args.baseurl == ""):
                print(f'\nThe Base URL is required and cannot be empty.\n')
                exit(1)
                
            #If the auth token argument is empty or missing
            elif(args.token == None) or (args.token == ""):
                print(f'\nThe Auth Token is required and cannot be empty.\n')
                exit(1)

            #If the resource argument is empty or missing
            if(args.resource == None) or (args.resource == ""):
                print(f'\nThe argument \"--resource\" is required for the server connection method, and cannot be empty.\n')
                exit(1)

            #Connect via Direct URL
            #Generate Playlist for the requested Server (Method) Users
            if (args.homeusers != False):
                generate_all_users_playlist_via_server_method(args.baseurl, args.token, homeUsers)
            else:
                generate_all_users_playlist_via_server_method(args.baseurl, args.token)
            
        else:
            #Print that the connection method is required to proceed.
            print(f'\nERROR - The script requires the use of ONE connection method to proceed.\n\nAvailable options:\n [1] - account (--account) \n [2] - server (--server)\n')
            exit(1)
            
    else:
        print(f'\nError - \"args.number\" must be greater than 0.\n')
        exit(1)
        


if __name__ == '__main__':
    main()
