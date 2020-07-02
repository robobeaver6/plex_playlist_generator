# Plex Random Series Playlist Generator

Simple script to generate a playlist on a plex server that randomises the series, but plays the episodes within that 
series in order

##Usage
```
usage: playlist_generator.py [-h] [--name NAME] [--number NUMBER] [--server]
                             [--baseurl BASEURL] [--token TOKEN] [--account]
                             [--username USERNAME] [--password PASSWORD]
                             [--resource RESOURCE] [--ignore-skipped]
                             [--randomize] [--include-watched] [--debug]

Create playlist of unwatched episodes from random shows but in correct episode
order.

optional arguments:
  -h, --help                    show this help message and exit
  --name NAME                   Playlist Name
  --number NUMBER, -n NUMBER    Number of episodes to add to play list
  --debug, -d                   Debug Logging

Server Connection Method:
  --server                      Server connection Method
  --baseurl BASEURL, -b BASEURL Base URL of Server
  --token TOKEN, -t TOKEN   Authentication Token

Plex Account Connection Method:
  --account              Account Connection Method
  --username USERNAME, -u USERNAME   Plex Account Username
  --password PASSWORD, -p PASSWORD   Plex AccountPassword
  --resource RESOURCE, -r RESOURCE   Resource Name (Plex Server Name)

Episode Selection Behaviour:
  --ignore-skipped      Don't test for missing episodes
  --randomize           Randomize selected episodes, not next unwatched
  --include-watched     include watched episodes (use with --randomize
```
## Connection Methods
### Account
Uses your PlexTV Account, username and Resource Name (Server Name)  
e.g. `playlist_generator.py --account --username MyUserName --password Sh1tPass --resource MyServer`

### Server
Uses The Server URL and Authentication Token  
e.g. `playlist_generator.py --server --baseurl "http://172.16.1.100:32400" --token "fR5GrDxfLunKynNub5"`

### Authentication Token
To get your Auth token, browse to an episode in the web UI. Click on the `...` video and select `Get Info`.  In the 
popup window select `View XML` in the URL there is the `X-Plex-Token=XXXXXXXXXXXXXX`
