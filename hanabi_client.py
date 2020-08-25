# Imports (standard library)
import os
import sys
import json
import pprint
import threading
import time
import random

# Imports (3rd-party)
import websocket
import torch
import numpy as np

# Imports (local application)
from constants import ACTION
from game_state import *

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root, 'pyhanabi'))
import r2d2
import supervised_model
from utils import load_agent


class HanabiClient:
    def __init__(self, url, cookie, model_path, rl):
        # Initialize all class variables
        self.commandHandlers = {}
        self.tables = {}
        self.username = ''
        self.ws = None
        self.games = {}

        # model loading and related
        # NOTE: last_action feature is not implemented AT ALL!!!
        self.rl = rl
        if rl:
            self.agent, cfgs = load_agent(model_path, {"device": "cpu", "vdn": False})
            assert cfgs["hide_action"]
        else:
            self.agent = supervised_model.SupervisedAgent("cpu", 1024, 21, 1)
            self.agent.load_state_dict(torch.load(model_path))
        self.rnn_hids = {}
        self.next_moves = {}
        self.scores = []

        # Initialize the Hanabi Live command handlers (for the lobby)
        self.commandHandlers['welcome'] = self.welcome
        self.commandHandlers['warning'] = self.warning
        self.commandHandlers['error'] = self.error
        self.commandHandlers['chat'] = self.chat
        self.commandHandlers['table'] = self.table
        self.commandHandlers['tableList'] = self.table_list
        self.commandHandlers['tableGone'] = self.table_gone
        self.commandHandlers['tableStart'] = self.table_start

        # Initialize the Hanabi Live command handlers (for the game)
        self.commandHandlers['init'] = self.init
        self.commandHandlers['gameAction'] = self.game_action
        self.commandHandlers['gameActionList'] = self.game_action_list
        self.commandHandlers['yourTurn'] = self.your_turn
        self.commandHandlers['databaseID'] = self.database_id

        # Start the WebSocket client
        print('Connecting to "' + url + '".')

        self.ws = websocket.WebSocketApp(
            url,
            on_message=lambda ws, message: self.websocket_message(ws, message),
            on_error=lambda ws, error: self.websocket_error(ws, error),
            on_open=lambda ws: self.websocket_open(ws),
            on_close=lambda ws: self.websocket_close(ws),
            cookie=cookie,
        )
        self.ws.run_forever()

    # ------------------
    # WebSocket Handlers
    # ------------------

    def websocket_message(self, ws, message):
        # WebSocket messages from the server come in the format of:
        # commandName {"data1":"data2"}
        # For more information, see:
        # https://github.com/Zamiell/hanabi-live/blob/master/src/websocketMessage.go
        result = message.split(' ', 1)  # Split it into two things
        if len(result) != 1 and len(result) != 2:
            print('error: recieved an invalid WebSocket message:')
            print(message)
            return

        command = result[0]
        try:
            data = json.loads(result[1])
        except:
            print('error: the JSON data for the command of "' + command +
                  '" was invalid')
            return

        if command in self.commandHandlers:
            # print('debug: got command "' + command + '"')
            try:
                self.commandHandlers[command](data)
            except Exception as e:
                print('error: command handler for "' + command + '" failed:',
                      e)
                return
        else:
            pass
            # print('debug: ignoring command "' + command + '"')

    def websocket_error(self, ws, error):
        print('Encountered a WebSocket error:', error)

    def websocket_close(self, ws):
        print('WebSocket connection closed.')

    def websocket_open(self, ws):
        print('Successfully established WebSocket connection.')

    # ------------------------------------
    # Hanabi Live Command Handlers (Lobby)
    # ------------------------------------

    def welcome(self, data):
        # The "welcome" message is the first message that the server sends us
        # once we have established a connection
        # It contains our username, settings, and so forth
        self.username = data['username']

    def error(self, data):
        # Either we have done something wrong,
        # or something has gone wrong on the server
        print(data)

    def warning(self, data):
        # We have done something wrong
        print(data)

    def chat(self, data):
        # We only care about private messages
        if data['recipient'] != self.username:
            return

        # We only care about private messages that start with a forward slash
        if not data['msg'].startswith('/'):
            return
        data['msg'] = data['msg'][1:]  # Remove the slash

        # We want to split it into two things
        result = data['msg'].split(' ', 1)
        command = result[0]

        if command == 'join':
            self.chat_join(data)
        else:
            self.chat_reply('That is not a valid command.', data['who'])

    def chat_join(self, data):
        # Someone sent a private message to the bot and requested that we join
        # their game
        # Find the table that the current user is currently in
        table_id = None
        for table in self.tables.values():
            # Ignore games that have already started (and shared replays)
            if table['running']:
                continue

            if data['who'] in table['players']:
                if len(table['players']) == 6:
                    msg = ('Your game is full. Please make room for me before '
                           'requesting that I join your game.')
                    self.chat_reply(msg, data['who'])
                    return

                table_id = table['id']
                break

        if table_id is None:
            self.chat_reply(
                'Please create a table first before requesting '
                'that I join your game.', data['who'])
            return

        self.send('tableJoin', {
            'tableID': table_id,
        })

    def table(self, data):
        self.tables[data['id']] = data

    def table_list(self, data_list):
        for data in data_list:
            self.table(data)

    def table_gone(self, data):
        del self.tables[data['id']]

    def table_start(self, data):
        # The server has told us that a game that we are in is starting
        # So, the next step is to request some high-level information about the
        # game (e.g. number of players)
        # The server will respond with an "init" command
        self.send('getGameInfo1', {
            'tableID': data['tableID'],
        })

    # -----------------------------------
    # Hanabi Live Command Handlers (Game)
    # -----------------------------------

    def init(self, data):
        # At the beginning of the game, the server sends us some high-level
        # data about the game, including the names and ordering of the players
        # at the table

        # Make a new game state and store it on the "games" dictionary
        state = HleGameState(data['names'], self.username, True)
        self.games[data['tableID']] = state

        print('>>>>> init for table %s called <<<<<' % data['tableID'])
        self.rnn_hids[data['tableID']] = self.agent.get_h0(1)
        self.next_moves[data['tableID']] = None
        print('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<')

        # # Initialize the hands for each player (an array of cards)
        # for i in range(len(state.players)):
        #     state.hands.append([])

        # Initialize the play stacks
        '''
        This is hard coded to 5 because there 5 suits in a no variant game
        Hanabi Live supports variants that have 3, 4, and 6 suits
        TODO This code should compare "data['variant']" to the "variants.json"
        file in order to determine the correct amount of suits
        https://raw.githubusercontent.com/Zamiell/hanabi-live/master/public/js/src/data/variants.json
        '''
        # for i in range(5):
        #     state.play_stacks.append([])

        # At this point, the JavaScript client would have enough information to
        # load and display the game UI; for our purposes, we do not need to
        # load a UI, so we can just jump directly to the next step
        # Now, we request the specific actions that have taken place thus far
        # in the game
        self.send('getGameInfo2', {
            'tableID': data['tableID'],
        })

    def game_action(self, data):
        # We just recieved a new action for an ongoing game
        self.handle_action(data['action'], data['tableID'])

    def game_action_list(self, data):
        # We just recieved a list of all of the actions that have occurred thus
        # far in the game
        for action in data['list']:
            self.handle_action(action, data['tableID'])

    def handle_action(self, data, table_id):
        """action comes in the order of:
        [status, turn, action], [status, turn, action]...
        """

        if data['type'] == 'text':
            return

        print('-------------begin: handle_action:-------------')
        pprint.pprint(data)

        # Local variables
        state = self.games[table_id]

        if data['type'] == 'status':
            assert data['clues'] == state.hint_tokens
            assert data['score'] == state.get_score()
        elif data['type'] == 'draw':
            # Add the newly drawn card to the player's hand
            state.draw(
                data['who'], data['suit'], data['rank'], data['order']
            )
        elif data['type'] == 'play' or (data['type'] == 'discard' and data['failed']):
            # success play, and failed play (encoded as discard)
            seat = data['which']['index']
            order = data['which']['order']
            color = data['which']['suit']
            rank = data['which']['rank']
            if data['type'] == 'play':
                success = True
            else:
                success = False
            state.play(seat, color, rank, order, success)
        elif data['type'] == 'discard':
            seat = data['which']['index']
            order = data['which']['order']
            color = data['which']['suit']
            rank = data['which']['rank']
            state.discard(seat, color, rank, order)
        elif data['type'] == 'clue':
            giver = data['giver']
            target = data['target']
            hint_type = data['clue']['type']
            hint_value = data['clue']['value']
            hinted_card_orders = data['list']
            state.hint(giver, target, hint_type, hint_value, hinted_card_orders)
        elif data['type'] == 'turn':
            if data['who'] == -1:
                return

            assert state.num_step == data['num']
            print('#STEP: %d, %d, my index: %d, my turn? %s'
                  % (state.num_step, data['num'], state.my_index, state.is_my_turn()))
            print('Bot observing')
            obs_vec = state.get_observation_in_vector()
            legal_move_vec = state.get_legal_moves_in_vector()
            obs = torch.tensor(obs_vec, dtype=torch.float32)
            priv_s = obs[125:].unsqueeze(0)
            publ_s = obs[250:].unsqueeze(0)
            legal_move = torch.tensor(legal_move_vec, dtype=torch.float32)

            if self.rl:
                with torch.no_grad():
                    adv, self.rnn_hids[table_id], _ = self.agent.online_net.act(
                        priv_s, publ_s, self.rnn_hids[table_id]
                    )
                if state.is_my_turn():
                    assert self.next_moves[table_id] is None
                    legal_adv = (1 + adv - adv.min()) * legal_move
                    action = legal_adv.argmax(1).detach()
                    action_uid = int(action.item())
                    move = state.hle_game.get_move(action_uid)

                    legal_adv = adv - (1 - legal_move) * 1e9
                    prob = torch.nn.functional.softmax(legal_adv * 5, 1)
                    logp = torch.nn.functional.log_softmax(legal_adv * 5, 1)
                    xent = -(prob * logp).sum().item()
                    self.next_moves[table_id] = (move, xent)
                else:
                    self.next_moves[table_id] = None
            else:
                # clone bot
                with torch.no_grad():
                    logit, self.rnn_hids[table_id] = self.agent.forward(
                        priv_s.unsqueeze(0), publ_s.unsqueeze(0), self.rnn_hids[table_id]
                    )
                if state.is_my_turn():
                    logit = logit.squeeze()
                    action = (logit - (1 - legal_move) * 1e9).argmax(0)
                    action_uid = int(action.item())
                    move = state.hle_game.get_move(action_uid)
                    self.next_moves[table_id] = (move, 0)
                else:
                    self.next_moves[table_id] = None
        elif data['type'] == 'status':
            assert state.get_score() == data['score']
            assert state.hint_tokens == data['clues']
        print('===============================================')

    def your_turn(self, data):
        # The "yourTurn" command is only sent when it is our turn
        # (in the present, as opposed to recieving a "game_action" message
        # about a turn in the past)
        # Query the AI functions to see what to do

        # th = threading.Thread(target=self.decide_action, args=(data['tableID'],))
        # th.start()
        self.decide_action(data['tableID'])

    def database_id(self, data):
        # Games are transformed into shared replays after they are copmleted
        # The server sends a "databaseID" message when the game has ended
        # Use this as a signal to leave the shared replay
        self.send('tableUnattend', {
            'tableID': data['tableID'],
        })

        # Delete the game state for the game to free up memory
        self.scores.append(self.games[data['tableID']].get_score())
        self.games.pop(data['tableID'])
        self.rnn_hids.pop(data['tableID'])
        self.next_moves.pop(data['tableID'])
        print("finished %d games, mean score: %.2f" % (len(self.scores), np.mean(self.scores)))

    # ------------
    # AI functions
    # ------------

    def decide_action(self, table_id):
        state = self.games[table_id]
        move, xent = self.next_moves[table_id]
        print("$$$ MODEL ACTION: %s $$$" % (move.to_string()))

        move_json = state.convert_move(move)
        move_json['tableID'] = table_id
        print('$$$ json move: %s $$$' % move_json)
        # if xent > 0:
        #     print('$$$Xent:', xent)
        #     time.sleep(max(0, (xent - 1) / (2.9 - 1) * 10))  # ln(20) ~= 2.9
        self.send('action', move_json)

    # -----------
    # Subroutines
    # -----------

    def chat_reply(self, message, recipient):
        self.send('chatPM', {
            'msg': message,
            'recipient': recipient,
            'room': 'lobby',
        })

    def send(self, command, data):
        if not isinstance(data, dict):
            data = {}
        self.ws.send(command + ' ' + json.dumps(data))
        # print('debug: sent command "' + command + '"')
