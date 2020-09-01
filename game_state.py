import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root, 'pyhanabi'))
from set_path import append_sys_path
append_sys_path()

import numpy as np
import torch
import rela
import hanalearn as hle

from constants import *


def print_observation(vec):
    def print_hand(hand):
        for i in range(5):
            card = hand[i * 25 : (i + 1) * 25]
            print('card: %d, sum %d, argmax %d' % (i, sum(card), np.argmax(card)))

    def print_knowledge(kn):
        for i in range(5):
            card = kn[i*35 : i*35+25]
            color = kn[i*35+25:i*35+30]
            rank = kn[i*35+30:i*35+35]
            # print('card: %d, sum %d, argmax %d', (i, sum(card), np.argmax(card)))
            print('*****')
            card_print = []
            for i in range(5):
                c = ','.join([str(i)[:5] for i in card[5*i:5*(i+1)]])
                card_print.append(c)
            print(card_print)
            print(color)
            print(rank)

    print('--my hand--')
    print_hand(vec[:125])
    print('--your hand--')
    print_hand(vec[125:250])
    print('--hand info--')
    print(vec[250:252])
    print('--deck--: sum: %d' % sum(vec[252:292]))
    print([int(x) for x in vec[252:292]])
    print('--firework--: sum: %d' % sum(vec[292:317]))
    for i in range(5):
        print([int(x) for x in vec[292+5*i:292+5*(i+1)]])
    print('--info--: sum %d' % sum(vec[317:325]))
    print([int(x) for x in vec[317:325]])
    print('--life--: sum %d' % sum(vec[325:328]))
    print([int(x) for x in vec[325:328]])
    print('--discard--')
    for i in range(5):
        print([int(x) for x in vec[328+10*i:328+10*(i+1)]])
    print('--last action--')
    print(sum(vec[378:433]))
    print('--card knowledge--')
    print('--my knowledge--')
    print_knowledge(vec[433:433+175])
    print('--your knowledge--')
    print_knowledge(vec[433+175:])


class Card:
    def __init__(self, color, rank, order):
        if rank != -1:
            rank -= 1
        assert self.check_card(color, rank)
        self.hle_card = hle.HanabiCard(color, rank)
        self.order = order

    def __repr__(self):
        return '%s%s' % ('RYGBPU'[self.color], '12345U'[self.rank])

    @property
    def color(self):
        return self.hle_card.color()

    @property
    def rank(self):
        return self.hle_card.rank()

    @staticmethod
    def check_card(color, rank):
        if color == -1 and rank == -1:
            return True
        if color >= 0 and color < 5 and rank >= 0 and rank < 5:
            return True

    def is_valid(self):
        return self.hle_card.is_valid()


class Hand:
    def __init__(self, hand_size, num_color, num_rank):
        self.hand_size = hand_size
        self.num_color = num_color
        self.num_rank = num_rank

        self.hle_hand = hle.HanabiHand()
        self.cards = []

    def __len__(self):
        return len(self.cards)

    def get_with_order(self, order):
        for card in self.cards:
            if card.order == order:
                return card
        return None

    def add_card(self, card):
        assert len(self.cards) < self.hand_size
        self.cards.append(card)
        self.hle_hand.add_card(
            card.hle_card, hle.CardKnowledge(self.num_color, self.num_rank)
        )

    def remove_from_hand(self, order):
        to_remove = -1
        for i, card in enumerate(self.cards):
            if card.order == order:
                assert to_remove == -1
                to_remove = i
        assert to_remove >= 0 and to_remove < len(self.cards)
        card = self.cards.pop(to_remove)
        self.hle_hand.remove_from_hand(to_remove, [])
        return card


class FireworkPile:
    def __init__(self, num_color, num_rank):
        self.num_color = num_color
        self.num_rank = num_rank
        self.firework = [0 for _ in range(num_color)]

    def add_to_pile(self, card):
        assert card.color >= 0 and card.color < self.num_color
        assert card.rank >= 0 and card.color < self.num_rank

        assert self.firework[card.color] == card.rank
        self.firework[card.color] += 1
        assert self.firework[card.color] <= self.num_color
        if self.firework[card.color] == self.num_rank:
            return 1  # get 1 hint token back
        else:
            return 0

    def get_score(self):
        return sum(self.firework)


