# Imports (standard library)
import os
import sys
import json
import pprint

# Imports (3rd-party)
import websocket
import torch

# Imports (local application)
from constants import ACTION
from game_state import *

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root, 'pyhanabi'))
import r2d2
from utils import load_agent


class HanabiClient:
    def __init__(self, url, cookie, model_path):
        # Initialize all class variables
        self.commandHandlers = {}
        self.tables = {}
        self.username = ''
        self.ws = None
        self.games = {}

        # model loading and related
        self.agent, _ = load_agent(model_path, {"device": "cpu"})
        self.rnn_hid = self.agent.get_h0(1)

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

        print('>>>>>>> init called, set rnn hid = 0')
        self.rnn_hid = self.agent.get_h0(1)
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
        # print('debug: got a game action of "' + data['type'] + '" for table ' +
        #       str(table_id))
        if data['type'] == 'text':
            return

        print('-------------begin: handle_action:-------------')
        pprint.pprint(data)

        # Local variables
        state = self.games[table_id]

        if data['type'] == 'draw':
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
            state.num_step = data['num']
            print('#STEP: ', state.num_step, ', MY INDEX: ', state.my_index)

        print('===============================================')

    def your_turn(self, data):
        # The "yourTurn" command is only sent when it is our turn
        # (in the present, as opposed to recieving a "game_action" message
        # about a turn in the past)
        # Query the AI functions to see what to do
        self.decide_action(data['tableID'])

    def database_id(self, data):
        # Games are transformed into shared replays after they are copmleted
        # The server sends a "databaseID" message when the game has ended
        # Use this as a signal to leave the shared replay
        self.send('tableUnattend', {
            'tableID': data['tableID'],
        })

        # Delete the game state for the game to free up memory
        del self.games[data['tableID']]

    # ------------
    # AI functions
    # ------------

    def decide_action(self, table_id):
        # Local variables
        state = self.games[table_id]

        # The server expects to be told about actions in the following format:
        # https://github.com/Zamiell/hanabi-live/blob/master/src/command_action.go
        obs_vec = state.get_observation_in_vector()
        legal_move_vec = state.get_legal_moves_in_vector()
        obs = torch.tensor(obs_vec, dtype=torch.float32)
        priv_s = obs[125:].unsqueeze(0)
        publ_s = obs[250:].unsqueeze(0)
        legal_move = torch.tensor(legal_move_vec, dtype=torch.float32)

        action, self.rnn_hid, _ = self.agent.greedy_act(
            priv_s, publ_s, legal_move, self.rnn_hid
        )
        action_uid = int(action.item())
        move = state.hle_game.get_move(action_uid)
        print("$$$ MODEL ACTION: UID: %d, %s $$$" % (action_uid, move.to_string()))

        move_json = state.convert_move(move)
        move_json['tableID'] = table_id
        print('$$$ json move: %s $$$' % move_json)
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

    # # "seat" is the index of the player
    # def remove_card_from_hand(self, state, seat, order):
    #     hand = state.hands[seat]
    #     card_index = -1
    #     for i in range(len(hand)):
    #         card = hand[i]
    #         if card['order'] == order:
    #             card_index = i
    #     if card_index == -1:
    #         print('error: unable to find card with order ' + str(order) + ' in'
    #               'the hand of player ' + str(seat))
    #         return None
    #     card = hand[card_index]
    #     print('>>>before pop?', len(state.hands[seat]))
    #     hand.pop(card_index)
    #     print('>>>after pop?', len(state.hands[seat]))
    #     return card
