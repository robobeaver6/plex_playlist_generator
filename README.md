# Plex Random Series Playlist Generator

Simple script to generate a playlist on a plex server that randomises the series, but plays the episodes within that 
series in order

##Usage
```
usage: plex_playlist_generator.py [-h] [--name NAME] [--number NUMBER] [--debug]
                                  [--server] [--baseurl BASEURL] [--token TOKEN] [--account]
                                  [--username USERNAME] [--password PASSWORD]
                                  [--resource RESOURCE] [--tvdb-api-key TVDB_API_KEY]
                                  [--ignore-skipped] [--randomize] [--include-watched]
                                  [--allshows] [--allmovies] [--select-library SELECT_LIBRARY]
                                  [--exclude-library EXCLUDE_LIBRARY] [--purge] [--adminuser]
                                  [--homeusers HOMEUSERS]

Create playlist of unwatched episodes from random shows but in correct episode
order.

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           Playlist Name
  --number NUMBER, -n NUMBER
                        Number of episodes or Movies to add to play list
  --debug, -d           Debug Logging

Server Connection Method:
  --server              Server connection Method
  --baseurl BASEURL, -b BASEURL
                        Base URL of Server (I.E "http://10.1.1.8:32400" or "https://your.domain.com:32400")
  --token TOKEN, -t TOKEN
                        Authentication Token

Plex Account Connection Method:
  --account             Account Connection Method
  --username USERNAME, -u USERNAME
                        Plex Account Username
  --password PASSWORD, -p PASSWORD
                        Plex Account Password
  --resource RESOURCE, -r RESOURCE
                        Resource Name (Plex Server Name)
  --tvdb-api-key TVDB_API_KEY
                        TVDB API Key)

Episode/Movie Selection Behaviour:
  --ignore-skipped      Don't test for missing episodes
  --randomize           Randomize selected episodes, not next unwatched
  --include-watched     include watched movies or episodes (use with --randomize)

Library Selection Behavior:
  --allshows             Grab All Shows in all Library sections From Plex
  --allmovies            Grab All Movies in all Library sections From Plex
  --select-library, -l   SELECT_LIBRARY   Choose between library sections of both TV Shows or Movies to build a playlist from (comma seperated within quotes if multiple users)
  --exclude-library -e   EXCLUDE_LIBRARY  Comma seperated list (if selecting multiple users) of sections to exclude (I.E. "Test Videos,Workout,Home Videos" ) there should be no space between the comma and the first character of the next value
  --purge                Remove a playlist from plex for the provided user(s)

User Profile Selection:
  --adminuser, -a        Generate playlist for the Plex Admin user profile name that was used to login.
  --homeusers HOMEUSERS  Generate playlist for the provided Plex home users (comma seperated within quotes if multiple users). For all plex home users type "all"

```
### Install dependencies
> **NOTE:**
>
> Recommend Using a virtual env
>
> `pip install Pipfile`
> 
> `pip install xmltodict`

## Connection Methods
### Account
Uses your PlexTV Account, username and Resource Name (Server Name)  
e.g. `plex_playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer --allmovies`

### Server
Uses The Server URL and Authentication Token  
e.g. `plex_playlist_generator.py --server --baseurl "http://172.16.1.100:32400" --token "fR5GrDxfLunKynNub5" --allshows`

### Authentication Token
To get your Auth token, browse to an episode in the web UI. Click on the `...` video and select `Get Info`.  In the 
popup window select `View XML` in the URL there is the `X-Plex-Token=XXXXXXXXXXXXXX`

### Library Selection
Uses either the Account Method or Server Method to generate playlist of movies and/or TV Shows
>
>Note: any of the below commands can be run by either connection method (Server/Account).
>
The default behavior of the script for TV Shows is that if its a show a user has began watching the script will begin with the episode you are currently on.


### Examples:

Generate 10 random unwatched TV Show episodes:  
    `plex_playlist_generator.py --server --baseurl "https://your.domain.com:32400" --token "fR5GrDxfLunKynNub5" --resource MyServer --allshows --homeusers John`

Generate 10 random unwatched epsidodes for the 3 provided homeusers (Johnny,Smith,Curry): 
    `plex_playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer --allshows --homeusers "John,Smith,Curry" --excludeilibrary "TV Shows,Movies"`

Generate 10 random unwatched movies for the admin user:
    `plex_playlist_generator.py --server --baseurl "https://your.domain.com:32400" --token "fR5GrDxfLunKynNub5" --resource MyServer --allmovies --admin`

Generate 5 random unwatched Movies for the 3 provided homeusers (Johnny,Smith,Curry): 
  `plex_playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer --allmovies --admin --homeusers "John,Smith,Curry" --number 5`

Generate 3 random unwatched epsidodes for all home users on the plex server:
    `plex_playlist_generator.py --server --baseurl "http://172.16.1.100:32400" --token "fR5GrDxfLunKynNub5" --resource MyServer --allmovies --admin --homeusers all --number 3`

Ignore The facty that not all episodes are available for a show in your library [highly recommend using to reduce processing time]
    `plex_playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer --allmovies --admin --homeusers "all" --ignore-skipped`

Generate a mix 8 random shows and movies:
    `plex_playlist_generator.py --server --baseurl "http://172.16.1.100:32400" --token "fR5GrDxfLunKynNub5" --resource MyServer --allmovies --homeusers --allshows --allmovies --number 8`

Generate a playlist with the name "Test1" for all home users:
`plex_playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer --allmovies --admin --homeusers "all" --name "Test1"`

Delete a playlist with the name "Test1" for all home users:
    `plex_playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer --allmovies --admin --homeusers "all" --purge`

