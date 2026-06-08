"""
reversi_ai.py

State-of-the-Art AI Engine for Reversi using Bitboards, Iterative Deepening, 
Principal Variation Search (PVS), History Heuristics, Transposition Tables, 
and refined Mobility/Positional/Frontier heuristics.
"""

import time
from reversi_logic import BLACK, WHITE, EMPTY

# Static positional weights (flat 1D array corresponding to 8x8 board)
WEIGHTS = [
    [100, -20, 10,  5,  5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [ 10,  -2,  5,  1,  1,  5,  -2,  10],
    [  5,  -2,  1,  0,  0,  1,  -2,   5],
    [  5,  -2,  1,  0,  0,  1,  -2,   5],
    [ 10,  -2,  5,  1,  1,  5,  -2,  10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10,  5,  5, 10, -20, 100]
]

# Precomputed masks for vectorized evaluation
WEIGHT_MASKS = {}
for r in range(8):
    for c in range(8):
        w = WEIGHTS[r][c]
        WEIGHT_MASKS[w] = WEIGHT_MASKS.get(w, 0) | (1 << (r * 8 + c))
OPTIMIZED_WEIGHTS = list(WEIGHT_MASKS.items())

# Masks for bitboard directional shifting
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
    """Generate a bitboard of all legal moves for Player (P) against Opponent (O)."""
    E = ~(P | O) & 0xFFFFFFFFFFFFFFFF
    moves = 0
    for shift, mask in MASKS:
        if shift > 0:
            c = O & ((P << shift) & mask)
            for _ in range(5):
                c |= O & ((c << shift) & mask)
            moves |= E & ((c << shift) & mask)
        else:
            s = -shift
            c = O & ((P >> s) & mask)
            for _ in range(5):
                c |= O & ((c >> s) & mask)
            moves |= E & ((c >> s) & mask)
    return moves

def make_move_bb(P, O, move):
    """Apply a move (single bit) for Player (P). Returns (new_P, new_O)."""
    flip = 0
    for shift, mask in MASKS:
        c = 0
        if shift > 0:
            temp = O & ((move << shift) & mask)
            while temp:
                c |= temp
                temp = O & ((temp << shift) & mask)
            if (c << shift) & mask & P:
                flip |= c
        else:
            s = -shift
            temp = O & ((move >> s) & mask)
            while temp:
                c |= temp
                temp = O & ((temp >> s) & mask)
            if (c >> s) & mask & P:
                flip |= c
    return P ^ move ^ flip, O ^ flip

def get_frontier_bb(P, O):
    """Get bitboard of discs adjacent to empty squares."""
    E = ~(P | O) & 0xFFFFFFFFFFFFFFFF
    N = ((E << 1) & 0xFEFEFEFEFEFEFEFE) | \
        ((E >> 1) & 0x7F7F7F7F7F7F7F7F) | \
        (E << 8) | (E >> 8) | \
        ((E << 7) & 0x7F7F7F7F7F7F7F7F) | \
        ((E >> 7) & 0xFEFEFEFEFEFEFEFE) | \
        ((E << 9) & 0xFEFEFEFEFEFEFEFE) | \
        ((E >> 9) & 0x7F7F7F7F7F7F7F7F)
    return P & N

def count_bits(n):
    return bin(n).count('1')

def evaluate_bb(P, O, phase):
    """Heuristic evaluation function based on mobility, coins, weights, and frontier discs."""
    p_moves_bb = get_moves_bb(P, O)
    o_moves_bb = get_moves_bb(O, P)
    p_moves = count_bits(p_moves_bb)
    o_moves = count_bits(o_moves_bb)
    
    # End game exact score: maximizing coin difference
    if phase == 64 or (p_moves == 0 and o_moves == 0):
        p_coins = count_bits(P)
        o_coins = count_bits(O)
        if p_coins > o_coins: return 100000 + p_coins - o_coins
        if p_coins < o_coins: return -100000 + p_coins - o_coins
        return 0
    
    score = 0
    # Vectorized positional weights
    for w, mask in OPTIMIZED_WEIGHTS:
        score += (count_bits(P & mask) - count_bits(O & mask)) * w
        
    # Mobility score: weighted higher in early/mid game
    mobility_score = (p_moves - o_moves) * (20 if phase < 40 else 10)
    
    # Frontier score: fewer frontier discs is better
    p_frontier = count_bits(get_frontier_bb(P, O))
    o_frontier = count_bits(get_frontier_bb(O, P))
    frontier_score = (o_frontier - p_frontier) * 5
    
    return score + mobility_score + frontier_score

# Transposition Table Constants
EXACT, LOWERBOUND, UPPERBOUND = 0, 1, 2

class TranspositionTable:
    def __init__(self, size_limit=100000):
        self.table = {}
        self.size_limit = size_limit
        
    def store(self, P, O, depth, flag, eval_val, move):
        if len(self.table) > self.size_limit:
            # Simple cleanup: clear if full (could be more sophisticated)
            self.table.clear()
        self.table[(P, O)] = (depth, flag, eval_val, move)
        
    def lookup(self, P, O):
        return self.table.get((P, O), None)

class HistoryTable:
    def __init__(self):
        self.scores = [0] * 64
        
    def update(self, move_bb, depth):
        idx = (move_bb & -move_bb).bit_length() - 1
        if 0 <= idx < 64:
            self.scores[idx] += depth * depth
            
    def get_score(self, move_bb):
        idx = (move_bb & -move_bb).bit_length() - 1
        return self.scores[idx] if 0 <= idx < 64 else 0

TT = TranspositionTable()
HISTORY = HistoryTable()

def alphabeta(P, O, depth, alpha, beta, phase, start_time, time_limit):
    """PVS (Principal Variation Search) with Alpha-Beta pruning, move ordering, and TT."""
    if time.time() - start_time > time_limit:
        raise TimeoutError

    tt_entry = TT.lookup(P, O)
    tt_move = None
    if tt_entry and tt_entry[0] >= depth:
        tt_flag = tt_entry[1]
        tt_val = tt_entry[2]
        tt_move = tt_entry[3]
        if tt_flag == EXACT: return tt_val, tt_move
        elif tt_flag == LOWERBOUND: alpha = max(alpha, tt_val)
        elif tt_flag == UPPERBOUND: beta = min(beta, tt_val)
        if alpha >= beta: return tt_val, tt_move

    if depth <= 0 or phase == 64:
        return evaluate_bb(P, O, phase), None

    moves_bb = get_moves_bb(P, O)
    if moves_bb == 0:
        opp_moves_bb = get_moves_bb(O, P)
        if opp_moves_bb == 0:
            return evaluate_bb(P, O, phase), None
        val, _ = alphabeta(O, P, depth - 1, -beta, -alpha, phase, start_time, time_limit)
        return -val, None
        
    # Move ordering
    moves_list = []
    temp = moves_bb
    while temp:
        lsb = temp & -temp
        score = 0
        if lsb == tt_move:
            score = 1000000
        else:
            # Combine static positional weight and history heuristic
            idx = (lsb & -lsb).bit_length() - 1
            score = WEIGHTS[idx // 8][idx % 8] + HISTORY.get_score(lsb)
        moves_list.append((score, lsb))
        temp &= temp - 1
    moves_list.sort(reverse=True, key=lambda x: x[0])
    
    best_move = None
    best_val = float('-inf')
    original_alpha = alpha
    
    # PVS implementation
    for i, (_, move) in enumerate(moves_list):
        new_P, new_O = make_move_bb(P, O, move)
        if i == 0:
            # Full window search for the first move
            val, _ = alphabeta(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
            val = -val
        else:
            # Null window search for subsequent moves
            val, _ = alphabeta(new_O, new_P, depth - 1, -alpha - 1, -alpha, phase + 1, start_time, time_limit)
            val = -val
            if alpha < val < beta:
                # Re-search if null window search failed high
                val, _ = alphabeta(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
                val = -val
                
        if val > best_val:
            best_val = val
            best_move = move
        
        if val > alpha:
            alpha = val
            if alpha >= beta:
                HISTORY.update(move, depth)
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

def get_best_move(game, player, time_limit=1.5, **kwargs):
    black_bb, white_bb = board_to_bb(game.board)
    P, O = (black_bb, white_bb) if player == BLACK else (white_bb, black_bb)
    phase = count_bits(P | O)
    
    start_time = time.time()
    best_move = None
    depth = 1
    
    print(f"AI Thinking ({'Black' if player == BLACK else 'White'}) Phase {phase}...")
    try:
        while True:
            val, move_bb = alphabeta(P, O, depth, float('-inf'), float('inf'), phase, start_time, time_limit)
            if move_bb: best_move = move_bb
            if phase + depth >= 64: break
            depth += 1
    except TimeoutError:
        pass
        
    print(f"AI Reached Depth: {depth-1}")
    if best_move is None:
        moves_bb = get_moves_bb(P, O)
        if moves_bb: best_move = moves_bb & -moves_bb
            
    return bb_to_move(best_move)