class HleGameState:
    def __init__(self, players, my_name, verbose):
        self.num_player = len(players)
        self.players = players
        self.my_index = [i for i, name in enumerate(players) if name == my_name][0]
        print("Create state for %d player game" % self.num_player)

        self.hle_game = hle.HanabiGame({'players': str(len(players))})

        self.hint_tokens = self.hle_game.max_information_tokens()
        self.life_tokens = self.hle_game.max_life_tokens()
        self.deck_size = self.hle_game.max_deck_size()
        self.num_step = 0
        self.verbose = verbose

        self.hands = [
            Hand(
                self.hle_game.hand_size(),
                self.hle_game.num_colors(),
                self.hle_game.num_ranks(),
            )
            for _ in range(self.num_player)
        ]
        self.firework_pile = FireworkPile(
            self.hle_game.num_colors(), self.hle_game.num_ranks()
        )
        self.discard_pile = []
        self.encoder = hle.ObservationEncoder(self.hle_game)

        print('init hle game state done')

    ############### public functions for draw and play/discard/hint

    def draw(self, player, color, rank, order):
        if self.verbose:
            print(
                'player: %d draw a card: %s/%s at order: %s'
                % (player, color, rank, order)
            )
            print('before draw card: hand len is: ', len(self.hands[player]))

        self.deck_size -= 1
        self.hands[player].add_card(Card(color, rank, order))

    def play(self, seat, color, rank, order, success):
        card = Card(color, rank, order)
        if self.verbose:
            print(
                'player %s try to play [%s] and %s'
                % (seat, card, 'success' if success else 'fail')
            )
        removed = self.hands[seat].remove_from_hand(order)
        assert removed.order == order

        if success:
            finish_color = self.firework_pile.add_to_pile(card)
            if self.hint_tokens < self.hle_game.max_information_tokens():
                self.hint_tokens += finish_color
            if finish_color and self.verbose:
                print('one color is finished, get back 1 hint token')
        else:
            self.life_tokens -= 1
            self.discard_pile.append(card.hle_card)

        self.num_step += 1

    def discard(self, seat, color, rank, order):
        assert self.hint_tokens < self.hle_game.max_information_tokens()
        self.hint_tokens += 1

        card = Card(color, rank, order)
        removed = self.hands[seat].remove_from_hand(order)
        assert removed.order == order
        self.discard_pile.append(card.hle_card)

        self.num_step += 1

    def hint(self, giver, target, hint_type, hint_value, hinted_card_orders):
        hint_type = ['color_hint', 'rank_hint'][hint_type]
        if hint_type == 'rank_hint':
            hint_value -= 1
        # print('>>>> hint type:', hint_type, ', hint value:', hint_value)
        assert self.hint_tokens > 0
        self.hint_tokens -= 1

        assert giver != target
        hand = self.hands[target]
        knowledge = hand.hle_hand.knowledge_()
        hinted_count = 0
        for i, card in enumerate(hand.cards):
            # knowledge[i] = knowledge[i]owledge[i]
            # print('@@@', i, card.order, hinted_card_orders)
            mismatch = False

            if card.order in hinted_card_orders:
                hinted_count += 1
                if hint_type == 'color_hint':
                    knowledge[i].apply_is_color_hint(hint_value)
                    if card.is_valid() and card.color != hint_value:
                        mismatch = 1  # assert card.color == hint_value
                else:
                    knowledge[i].apply_is_rank_hint(hint_value)
                    if card.is_valid() and card.rank != hint_value:
                        mismatch = 2  # assert card.color != hint_value
            else:
                if hint_type == 'color_hint':
                    knowledge[i].apply_is_not_color_hint(hint_value)
                    if card.is_valid() and card.color == hint_value:
                        mismatch = 3  # assert card.value = hint_value
                else:
                    knowledge[i].apply_is_not_rank_hint(hint_value)
                    if card.is_valid() and card.rank == hint_value:
                        mismatch = 4  # assert card.value != hint_value

            if mismatch:
                print('ERROR: MISMATCH, type %d' % mismatch)
                print('card %d, order %d, %s' %
                      (i, hand.cards[i].order, hand.cards[i].hle_card.to_string()))
                print('%d: knowledge %s' % (i, knowledge[i].to_string()))
                assert False

        assert hinted_count == len(hinted_card_orders)
        self.num_step += 1

    def get_observation(self):
        hands = [hand.hle_hand for hand in self.hands]
        legal_moves = self.get_legal_moves()
        if self.verbose and self.is_my_turn():
            print('Legal Moves:')
            for m in legal_moves:
                print('\t', m.to_string())
        obs = hle.HanabiObservation(
            self.current_player(),
            self.my_index,
            hands,
            self.discard_pile,
            self.firework_pile.firework,
            self.deck_size,
            self.hint_tokens,
            self.life_tokens,
            legal_moves,
            self.hle_game,
        )
        return obs

    def get_observation_in_vector(self):
        obs = self.get_observation()
        vec = self.encoder.encode(obs, False, [], False, [], [], True)
        # print_observation(vec)
        return vec

    def get_legal_moves_in_vector(self):
        legal_moves = [0 for _ in range(self.hle_game.max_moves() + 1)]
        if self.is_my_turn():
            moves = self.get_legal_moves()
            for m in moves:
                uid = self.hle_game.get_move_uid(m)
                legal_moves[uid] = 1

            if self.num_player == 2:
                assert len(legal_moves) == 21
        else:
            legal_moves[-1] = 1
        return legal_moves

    def observe(self):
        obs_vec = self.get_observation_in_vector()
        obs = torch.tensor(obs_vec, dtype=torch.float32)
        priv_s = obs[125:].unsqueeze(0)
        publ_s = obs[125 * self.num_player:].unsqueeze(0)

        legal_move_vec = self.get_legal_moves_in_vector()
        legal_move = torch.tensor(legal_move_vec, dtype=torch.float32)
        return priv_s, publ_s, legal_move

    def convert_move(self, hle_move):
        type_map = {
            hle.MoveType.Play: ACTION.PLAY,
            hle.MoveType.Discard: ACTION.DISCARD,
            hle.MoveType.RevealColor: ACTION.COLOR_HINT,
            hle.MoveType.RevealRank: ACTION.RANK_HINT,
        }

        if hle_move.move_type() in [hle.MoveType.Play, hle.MoveType.Discard]:
            card_idx = hle_move.card_index()
            assert card_idx >= 0 and card_idx < len(self.hands[self.my_index])
            # for c in self.hands[self.my_index].cards:
            #     print('>>card', c.order)
            card_order = self.hands[self.my_index].cards[card_idx].order
            return {
                'type': type_map[hle_move.move_type()],
                'target': card_order,
            }

        target_idx = (self.my_index + hle_move.target_offset()) % self.num_player
        if hle_move.move_type() == hle.MoveType.RevealColor:
            value = hle_move.color()
            assert value >= 0 and value < self.hle_game.num_colors()
        else:
            value = hle_move.rank()
            assert value >= 0 and value < self.hle_game.num_ranks()
            value += 1  # hanabi-live is 1 indexed for rank

        return {
            'type': type_map[hle_move.move_type()],
            'target': target_idx,
            'value': value,
        }

    ############### helper functions
    def current_player(self):
        return self.num_step % self.num_player

    def is_my_turn(self):
        return self.current_player() == self.my_index

    def get_legal_moves(self):
        moves = []
        if self.hint_tokens < self.hle_game.max_information_tokens():
            for i in range(len(self.hands[self.my_index])):
                moves.append(hle.HanabiMove(hle.MoveType.Discard, i, 1, -1, -1))

        for i in range(len(self.hands[self.my_index])):
            moves.append(hle.HanabiMove(hle.MoveType.Play, i, 1, -1, -1))

        if self.hint_tokens == 0:
            return moves

        for i, hand in enumerate(self.hands):
            possible_hint_color = []
            possible_hint_rank = []
            if i == self.my_index:
                continue

            for card in hand.cards:
                player_offset = (i - self.my_index) % self.num_player
                if card.color not in possible_hint_color:
                    possible_hint_color.append(card.color)
                    move = hle.HanabiMove(
                        hle.MoveType.RevealColor, -1, player_offset, card.color, -1
                    )
                    moves.append(move)
                if card.rank not in possible_hint_rank:
                    possible_hint_rank.append(card.rank)
                    move = hle.HanabiMove(
                        hle.MoveType.RevealRank, -1, player_offset, -1, card.rank
                    )
                    moves.append(move)

        return moves

    def get_score(self):
        return self.firework_pile.get_score()
