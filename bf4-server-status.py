#!/usr/bin/env python

import socket
import sys
from collections import namedtuple
from lib.frostbite_wire.packet import Packet
import argparse
import urllib
import json
import os
import socket
import sys
import time
from django.template import Template, Context
from django.conf import settings
from django.utils.datastructures import SortedDict


# Generic way to write our files
def write_file(filename, text):
    with open(filename, 'w') as f:
        f.write(text)


# http://stackoverflow.com/questions/788411/check-to-see-if-python-script-is-running
class ProcessLock:
    def __init__(self):
        self.lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    def get_lock(self, process_name):
        try:
            self.lock_socket.bind('\0' + process_name)
        except socket.error:
            sys.exit('already running.  exiting.')


def json_query(json_url):
    retry_limit = range(1, 6)
    for x in retry_limit:
        try:
            result_json = json.load(urllib.urlopen(json_url))
            return result_json
        except:
            print 'query failed - URL was ' + json_url
            print 'attempting retry ' + str(x) + ' of ' + str(retry_limit[-1])
            time.sleep(1)
            if x >= retry_limit[-1]:
                sys.exit('giving up.  exiting.')
            else:
                continue


def write_template(player_count, current_map, current_mode, player_data, file_dir, refresh):
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
    {{player_count}} player(s) on {{current_map}} {{current_mode}}.
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
    write_file(os.path.join(file_dir + '/player_count.html'), player_count)
    update_time = time.strftime('%H:%M:%S %m/%d/%Y')
    t = Template(template)
    c = Context({"player_count": player_count,
                 "current_map": current_map,
                 "current_mode": current_mode,
                 "refresh": refresh,
                 "update_time": update_time,
                 "player_data": player_data})
    write_file(os.path.join(file_dir + '/index.html'), t.render(c))


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
                 'XP3_WtrFront': 'Sunken Dragon'}

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

    little_player_list = list()
    for x in player_list:
        little_player_list.append(x[0])
        if debug and len(little_player_list) > 1:
            break

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
    return little_player_list, player_count, current_map, current_mode


def bf4db_query(player_list, bf4db_url, debug=False):
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


class CommandLine():
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


def _main():
    cmdline = CommandLine()
    cmdline.cmdline()
    process_lock = ProcessLock()
    process_lock.get_lock('bf4_server_status.py')
    refresh = 60
    bf4db_url = 'http://api.bf4db.com/api-player.php?name='
    # We have to do this to use django templates standalone - see
    # http://stackoverflow.com/questions/98135/how-do-i-use-django-templates-without-the-rest-of-django
    settings.configure()
    little_player_list, player_count, current_map, current_mode = server_status(cmdline.address, cmdline.server_port, cmdline.debug)
    player_data = bf4db_query(little_player_list, bf4db_url, cmdline.debug)
    write_template(player_count, current_map, current_mode, player_data, cmdline.file_dir, refresh)

if __name__ == '__main__':
    _main()
