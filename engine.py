import pickle
import torch
from game_state import *


def load_deck(deck_file):
    with open(deck_file, 'r') as f:
        line = f.readlines()

    deck = []
    for i, l in enumerate(line):
        l = l.strip()
        assert len(l) == 2
        rank = int(l[0])
        color = ord(l[1]) - ord('a')

        deck.append(Card(color, rank, i))

    return deck


def print_priv_s(vec):
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

    vec = [0] * 125 + vec
    # print('--my hand--')
    # print_hand(vec[:125])
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


def compare(priv_s, ref_priv_s):
    if not priv_s == ref_priv_s:
        print_priv_s(priv_s)
        print('--------------------')
        # print(len((ref_priv_s)))
        print_priv_s(ref_priv_s)
        print('====================')
        print(priv_s == ref_priv_s)

    return priv_s == ref_priv_s


def run_game(deck_file, obs_file, agents, verbose):
    deck = load_deck(deck_file)
    priv_s_history = pickle.load(open(obs_file, 'rb'))

    players = ['p0', 'p1']
    state0 = HleGameState(players, 'p0', verbose)
    state1 = HleGameState(players, 'p1', verbose)
    states = [state0, state1]

    playable_rank = [0, 0, 0, 0, 0]

    # deal init hand
    for p in [0, 1]:
        for _ in range(5):
            card = deck.pop(0)
            for s in states:
                s.draw(p, card.color, card.rank+1, card.order)

    active_player = 0
    count_down = 0
    rnn_hids = [agent.get_h0(1) for agent in agents]
    history_counter = 0
    while state0.life_tokens > 0 and state0.get_score() < 25:
        if len(deck) == 0:
            count_down += 1
        if count_down > 2:
            break

        active_action = None
        for p in [0, 1]:
            if verbose:
                print("player %d observe/play" % p)
            state = states[p]
            obs_vec = state.get_observation_in_vector()
            priv_s = obs_vec[125:]
            # print(history_counter, len(deck), count_down)
            ref_priv_s = priv_s_history[history_counter]
            if not compare(priv_s, ref_priv_s):
                print('>>>WRONG:', obs_file)
                assert False

            history_counter += 1

            legal_move_vec = state.get_legal_moves_in_vector()
            obs = torch.tensor(obs_vec, dtype=torch.float32)
            priv_s = obs[125:].unsqueeze(0)
            publ_s = obs[250:].unsqueeze(0)
            legal_move = torch.tensor(legal_move_vec, dtype=torch.float32)
            # print('>>>legal_move:', legal_move)

            agent = agents[p]
            action, rnn_hids[p], _ = agent.greedy_act(
                priv_s, publ_s, legal_move, rnn_hids[p]
            )
            action_uid = int(action.item())
            # print('action uid', action_uid, 'active_player:', active_player)
            if p != active_player:
                assert action_uid == 20
            else:
                active_action = action_uid

        move = states[active_player].hle_game.get_move(active_action)
        if verbose:
            print("Player", active_player, "perform: ", move.to_string())

        # execute move
        if move.move_type() == hle.MoveType.Discard:
            card_idx = move.card_index()
            card = states[active_player].hands[active_player].cards[card_idx]
            for s in states:
                s.discard(active_player, card.color, card.rank+1, card.order)
        elif move.move_type() == hle.MoveType.Play:
            card_idx = move.card_index()
            card = states[active_player].hands[active_player].cards[card_idx]
            if card.rank == playable_rank[card.color]:
                success = True
                playable_rank[card.color] += 1
            else:
                success = False
            for s in states:
                s.play(active_player, card.color, card.rank+1, card.order, success)
        else:
            if move.move_type() == hle.MoveType.RevealColor:
                hint_value = move.color()
                hint_type = 0
            else:
                hint_value = move.rank() + 1
                hint_type = 1
            for s in states:
                target_cards = states[active_player].hands[1-active_player].cards
                hint_orders = []
                for c in target_cards:
                    if move.move_type() == hle.MoveType.RevealColor and move.color() == c.color:
                        hint_orders.append(c.order)
                    if move.move_type() == hle.MoveType.RevealRank and move.rank() == c.rank:
                        hint_orders.append(c.order)

                s.hint(active_player, 1-active_player, hint_type, hint_value, hint_orders)

        if move.move_type() in [hle.MoveType.Play, hle.MoveType.Discard]:
            if len(deck) > 0:
                new_card = deck.pop(0)
                for s in states:
                    s.draw(active_player, new_card.color, new_card.rank+1, new_card.order)

        active_player = 1 - active_player
        if verbose:
            print("===================step %d done==================" % states[0].num_step)
    print("final score: ", states[0].get_score())
    return states[0].get_score()


root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(root, 'pyhanabi'))
import r2d2
from utils import load_agent


weight = '/private/home/hengyuan/HanabiModels/rl1_fix_o/HIDE_ACTION1_PRED0.25_MIN_T0.01_MAX_T0.1_SEEDb/model0.pthw'


seed = 8
deck = '/private/home/hengyuan/NewHanabi/rl/pyhanabi/exps/play/deck_seed%d.txt' % seed
ref = '/private/home/hengyuan/NewHanabi/rl/pyhanabi/exps/play/priv_s%d.pkl' % seed
agent, _ = load_agent(weight, {"device": "cpu"})
score = run_game(deck, ref, [agent, agent], False)

scores = []
for seed in range(1, 101):
    deck = '/private/home/hengyuan/NewHanabi/rl/pyhanabi/exps/play/deck_seed%d.txt' % seed
    ref = '/private/home/hengyuan/NewHanabi/rl/pyhanabi/exps/play/priv_s%d.pkl' % seed
    agent, _ = load_agent(weight, {"device": "cpu"})
    score = run_game(deck, ref, [agent, agent], False)
    print('pass, ', seed)
    scores.append(score)


import numpy as np
print('avg score:', np.mean(scores))
