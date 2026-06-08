"""
reversi_ai.py

State-of-the-Art AI Engine for Reversi using Bitboards, Iterative Deepening, 
Principal Variation Search (PVS), History Heuristics, Transposition Tables, 
Killer Moves, and an Extreme evaluation function.
"""

import time
from reversi_logic import BLACK, WHITE, EMPTY

# --- Egaroucid-Inspired Positional Weights ---
EARLY_WEIGHTS = [
    [100, -20, 10,  5,  5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [ 10,  -2,  5,  1,  1,  5,  -2,  10],
    [  5,  -2,  1,  0,  0,  1,  -2,   5],
    [  5,  -2,  1,  0,  0,  1,  -2,   5],
    [ 10,  -2,  5,  1,  1,  5,  -2,  10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10,  5,  5, 10, -20, 100]
]

MID_WEIGHTS = [
    [120, -10, 20, 10, 10, 20, -10, 120],
    [-10, -20,  1,  1,  1,  1, -20, -10],
    [ 20,   1,  5,  2,  2,  5,   1,  20],
    [ 10,   1,  2,  1,  1,  2,   1,  10],
    [ 10,   1,  2,  1,  1,  2,   1,  10],
    [ 20,   1,  5,  2,  2,  5,   1,  20],
    [-10, -20,  1,  1,  1,  1, -20, -10],
    [120, -10, 20, 10, 10, 20, -10, 120]
]

# Bitboard constants
CORNERS = 0x8100000000000081
X_SQUARES = 0x0042000000004200
C_SQUARES = 0x4281000000008142

MASKS = [
    (1, 0xFEFEFEFEFEFEFEFE),  # Right
    (-1, 0x7F7F7F7F7F7F7F7F), # Left
    (8, 0xFFFFFFFFFFFFFFFF),  # Down
    (-8, 0xFFFFFFFFFFFFFFFF), # Up
    (9, 0xFEFEFEFEFEFEFEFE),  # Down-Right
    (7, 0x7F7F7F7F7F7F7F7F),  # Down-Left
    (-7, 0xFEFEFEFEFEFEFEFE), # Up-Right
    (-9, 0x7F7F7F7F7F7F7F7F)  # Up-Left
]

def get_moves_bb(P, O):
    E = ~(P | O) & 0xFFFFFFFFFFFFFFFF
    moves = 0
    for shift, mask in MASKS:
        if shift > 0:
            c = O & ((P << shift) & mask)
            for _ in range(5): c |= O & ((c << shift) & mask)
            moves |= E & ((c << shift) & mask)
        else:
            s = -shift
            c = O & ((P >> s) & mask)
            for _ in range(5): c |= O & ((c >> s) & mask)
            moves |= E & ((c >> s) & mask)
    return moves

def make_move_bb(P, O, move):
    flip = 0
    for shift, mask in MASKS:
        c = 0
        if shift > 0:
            temp = O & ((move << shift) & mask)
            while temp:
                c |= temp
                temp = O & ((temp << shift) & mask)
            if (c << shift) & mask & P: flip |= c
        else:
            s = -shift
            temp = O & ((move >> s) & mask)
            while temp:
                c |= temp
                temp = O & ((temp >> s) & mask)
            if (c >> s) & mask & P: flip |= c
    return P ^ move ^ flip, O ^ flip

def get_frontier_bb(P, O):
    E = ~(P | O) & 0xFFFFFFFFFFFFFFFF
    N = ((E << 1) & 0xFEFEFEFEFEFEFEFE) | ((E >> 1) & 0x7F7F7F7F7F7F7F7F) | \
        (E << 8) | (E >> 8) | ((E << 7) & 0x7F7F7F7F7F7F7F7F) | \
        ((E >> 7) & 0xFEFEFEFEFEFEFEFE) | ((E << 9) & 0xFEFEFEFEFEFEFEFE) | \
        ((E >> 9) & 0x7F7F7F7F7F7F7F7F)
    return P & N

def get_stable_bb(P, O):
    stable = P & CORNERS
    for _ in range(6):
        stable |= (P & 0x00000000000000FF) & ((stable << 1) & 0xFE | (stable >> 1) & 0x7F)
        stable |= (P & 0xFF00000000000000) & ((stable << 1) & 0xFE00000000000000 | (stable >> 1) & 0x7F00000000000000)
        stable |= (P & 0x0101010101010101) & ((stable << 8) | (stable >> 8))
        stable |= (P & 0x8080808080808080) & ((stable << 8) | (stable >> 8))
    return stable

def count_bits(n): return bin(n).count('1')

EXACT, LOWERBOUND, UPPERBOUND = 0, 1, 2

class TranspositionTable:
    def __init__(self, size_limit=1000000):
        self.table = {}
        self.size_limit = size_limit

    def store(self, P, O, depth, flag, eval_val, move):
        key = (P, O)
        if len(self.table) >= self.size_limit: self.table.clear()
        self.table[key] = (depth, flag, eval_val, move)

    def lookup(self, P, O): return self.table.get((P, O))

class HistoryTable:
    def __init__(self): self.scores = [0] * 64
    def update(self, move_bb, depth):
        idx = (move_bb & -move_bb).bit_length() - 1
        if 0 <= idx < 64: self.scores[idx] += depth * depth
    def get_score(self, move_bb):
        idx = (move_bb & -move_bb).bit_length() - 1
        return self.scores[idx] if 0 <= idx < 64 else 0

class KillerTable:
    def __init__(self): self.killers = [[0, 0] for _ in range(65)]
    def update(self, m, d):
        if d < 65 and m != self.killers[d][0]:
            self.killers[d][1] = self.killers[d][0]
            self.killers[d][0] = m
    def get_killers(self, d): return self.killers[d] if d < 65 else [0, 0]

TT = TranspositionTable()
HISTORY = HistoryTable()
KILLERS = KillerTable()

def evaluate_extreme(P, O, phase):
    p_moves_bb = get_moves_bb(P, O)
    o_moves_bb = get_moves_bb(O, P)
    p_moves = count_bits(p_moves_bb)
    o_moves = count_bits(o_moves_bb)
    
    if p_moves == 0 and o_moves == 0:
        diff = count_bits(P) - count_bits(O)
        return diff * 10000 if diff != 0 else 0

    early = max(0.0, (48 - phase) / 48.0)
    mid = 1.0 - early if phase < 56 else 0.0
    late = 1.0 - early - mid

    score = 0
    weights = EARLY_WEIGHTS if phase < 32 else MID_WEIGHTS
    for r in range(8):
        for c in range(8):
            mask = 1 << (r * 8 + c)
            if P & mask: score += weights[r][c]
            elif O & mask: score -= weights[r][c]

    score += (p_moves - o_moves) * (40 * early + 10 * mid)
    p_stable = count_bits(get_stable_bb(P, O))
    o_stable = count_bits(get_stable_bb(O, P))
    score += (p_stable - o_stable) * (200 * early + 400 * mid + 600 * late)
    p_frontier = count_bits(get_frontier_bb(P, O))
    o_frontier = count_bits(get_frontier_bb(O, P))
    score -= (p_frontier - o_frontier) * (20 * early + 5 * mid)
    score += (count_bits(P & CORNERS) - count_bits(O & CORNERS)) * 1000

    empty = ~(P | O) & CORNERS
    if empty:
        p_x = count_bits(P & X_SQUARES & (empty << 9 | empty >> 9 | empty << 7 | empty >> 7))
        o_x = count_bits(O & X_SQUARES & (empty << 9 | empty >> 9 | empty << 7 | empty >> 7))
        score -= (p_x - o_x) * 500
        p_c = count_bits(P & C_SQUARES & (empty << 1 | empty >> 1 | empty << 8 | empty >> 8))
        o_c = count_bits(O & C_SQUARES & (empty << 1 | empty >> 1 | empty << 8 | empty >> 8))
        score -= (p_c - o_c) * 200

    if (64 - phase) % 2 == 1: score += 100
    return int(score)

def solve_endgame(P, O, alpha, beta, phase, start_time, time_limit):
    if time.time() - start_time > time_limit: raise TimeoutError
    
    tt_entry = TT.lookup(P, O)
    if tt_entry and tt_entry[0] >= 64 - phase:
        flag, val = tt_entry[1], tt_entry[2]
        if flag == EXACT: return val
        if flag == LOWERBOUND: alpha = max(alpha, val)
        elif flag == UPPERBOUND: beta = min(beta, val)
        if alpha >= beta: return val

    moves_bb = get_moves_bb(P, O)
    if moves_bb == 0:
        if get_moves_bb(O, P) == 0: return count_bits(P) - count_bits(O)
        return -solve_endgame(O, P, -beta, -alpha, phase, start_time, time_limit)

    moves_list = []
    temp = moves_bb
    weights = MID_WEIGHTS
    while temp:
        m = temp & -temp
        idx = (m & -m).bit_length() - 1
        score = weights[idx // 8][idx % 8]
        moves_list.append((score, m))
        temp &= temp - 1
    moves_list.sort(key=lambda x: x[0], reverse=True)

    best_val, original_alpha = -100, alpha
    for _, m in moves_list:
        new_P, new_O = make_move_bb(P, O, m)
        val = -solve_endgame(new_O, new_P, -beta, -alpha, phase + 1, start_time, time_limit)
        best_val = max(best_val, val)
        alpha = max(alpha, val)
        if alpha >= beta: break
        
    flag = EXACT
    if best_val <= original_alpha: flag = UPPERBOUND
    elif best_val >= beta: flag = LOWERBOUND
    TT.store(P, O, 64 - phase, flag, best_val, 0)
    return best_val

def pvs(P, O, depth, alpha, beta, phase, start_time, time_limit):
    if time.time() - start_time > time_limit: raise TimeoutError

    tt_entry = TT.lookup(P, O)
    tt_move = 0
    if tt_entry and tt_entry[0] >= depth:
        flag, val, tt_move = tt_entry[1], tt_entry[2], tt_entry[3]
        if flag == EXACT: return val, tt_move
        elif flag == LOWERBOUND: alpha = max(alpha, val)
        elif flag == UPPERBOUND: beta = min(beta, val)
        if alpha >= beta: return val, tt_move

    if depth <= 0 or phase == 64: return evaluate_extreme(P, O, phase), 0

    moves_bb = get_moves_bb(P, O)
    if moves_bb == 0:
        if get_moves_bb(O, P) == 0: return evaluate_extreme(P, O, phase), 0
        val, _ = pvs(O, P, depth - 1, -beta, -alpha, phase, start_time, time_limit)
        return -val, 0

    moves_list = []
    killers = KILLERS.get_killers(depth)
    weights = EARLY_WEIGHTS if phase < 32 else MID_WEIGHTS
    temp = moves_bb
    while temp:
        m = temp & -temp
        score = 0
        if m == tt_move: score = 1000000
        elif m in killers: score = 500000
        else:
            idx = (m & -m).bit_length() - 1
            score = weights[idx // 8][idx % 8] + HISTORY.get_score(m)
        moves_list.append((score, m))
        temp &= temp - 1
    moves_list.sort(key=lambda x: x[0], reverse=True)

    best_val, best_move, original_alpha = float('-inf'), 0, alpha
    for i, (_, m) in enumerate(moves_list):
        new_P, new_O = make_move_bb(P, O, m)
        if i == 0:
            val, _ = pvs(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
            val = -val
        else:
            val, _ = pvs(new_O, new_P, depth - 1, -alpha - 1, -alpha, phase + 1, start_time, time_limit)
            val = -val
            if alpha < val < beta:
                val, _ = pvs(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
                val = -val
        if val > best_val: best_val, best_move = val, m
        alpha = max(alpha, val)
        if alpha >= beta:
            HISTORY.update(m, depth)
            KILLERS.update(m, depth)
            break

    flag = EXACT
    if best_val <= original_alpha: flag = UPPERBOUND
    elif best_val >= beta: flag = LOWERBOUND
    TT.store(P, O, depth, flag, best_val, best_move)
    return best_val, best_move

def board_to_bb(board):
    black_bb = white_bb = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == BLACK: black_bb |= (1 << (r * 8 + c))
            elif board[r][c] == WHITE: white_bb |= (1 << (r * 8 + c))
    return black_bb, white_bb

def bb_to_move(move_bb):
    if not move_bb: return None
    idx = (move_bb & -move_bb).bit_length() - 1
    return (idx // 8, idx % 8)

OPENING_BOOK = {
    (0x810000000, 0x1008000000): 0x2000000000, (0x8000000, 0x3810000000): 0x80000000000,
    (0x3010000000, 0x80808000000): 0x40000, (0x80800000000, 0x3018040000): 0x80000,
    (0x3010040000, 0x80808080000): 0x4000000, (0x80808000000, 0x3010100000): 0x80000,
    (0x3010100000, 0x80808080000): 0x4000000, (0x80800080000, 0x301c100000): 0x200000000000,
    (0x80800080000, 0x301c040000): 0x20000000, (0x201c040000, 0x81820080000): 0x400000000,
}

def get_best_move(game, player, time_limit=1.5, **kwargs):
    black_bb, white_bb = board_to_bb(game.board)
    P, O = (black_bb, white_bb) if player == BLACK else (white_bb, black_bb)
    phase = count_bits(P | O)
    if (P, O) in OPENING_BOOK: return bb_to_move(OPENING_BOOK[(P, O)])
    start_time = time.time()
    if phase >= 48:
        try:
            val = solve_endgame(P, O, -100, 100, phase, start_time, time_limit)
            temp = get_moves_bb(P, O)
            while temp:
                m = temp & -temp
                new_P, new_O = make_move_bb(P, O, m)
                if -solve_endgame(new_O, new_P, -val, -val + 1, phase + 1, start_time, time_limit) >= val: return bb_to_move(m)
                temp &= temp - 1
        except TimeoutError: pass
    best_move, depth, alpha, beta, last_val = 0, 1, float('-inf'), float('inf'), 0
    try:
        while True:
            val, m = pvs(P, O, depth, alpha, beta, phase, start_time, time_limit)
            if val <= alpha or val >= beta:
                alpha, beta = float('-inf'), float('inf')
                val, m = pvs(P, O, depth, alpha, beta, phase, start_time, time_limit)
            best_move, last_val = m, val
            alpha, beta = last_val - 60, last_val + 60
            if phase + depth >= 64: break
            depth += 1
    except TimeoutError: pass
    if best_move == 0:
        moves = get_moves_bb(P, O)
        best_move = moves & -moves
    return bb_to_move(best_move)

def get_best_move_v2(game, player, time_limit=1.5): return get_best_move(game, player, time_limit)
def get_best_move_pattern(game, player, time_limit=1.5): return get_best_move(game, player, time_limit)
