#!/usr/bin/env python
# debian deps:
# python-django

'''Get BF4 server data and output to HTML

Usage: bf4_server_status.py [--debug]
'''

import urllib
import json
import os
import socket
import sys
import time
from django.template import Template, Context
from django.conf import settings
from django.utils.datastructures import SortedDict
settings.configure() # We have to do this to use django templates standalone - see
# http://stackoverflow.com/questions/98135/how-do-i-use-django-templates-without-the-rest-of-django

# Our template. Could just as easily be stored in a separate file
template = """
<style>
table,th,td
{
border:1px solid black;
font-size:95%;
}
</style>
<meta http-equiv="refresh" content="{{refresh}}" >
{{player_count}} player(s) on {{current_map}}.
<table style="width:270px">
    <tr>
        <td>Player</td>
        <td>Cheat Score</td>
    </tr>
    {% for key, value in player_data.items %}
    <tr>
        <td><a href="http://battlelog.battlefield.com/bf4/soldier/{{key}}/stats/{{value.personaId}}/pc/">{{key}}</a></td>
        {% if value.cheatscore < 10 or value.cheatscore == None %}
            <td><a href="{{value.bf4db_url}}">{{value.cheatscore}}</a></td>
        {% else %}
            <td bgcolor="red"><a href="{{value.bf4db_url}}">{{value.cheatscore}}</a></td>
        {% endif %}
    </tr>
    {% endfor %}
</table>
Last updated at {{update_time}} UTC.
"""

# Mapping engine map names to human-readable names
map_names = {'MP_Abandoned': 'Zavod 311',
             'MP_Damage': 'Lancang Dam',
             'MP_Flooded': 'Flood Zone',
             'MP_Journey': 'Golmud Railway',
             'MP_Naval': 'Paracel Storm',
             'MP_Prison': 'Operation Locker',
             'MP_Resort': 'Hainan Resort',
             'MP_Siege': 'Siege of Shanghai',
             'MP_TheDish': 'Rogue Transmission',
             'MP_Tremors': 'Dawnbreaker',
             'XP1_001': 'Silk Road',
             'XP1_002': 'Altai Range',
             'XP1_003': 'Guilin Peaks',
             'XP1_004': 'Dragon Pass',
             'XP0_Caspian': 'Caspian Border',
             'XP0_Firestorm': 'Operation Firestorm',
             'XP0_Metro': 'Operation Metro',
             'XP0_Oman': 'Gulf of Oman',
             'XP2_001': 'Lost Islands',
             'XP2_002': 'Nansha strike',
             'XP2_003': 'WaveBreaker',
             'XP2_004': 'Operation Mortar'}

# Put your URLs here
server_url = ''
file_dir = ''
refresh = 60
bf4db_url = 'http://api.bf4db.com/api-player.php?name='

# Generic way to write our files
def write_file(filename, text):
    with open(filename, 'w') as f:
        f.write(text)

# http://stackoverflow.com/questions/788411/check-to-see-if-python-script-is-running
def get_lock(process_name):
    global lock_socket
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind('\0' + process_name)
    except socket.error:
        print 'already running.  exiting.'
        sys.exit()

def json_query(json_url):
    retry_limit = range(1,6)
    for x in retry_limit:
        try:
            result_json = json.load(urllib.urlopen(json_url))
            return result_json
        except:
            print 'query failed - URL was ' + json_url
            print 'attempting retry ' + str(x) + ' of ' + str(retry_limit[-1])
            time.sleep(1)
            if x >= retry_limit[-1]:
                print 'giving up.  exiting.'
                sys.exit(1)
            else:
                continue

def write_template(player_count, current_map, player_data):
    write_file(os.path.join(file_dir + 'player_count.html'), player_count)
    update_time = time.strftime('%H:%M:%S %m/%d/%Y')
    t = Template(template)
    c = Context({"player_count": player_count,
                 "current_map": current_map,
                 "map_names": map_names,
                 "refresh": refresh,
                 "update_time": update_time,
                 "player_data": player_data})
    write_file(os.path.join(file_dir + 'index.html'), t.render(c))

def server_status(server_url):
    server_json = json_query(server_url)
    try:
        current_map_id = server_json['message']['SERVER_INFO']['map']
        player_count_json = server_json['message']['SERVER_INFO']['slots']['2']['current']
    except TypeError:
        if debug:
            print 'Unable to query battlelog'
        sys.exit(1)
    current_map = map_names[current_map_id]
    player_count = str(player_count_json)
    player_list = []
    for x in range(0, len(server_json['message']['SERVER_PLAYERS'])):
        player_list.append(server_json['message']['SERVER_PLAYERS'][x]['persona']['user']['username'])
    if debug:
        print 'Player count: ' + player_count
    return player_list, player_count, current_map

def bf4db_query(player_list):
    player_dict = SortedDict()
    for x in sorted(player_list, key=lambda s: s.lower()):
        time.sleep(0.5)
        try:
            bf4db_json = json_query(bf4db_url + x)
            player_dict[x] = bf4db_json['data']
        except ValueError:
            player_dict[x] = None
        if debug:
            print x + ' ' + str(player_dict[x]['cheatscore'])
    return player_dict

def cmdline():
    global debug
    try:
        arg = sys.argv[1]
        if arg == '--debug':
            debug = True
        else:
            print __doc__
            sys.exit(1)
    except IndexError:
        debug = False

cmdline()
get_lock('bf4_server_status.py')
players = server_status(server_url)
player_data = bf4db_query(players[0])
write_template(players[1], players[2], player_data)
