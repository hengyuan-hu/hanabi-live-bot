#!/usr/bin/env python

# An example reference bot for the Hanabi Live website
# Written by Zamiel

# # The "dotenv" module does not work in Python 2
# import sys
# if sys.version_info < (3, 0):
#     print('This script requires Python 3.x.')
#     sys.exit(1)

# Imports (standard library)
import os
import argparse

# # Imports (3rd-party)
# import dotenv
import requests

# Imports (local application)
from hanabi_client import HanabiClient


# Authenticate, login to the Hanabi Live WebSocket server, and run forever
def main(name, model, rl):
    # # Load environment variables from the ".env" file
    # dotenv.load_dotenv()

    # use_localhost = os.getenv('USE_LOCALHOST')
    # if use_localhost == '':
    #     print('error: "USE_LOCALHOST" is blank in the ".env" file')
    #     sys.exit(1)
    # if use_localhost == 'true':
    #     use_localhost = True
    # elif use_localhost == 'false':
    #     use_localhost = False
    # else:
    #     print('error: "USE_LOCALHOST" should be set to either "true" or '
    #           '"false" in the ".env" file')
    #     sys.exit(1)

    use_localhost = False
    username = name
    password = name

    # Get an authenticated cookie by POSTing to the login handler
    if use_localhost:
        protocol = 'http'
        ws_protocol = 'ws'
        host = 'localhost'
    else:
        protocol = 'http'
        ws_protocol = 'ws'
        # protocol = 'https'
        # ws_protocol = 'wss'
        host = '54.202.108.64'
    path = '/login'
    ws_path = '/ws'
    url = protocol + '://' + host + path
    ws_url = ws_protocol + '://' + host + ws_path
    print('Authenticating to "' + url + '" with a username of "' + username +
          '".')
    resp = requests.post(
        url,
        {
            'username': name,
            'password': name,
            # 'username': 'test-0',
            # 'password': 'test-0',
            # This is normally the version of the JavaScript client,
            # but it will also accept "bot" as a valid version
            'version': 'bot',
        })

    # Handle failed authentication and other errors
    if resp.status_code != 200:
        print('Authentication failed:')
        print(resp.text)
        sys.exit(1)

    # Scrape the cookie from the response
    cookie = ''
    for header in resp.headers.items():
        if header[0] == 'Set-Cookie':
            cookie = header[1]
            break
    if cookie == '':
        print('Failed to parse the cookie from the authentication response '
              'headers:')
        print(resp.headers)
        sys.exit(1)

    HanabiClient(ws_url, cookie, model, rl)


models = {
    "Bot-Rank": "/private/home/hengyuan/HanabiModels/rl2_lstm1024/HIDE_ACTION1_RNN_HID_DIM1024_LSTM_LAYER2_SEEDc/model4.pthw",
    "Bot-Color": "/private/home/hengyuan/HanabiModels/cr4_cont/HIDE_ACTION1_MIN_CR0.25_NUM_CR1_SEEDa/model0.pthw",
    "Bot-BR": "/private/home/hengyuan/HanabiModels/br1_aux_big_cont/HIDE_ACTION1_RNN_HID_DIM768_ACT_BASE_EPS0.1_SEEDa/model0.pthw",
    "Bot-Clone": "/checkpoint/lep/hanabi/supervised/min_score_0_bs2048/checkpoint-22-19.732.pt",
    "Bot-CH": "/private/home/bcui/OneHanabi/rl/heirarchy_br/10_agents_boltzmann_random_2/heir_8/model_epoch1540.pthw",
    "Bot-Clone-BR": "/checkpoint/lep/hanabi/supervised/br_2p/hide_action_1/RNN_HID_DIM768_HIDE_ACTION1_SEEDa/model0.pthw",
    "Bot-Clone-BRF": "/checkpoint/lep/hanabi/supervised/br_2p/bza_other/RNN_HID_DIM768_BZA_OTHER1_SEEDa/model0.pthw",
    "Bot-IQL": "/private/home/hengyuan/HanabiModels/iql1/HIDE_ACTION1_METHODiql_SEEDa/model0.pthw",
    "Bot-3": "/private/home/hengyuan/HanabiModels/rl2_p25_large/HIDE_ACTION1_NUM_PLAYER3_RNN_HID_DIM1024_LSTM_LAYER1_SEEDa/model0.pthw",
    # "Bot-Discard": "/private/home/hengyuan/HanabiModels/discard_oldest_1/HIDE_ACTION1_MIN_CR0.1_NUM_CR1_SEEDa/model0.pthw"
    "Bot-OffBelief": "/private/home/hengyuan/HanabiModels/off_belief3/METHODiql_MULTI_STEP1_SEEDa/model0.pthw"
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("--name", type=str, default="Bot-BR")
    parser.add_argument("--login_name", type=str, default=None)
    args = parser.parse_args()
    if args.name == "Bot-Clone":
        rl = False
    else:
        rl = True

    if args.login_name is None:
        args.login_name = args.name
    main(args.login_name, models[args.name], rl)
