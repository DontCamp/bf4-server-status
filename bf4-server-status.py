#!/usr/bin/env python
import argparse
import os
import socket
import sys
import time
from collections import namedtuple, OrderedDict

import requests
from frostbite_wire.packet import Packet
from jinja2 import Template


template = """
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="{{refresh}}" >
        <link rel="stylesheet" href="https://netdna.bootstrapcdn.com/bootstrap/{{bootstrap_version}}/css/bootstrap.min.css">
        <title>{{server_name}}</title>
    </head>
    <body>
        <div class="container">
            <h3>{{player_count}} player(s) on {{current_map}} {{current_mode}}</h3>
            {% macro team_block(team, player_data) %}
            <div class="col-xs-6">
                <div class="panel panel-primary">
                    <table class="table table-striped table-condensed">
                        <tr>
                            <th>Player</th>
                            <th class="text-center">Cheat Score</th>
                        </tr>
                        {% for key, value in player_data.items() %}
                        <tr>
                            <td><a href="http://battlelog.battlefield.com/bf4/soldier/{{key.name}}/stats/{{value.personaId}}/pc/">{{key.name}}</a></td>
                            {% if value.cheatscore < 1 or value.cheatscore == None %} {% set level="default" %}
                            {% elif value.cheatscore < 60 %} {% set level="warning" %}
                            {% else %} {% set level="danger" %}
                            {% endif %}
                            <td class="{{level}} text-center"><a href="{{value.bf4db_url}}" class="btn btn-xs btn-{{level}}">{{value.cheatscore}}</a></td>
                        </tr>
                        {% endfor %}
                    </table>
                    <div class="panel-heading"><strong>Team {{team}}</strong></div>
                </div>
            </div>
            {% endmacro %}
            {% for team, player_data in [(1, team1_players), (2, team2_players)] %}
                {{ team_block(team, player_data) }}
            {% endfor %}
        </div>
        <div class="container text-center">
            <p>Last updated at {{update_time}} UTC</p>
        </div>
        <script src="https://code.jquery.com/jquery.js"></script>
        <script src="https://netdna.bootstrapcdn.com/bootstrap/{{bootstrap_version}}/js/bootstrap.min.js"></script>
    </body>
</html>
"""


class CommandLine:
    def __init__(self):
        self.debug = False
        self.address = ''
        self.server_port = None
        self.file_dir = ''

    def cmdline(self):
        parser = argparse.ArgumentParser(description='Status web page for your BF4 server.')
        parser.add_argument('-d', help='show debug info in terminal',
                            action="store_true")
        parser.add_argument('address', help='Server hostname or IP address')
        parser.add_argument('-p', '--port', type=int, help='Server port number')
        parser.add_argument('file_dir', help='Path to generated HTML file(s)')
        args = parser.parse_args()
        self.address = args.address
        self.file_dir = args.file_dir
        if args.d:
            self.debug = True
        else:
            self.debug = False
        if args.port:
            self.server_port = args.port
        else:
            self.server_port = None


# http://stackoverflow.com/questions/788411/check-to-see-if-python-script-is-running
class ProcessLock:
    def __init__(self):
        self.lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    def get_lock(self, process_name):
        try:
            self.lock_socket.bind('\0' + process_name)
        except socket.error:
            sys.exit('already running.  exiting.')


