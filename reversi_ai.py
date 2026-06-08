"""
reversi_ai.py

State-of-the-Art AI Engine for Reversi using Bitboards, Iterative Deepening, 
Alpha-Beta pruning, Transposition Tables, and Mobility/Positional Heuristics.
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

# Map single bit values to weight for O(1) positional evaluation
FLAT_WEIGHTS_DICT = {}
for r in range(8):
    for c in range(8):
        FLAT_WEIGHTS_DICT[1 << (r * 8 + c)] = WEIGHTS[r][c]

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

def count_bits(n):
    return bin(n).count('1')

def evaluate_bb(P, O, phase):
    """Heuristic evaluation function based on mobility, coins, and static weights."""
    p_moves = count_bits(get_moves_bb(P, O))
    o_moves = count_bits(get_moves_bb(O, P))
    
    # End game exact score: maximizing coin difference
    if phase == 64 or (p_moves == 0 and o_moves == 0):
        p_coins = count_bits(P)
        o_coins = count_bits(O)
        if p_coins > o_coins: return 10000 + p_coins - o_coins
        if p_coins < o_coins: return -10000 + p_coins - o_coins
        return 0
    
    # Late game: prioritize coin parity and pure mobility
    if phase > 50:
        p_coins = count_bits(P)
        o_coins = count_bits(O)
        return (p_coins - o_coins) * 10 + (p_moves - o_moves) * 5
    
    # Mid game: positional weights + mobility
    score = 0
    p_temp = P
    while p_temp:
        lsb = p_temp & -p_temp
        score += FLAT_WEIGHTS_DICT.get(lsb, 0)
        p_temp &= p_temp - 1
        
    o_temp = O
    while o_temp:
        lsb = o_temp & -o_temp
        score -= FLAT_WEIGHTS_DICT.get(lsb, 0)
        o_temp &= o_temp - 1
        
    mobility_score = (p_moves - o_moves) * 15
    return score + mobility_score

# Transposition Table Constants
EXACT, LOWERBOUND, UPPERBOUND = 0, 1, 2

class TranspositionTable:
    def __init__(self):
        self.table = {}
        
    def store(self, P, O, depth, flag, eval_val, move):
        self.table[(P, O)] = (depth, flag, eval_val, move)
        
    def lookup(self, P, O):
        return self.table.get((P, O), None)

TT = TranspositionTable()

def alphabeta(P, O, depth, alpha, beta, phase, start_time, time_limit):
    """Minimax (Negamax) with Alpha-Beta pruning, move ordering, and transposition tables."""
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
        
        # Pass turn: the opponent gets to move
        val, _ = alphabeta(O, P, depth - 1, -beta, -alpha, phase, start_time, time_limit)
        return -val, None
        
    best_move = None
    best_val = float('-inf')
    original_alpha = alpha
    
    # Move ordering: TT move first, then positional score
    moves_list = []
    temp = moves_bb
    while temp:
        lsb = temp & -temp
        score = FLAT_WEIGHTS_DICT.get(lsb, 0)
        if lsb == tt_move:
            score += 100000 # Try TT move first
        moves_list.append((score, lsb))
        temp &= temp - 1
        
    moves_list.sort(reverse=True, key=lambda x: x[0])
    
    for _, move in moves_list:
        new_P, new_O = make_move_bb(P, O, move)
        try:
            val, _ = alphabeta(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
            val = -val
        except TimeoutError:
            raise
            
        if val > best_val:
            best_val = val
            best_move = move
        alpha = max(alpha, val)
        if alpha >= beta:
            break
            
    if best_val <= original_alpha:
        flag = UPPERBOUND
    elif best_val >= beta:
        flag = LOWERBOUND
    else:
        flag = EXACT
        
    TT.store(P, O, depth, flag, best_val, best_move)
    return best_val, best_move

def board_to_bb(board):
    black_bb = 0
    white_bb = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == BLACK:
                black_bb |= (1 << (r * 8 + c))
            elif board[r][c] == WHITE:
                white_bb |= (1 << (r * 8 + c))
    return black_bb, white_bb

def bb_to_move(move_bb):
    if not move_bb:
        return None
    idx = (move_bb & -move_bb).bit_length() - 1
    return (idx // 8, idx % 8)

def get_best_move(game, player, time_limit=1.5, **kwargs):
    global TT
    TT = TranspositionTable() # Clear TT for fresh search to avoid unbounded memory growth
    
    black_bb, white_bb = board_to_bb(game.board)
    if player == BLACK:
        P, O = black_bb, white_bb
    else:
        P, O = white_bb, black_bb
        
    phase = count_bits(P | O)
    print(f"AI Thinking (Player {'Black' if player == BLACK else 'White'}) Phase {phase}...")
    
    start_time = time.time()
    best_move = None
    depth = 1
    
    try:
        while True:
            val, move_bb = alphabeta(P, O, depth, float('-inf'), float('inf'), phase, start_time, time_limit)
            if move_bb is not None:
                best_move = move_bb
            # End game solver optimization
            if phase + depth >= 64:
                break
            depth += 1
    except TimeoutError:
        pass
        
    print(f"AI Reached Depth: {depth-1}")
    
    # Fallback to pure move generation if no move returned (e.g., instant timeout)
    if best_move is None:
        moves_bb = get_moves_bb(P, O)
        if moves_bb:
            best_move = moves_bb & -moves_bb
            
    move = bb_to_move(best_move)
    print(f"AI Selected Move: {move}")
    return move
