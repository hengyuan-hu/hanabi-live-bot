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
import random
import string


# Authenticate, login to the Hanabi Live WebSocket server, and run forever
def main(test):
    # Load environment variables from the ".env" file
    dotenv.load_dotenv()

    protocol = 'http'
    ws_protocol = 'ws'
    host = '54.202.108.64'
    # host = 'localhost:3999'

    usernames = []
    passwords = []

    if test:
        for i in range(num_players):
            username = 'test-%i' % i
            usernames.append(username)
            passwords.append(username)
    else:
        for i in range(num_players):
            username = 'player-%s' % random_string(5)
            usernames.append(username)
            passwords.append(random_string())

    print("Players:")
    for i, (username, password) in enumerate(zip(usernames, passwords)):
        print('%d: %s, %s' % (i, username, password))


    path = '/login'
    ws_path = '/ws'
    url = protocol + '://' + host + path
    ws_url = ws_protocol + '://' + host + ws_path

    for username, password in zip(usernames, passwords):
        print('Authenticating to "' + url + '" with a username of "' + username +'".')
        resp = requests.post(
            url,
            {
                'username': username,
                'password': password,
                # This is normally the version of the JavaScript client,
                # but it will also accept "bot" as a valid version
                'version': 'bot',
            })
        # Handle failed authentication and other errors
        if resp.status_code != 200:
            print('Authentication failed:')
            print(resp.text)
            sys.exit(1)
        else:
            print('Login success')

        resp = requests.get(protocol + '://' + host + '/logout')
        if resp.status_code != 200:
            print('Authentication failed:')
            print(resp.text)
            sys.exit(1)
        else:
            print('Logout success')


num_players = 2

seed = 1
random.seed(seed)

def random_string(length=10):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


if __name__ == '__main__':
    main(True)
