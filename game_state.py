from constants import *


# # This is just a reference;
# # for a fully-fleged bot, the game state would need to be more specific
# # (e.g. a card object should contain the positive and negative hints that are
# # "on" the card)
# class GameState:
#     replaying_past_actions = True
#     hint_tokens = MAX_HINT_NUM
#     players = []
#     our_index = -1
#     hands = []
#     play_stacks = []
#     discard_pile = []
#     turn = -1


class Knowledge:
    def __init__(self, value_range):
        # Value if hint directly provided the value, or -1 with no direct hint.
        self.value = -1
        # Knowledge from not-value hints.
        self.value_plausible_ = [None for _ in range(value_range)]


class Card:
    def __init__(self, color, rank, order):
        if rank != -1:
            rank -= 1
        assert self.check_card(color, rank)

        self.color = color
        self.rank = rank
        self.order = order

        self.color_knowledge = Knowledge(NUM_COLOR)
        self.rank_knowledge = Knowledge(NUM_RANK)

    def __repr__(self):
        return '%s%s' % ('RYGBPU'[self.color], '12345U'[self.rank])

    @staticmethod
    def check_card(color, rank):
        if color == -1 and rank == -1:
            return True
        if color >= 0 and color < 5 and rank >=0 and rank < 5:
            return True

    def is_valid(self):
        return self.color >= 0 and self.rank >= 0


class Hand:
    def __init__(self):
        self.cards = []

    def __getitem__(self, index):
        return self.cards[index]

    def __len__(self):
        return len(self.cards)

    def get_with_order(self, order):
        for card in self.cards:
            if card.order == order:
                return card
        return None

    def add_card(self, card):
        assert len(self.cards) < HAND_SIZE
        self.cards.append(card)

    def remove_from_hand(self, order):
        to_remove = -1
        for i, card in enumerate(self.cards):
            if card.order == order:
                to_remove = i
        assert to_remove >= 0 and to_remove < len(self.cards)
        card = self.cards.pop(i)
        return card


class FireworkPile:
    def __init__(self):
        self.fire_work = [0 for _ in range(NUM_COLOR)]

    def add_to_pile(self, card):
        assert card.color >= 0 and card.color < NUM_COLOR
        assert card.rank >= 0 and card.color < NUM_RANK

        assert self.fire_work[card.color] == card.rank
        self.fire_work[card.color] += 1
        assert self.fire_work[card.color] <= NUM_RANK
        if self.fire_work[card.color] == NUM_RANK:
            return 1   # get 1 hint token back
        else:
            return 0

    def get_score(self):
        return sum(self.fire_work)


class HleGameState:
    def __init__(self, players, my_name, verbose):
        self.hint_tokens = MAX_HINT_NUM
        self.life_tokens = MAX_LIFE_NUM
        self.num_step = -1
        self.verbose = verbose

        # print(players, my_name)
        self.num_player = len(players)
        # for i, name in enumerate(players):
        #     print(name)
        #     if name == my_name:
        #         self.my_index = i
        self.players = players
        self.my_index = [i for i, name in enumerate(players) if name == my_name][0]

        self.hands = [Hand() for _ in range(self.num_player)]
        self.firework_pile = FireworkPile()
        self.discard_pile = []

        print('init hle game state done')

    ############### public functions for draw and play/discard/hint

    def draw(self, player, color, rank, order):
        if self.verbose:
            print('player: %d draw a card: %s/%s at order: %s' % (player, color, rank, order))
            print('before draw card: hand len is: ', len(self.hands[player]))

        self.hands[player].add_card(Card(color, rank, order))

    def play(self, seat, color, rank, order, success):
        card = Card(color, rank, order)
        if self.verbose:
            print('player %s try to play [%s] and %s' %
                  (seat, card, 'success' if success else 'fail'))
        self.hands[seat].remove_from_hand(order)
        if success:
            finish_color = self.firework_pile.add_to_pile(card)
            self.hint_tokens += finish_color
            if finish_color and self.verbose:
                print('one color is finished, get back 1 hint token')
        else:
            self.discard_pile.append(card)

    def discard(self, seat, color, rank, order):
        assert self.hint_tokens < MAX_HINT_NUM
        self.hint_tokens += 1

        card = Card(color, rank, order)
        self.discard_pile.append(card)

    def hint(self):
        assert self.hint_tokens > 0
        self.hint_tokens -= 1

    ############### helper functions
    def _is_my_turn(self):
        pass

    # def remove_from_hand(self, seat, order):
    #     pass

    # def add_to_firework(self, card):
    #     pass

    # def add_to_discard(self, card):
    #     pass
