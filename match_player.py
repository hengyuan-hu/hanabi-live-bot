#!/usr/bin/env python

# An example reference bot to match player on the Hanabi Live website

# The "dotenv" module does not work in Python 2
import sys
if sys.version_info < (3, 0):
    print('This script requires Python 3.x.')
    sys.exit(1)

# Imports (standard library)
import os

# Imports (3rd-party)
import dotenv
import requests

# Authenticate, login to the Hanabi Live WebSocket server, and run forever
def main():
    # Load environment variables from the ".env" file
    dotenv.load_dotenv()

    protocol = 'http'
    ws_protocol = 'ws'
    host = 'localhost:3999'

    path = '/createRoom'
    ws_path = '/ws'
    url = protocol + '://' + host + path
    ws_url = ws_protocol + '://' + host + ws_path
    resp = requests.get(url)

    print(resp)
    print(resp.url)
    print(resp.text)

    # Handle failed authentication and other errors
    if resp.status_code != 200:
        print('command failed:')
        print(resp.text)
        sys.exit(1)


if __name__ == '__main__':
    main()
