bf4-server-status
=================
A simple status page for your Battlefield 4 server that's updated every couple of minutes with server title, map/game mode, player count, player list, bf4db.com cheat score, and links to player profiles.  Good for monitoring your server with a mobile device!

<pre>usage: bf4-server-status.py [-h] [-d] [-p PORT] address file_dir

Status web page for your BF4 server.

positional arguments:
  address               Server hostname or IP address
  file_dir              Path to generated HTML file(s)

optional arguments:
  -h, --help            show this help message and exit
  -d                    show debug info in terminal
  -p PORT, --port PORT  Server port number</pre>
  
Installation (in a virtualenv with a reasonably recent version of pip):
* `git clone --recursive https://github.com/robled/bf4-server-status.git`
* `pip install -Ur requirements.txt`
