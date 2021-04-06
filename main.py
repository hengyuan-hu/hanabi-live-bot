# Imports (standard library)
import os
import argparse

# Imports (3rd-party)
import requests

# Imports (local application)
from hanabi_client import HanabiClient


# Authenticate, login to the Hanabi Live WebSocket server, and run forever
def main(name, model, rl):
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
    "Bot-Baseline": "/private/home/hengyuan/HanabiModels/aamas1/HIDE_ACTION0_RNN_HID_DIM1024_LSTM_LAYER2_SEEDa/model0.pthw",
    "Bot-HideAction": "/private/home/hengyuan/HanabiModels/aamas1/HIDE_ACTION1_RNN_HID_DIM1024_LSTM_LAYER2_SEEDa/model0.pthw",
    "Bot-Boltzmann": "/private/home/hengyuan/HanabiModels/aamas3_boltzmann/HIDE_ACTION0_RESCALE0_RNN_HID_DIM1024_LSTM_LAYER2_SEEDa/model0.pthw",
    "Bot-Rank": "/private/home/hengyuan/HanabiModels/rl2_lstm1024/HIDE_ACTION1_RNN_HID_DIM1024_LSTM_LAYER2_SEEDc/model4.pthw",
    "Bot-Color": "/private/home/hengyuan/HanabiModels/cr4_cont/HIDE_ACTION1_MIN_CR0.25_NUM_CR1_SEEDa/model0.pthw",
    "Bot-BR": "/private/home/hengyuan/HanabiModels/br1_aux_big_cont/HIDE_ACTION1_RNN_HID_DIM768_ACT_BASE_EPS0.1_SEEDa/model0.pthw",
    "Bot-Clone": "/checkpoint/lep/hanabi/supervised/min_score_0_bs2048/checkpoint-22-19.732.pt",
    "Bot-Clone3": "/checkpoint/dwu/hanabi/clonebot/run3ponlinecolorshuf-0/checkpoint-48-17.547.pt",
    "Bot-CH": "/private/home/bcui/OneHanabi/rl/heirarchy_br/10_agents_boltzmann_random_2/heir_8/model_epoch1540.pthw",
    "Bot-Clone-BR": "/checkpoint/lep/hanabi/supervised/br_2p/RNN_HID_DIM1024_SEEDa/model0.pthw",
    "Bot-Clone-BRF": "/checkpoint/lep/hanabi/supervised/br_2p/bza_other/RNN_HID_DIM768_BZA_OTHER1_SEEDa/model0.pthw",
    "Bot-IQL": "/private/home/hengyuan/HanabiModels/iql1/HIDE_ACTION1_METHODiql_SEEDa/model0.pthw",
    "Bot-3": "/private/home/hengyuan/HanabiModels/rl2_p25_large/HIDE_ACTION1_NUM_PLAYER3_RNN_HID_DIM1024_LSTM_LAYER1_SEEDa/model0.pthw",
    "Bot-OBL1": "/private/home/hengyuan/HanabiModels/new_off_belief6/HIDE_ACTION0_OFF_BELIEF1_RNN_HID_DIM512_SEEDa/model0.pthw",
    "Bot-L2-OB": "/private/home/hengyuan/HanabiModels/new_l2_off_belief1/OFF_BELIEF1_LOAD1_BELIEF_SEEDa/model_epoch50.pthw",
    "Bot-L3-OB": "/private/home/hengyuan/HanabiModels/new_l3_off_belief1/OFF_BELIEF1_LOAD1_BELIEF_LOAD1_SEEDa/model0.pthw",
    "Bot-L4-OB": "/private/home/hengyuan/HanabiModels/new_l4_off_belief1/OFF_BELIEF1_LOAD1_BELIEF_LOAD1_SEEDa/model_epoch50.pthw",
    "Bot-L2-OB_FNL": "/private/home/hengyuan/HanabiModels/new_l2_off_belief1/OFF_BELIEF1_LOAD1_BELIEF_SEEDa/model0.pthw",
    "Bot-New-OBL1": "/private/home/hengyuan/HanabiModels/icml_run3_OBL1/OFF_BELIEF1_SHUFFLE_COLOR0_BZA1_BELIEF_a/model0.pthw",
    "Bot-New2-OBL1": "/private/home/hengyuan/HanabiModels/icml_run3_OBL1/OFF_BELIEF1_SHUFFLE_COLOR0_BZA0_BELIEF_a/model0.pthw",
    "Bot-BC-RL": "/checkpoint/hengyuan/hanabi_benchmark/rl_bc1/NETlstm_PRED0.25_CLONE_WEIGHT0.1_CLONE_T0.1_SEEDa/model0.pthw",
    "Bot-BCRL3": "/checkpoint/hengyuan/hanabi_benchmark/rl_bc_p3/NETlstm_NUM_PLAYER3_PRED0.25_CLONE_WEIGHT0.1_CLONE_T0.1_SEEDa/model0.pthw",
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("--name", type=str, default="Bot-BR")
    parser.add_argument("--login_name", type=str, default=None)
    args = parser.parse_args()
    if "Bot-Clone" in args.name:
        rl = False
    else:
        rl = True

    if args.login_name is None:
        args.login_name = args.name
    main(args.login_name, models[args.name], rl)