def server_status(address, server_port=None, debug=False):
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
                 'XP2_004': 'Operation Mortar',
                 'XP3_MarketPl': 'Pearl Market',
                 'XP3_Prpganda': 'Propaganda',
                 'XP3_UrbanGdn': 'Lumphini Garden',
                 'XP3_WtrFront': 'Sunken Dragon',
                 'XP4_Arctic': 'Operation Whiteout',
                 'XP4_SubBase': 'Hammerhead',
                 'XP4_Titan': 'Hangar 21',
                 'XP4_WlkrFtry': 'Giants of Karelia'}

    # Mapping engine map modes to human-readable names
    game_modes = {'AirSuperiority0': 'Air Superiority',
                  'CaptureTheFlag0': 'Capture the Flag',
                  'CarrierAssaultSmall0': 'Carrier Assault',
                  'CarrierAssaultLarge0': 'Carrier Assault Large',
                  'Chainlink0': 'Chain Link',
                  'ConquestSmall0': 'Conquest Small',
                  'ConquestLarge0': 'Conquest Large',
                  'Elimination0': 'Defuse',
                  'Domination0': 'Domination',
                  'Obliteration': 'Obliteration',
                  'RushLarge0': 'Rush',
                  'SquadDeathMatch0': 'Squad DM',
                  'TeamDeathMatch0': 'Team DM'}

    def recv(sock):
        # Pull enough to get the int headers and instantiate a Packet
        out = sock.recv(12)
        p = Packet.from_buffer(out)
        packet_size = len(p)
        # Pull one character at a time until we've recv'd
        # up to the reported size
        while len(out) < packet_size:
            out += sock.recv(1)
        return out

    try:
        port = int(server_port)
    except TypeError:
        port = 47200

    server = address, port

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(server)

    serverinfo = Packet(1, False, True, 'serverinfo')
    sock.sendall(serverinfo.to_buffer())

    response = Packet.from_buffer(recv(sock))
    serverinfo = response.words

    listplayers = Packet(2, False, True, 'listPlayers all')
    sock.sendall(listplayers.to_buffer())
    response = Packet.from_buffer(recv(sock))
    listplayers = response.words

    sock.close()

    # Need both of these to go on
    assert serverinfo[0] == 'OK'
    assert listplayers[0] == 'OK'

    # Chomp on the listplayers output and loop out some namedtuples
    num_fields, the_rest = int(listplayers[1]), listplayers[2:]
    fields, num_players, players = (
        the_rest[:num_fields],
        the_rest[num_fields],
        the_rest[num_fields + 1:]
    )

    Player = namedtuple('Player', fields)

    player_list = list()
    while players:
        player_list.append(Player(*players[:num_fields]))
        players = players[num_fields:]

    # Print out pretty server name/players
    if debug:
        print 'server name: ' + serverinfo[1]
        print 'players : ' + serverinfo[2]
        print 'maxplayers : ' + serverinfo[3]
        print 'mode : ' + serverinfo[4]
        print 'map : ' + serverinfo[5]

    player_count = serverinfo[2] + '/' + serverinfo[3]
    current_map = map_names[serverinfo[5]]
    current_mode = game_modes[serverinfo[4]]
    server_name = serverinfo[1]
    return player_list, player_count, current_map, current_mode, server_name


def json_query(json_url):
    retry_limit = range(1, 3)
    for x in retry_limit:
        if x >= retry_limit[-1]:
            break
        try:
            r = requests.get(json_url, timeout=10)
            return r.json()
        except:
            print 'query failed - URL was ' + json_url
            print 'attempting retry ' + str(x) + ' of ' + str(retry_limit[-1])


def bf4db_query(player_list, bf4db_url, debug=False):
    bf4db_up = True
    player_dict = OrderedDict()
    for p in sorted(player_list, key=lambda k: k.name.lower()):
        if bf4db_up:
            time.sleep(0.3)
            try:
                bf4db_json = json_query(bf4db_url + p.name)
                player_dict[p] = bf4db_json['data']
                if debug:
                    print p.name, player_dict[p]['cheatscore']
            except Exception as ex:
                bf4db_up = False
                if debug:
                    print ex, ex.args[0]
        else:
            # reset the player dictionary since bf4db is down
            player_dict = {}
    return player_dict


# Generic way to write our files
def write_file(filename, text):
    with open(filename, 'w') as f:
        f.write(text.encode('utf-8'))


def write_template(player_count, current_map, current_mode, player_data,
        server_name, file_dir, refresh):
    # Our template. Could just as easily be stored in a separate file
    write_file(os.path.join(file_dir, 'player_count.html'), player_count)
    update_time = time.strftime('%H:%M:%S %m/%d/%Y')
    t = Template(template)
    team1_players = OrderedDict()
    team2_players = OrderedDict()
    for player in player_data:
        if player.teamId == '1':
            team1_players[player] = player_data[player]
        elif player.teamId == '2':
            team2_players[player] = player_data[player]
    context = {
        "player_count": player_count,
        "current_map": current_map,
        "current_mode": current_mode,
        "refresh": refresh,
        "update_time": update_time,
        "team1_players": team1_players,
        "team2_players": team2_players,
        "server_name": server_name,
        "bootstrap_version": '3.3.1',
    }
    write_file(os.path.join(file_dir, 'index.html'), t.render(**context))


def _main():
    cmdline = CommandLine()
    cmdline.cmdline()
    process_lock = ProcessLock()
    process_lock.get_lock('bf4_server_status.py')
    refresh = 60
    bf4db_url = 'http://api.bf4db.com/api-player.php?format=json&name='
    player_list, player_count, current_map, current_mode, server_name = server_status(
        cmdline.address, cmdline.server_port, cmdline.debug)
    player_data = bf4db_query(player_list, bf4db_url, cmdline.debug)
    # Get a sorted list of keys based on cheatscore first, then the player name
    player_data_sorted_keys = sorted(player_data.keys(),
        key=lambda k: '%d%s' % (player_data[k]['cheatscore'], k.name.lower()))
    # rebuild player_data based on the sorted keys
    sorted_player_data = OrderedDict()
    for sorted_player in player_data_sorted_keys:
        sorted_player_data[sorted_player] = player_data[sorted_player]
    write_template(player_count, current_map, current_mode, sorted_player_data, server_name,
        cmdline.file_dir, refresh)

if __name__ == '__main__':
    _main()
