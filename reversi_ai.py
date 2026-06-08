"""
reversi_ai.py

State-of-the-Art AI Engine for Reversi using Bitboards, Iterative Deepening, 
Principal Variation Search (PVS), History Heuristics, Transposition Tables, 
and refined Mobility/Positional/Frontier heuristics.
"""

import time
from reversi_logic import BLACK, WHITE, EMPTY

# --- Egaroucid-Inspired Phase-Based Weights ---
# Early game positional weights (Focus on center, avoid edges next to corners)
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

# Mid/Late game positional weights (Coins and edges become more valuable)
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

WEIGHTS = EARLY_WEIGHTS # Alias for backwards compatibility in move ordering

def precompute_weight_masks(weights):
    masks = {}
    for r in range(8):
        for c in range(8):
            w = weights[r][c]
            masks[w] = masks.get(w, 0) | (1 << (r * 8 + c))
    return list(masks.items())

OPT_EARLY_WEIGHTS = precompute_weight_masks(EARLY_WEIGHTS)
OPT_MID_WEIGHTS = precompute_weight_masks(MID_WEIGHTS)

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
    """Egaroucid-inspired Phase-Based heuristic evaluation function."""
    p_moves_bb = get_moves_bb(P, O)
    o_moves_bb = get_moves_bb(O, P)
    p_moves = count_bits(p_moves_bb)
    o_moves = count_bits(o_moves_bb)
    
    # End game exact score: maximizing coin difference
    if phase >= 60 or (p_moves == 0 and o_moves == 0):
        p_coins = count_bits(P)
        o_coins = count_bits(O)
        if p_coins > o_coins: return 100000 + p_coins - o_coins
        if p_coins < o_coins: return -100000 + p_coins - o_coins
        return 0
    
    # Egaroucid inspired phase-based interpolation (phases ~4 to 64)
    early_ratio = max(0.0, (40 - phase) / 40.0)
    mid_ratio = 1.0 - early_ratio
    
    early_score = 0
    for w, mask in OPT_EARLY_WEIGHTS:
        early_score += (count_bits(P & mask) - count_bits(O & mask)) * w
        
    mid_score = 0
    for w, mask in OPT_MID_WEIGHTS:
        mid_score += (count_bits(P & mask) - count_bits(O & mask)) * w
        
    score = early_score * early_ratio + mid_score * mid_ratio
        
    # Mobility score: weighted higher in early/mid game
    mobility_weight = 20 * early_ratio + 5 * mid_ratio
    mobility_score = (p_moves - o_moves) * mobility_weight
    
    # Frontier score: fewer frontier discs is better
    p_frontier = count_bits(get_frontier_bb(P, O))
    o_frontier = count_bits(get_frontier_bb(O, P))
    frontier_weight = 10 * early_ratio + 2 * mid_ratio
    frontier_score = (o_frontier - p_frontier) * frontier_weight
    
    return int(score + mobility_score + frontier_score)

# Transposition Table Constants
EXACT, LOWERBOUND, UPPERBOUND = 0, 1, 2

class TranspositionTable:
    def __init__(self, size_limit=200000):
        self.table = {}
        self.size_limit = size_limit

    def store(self, P, O, depth, flag, eval_val, move):
        if len(self.table) > self.size_limit:
            # Better cleanup: Remove 25% of the table (randomly or oldest)
            # For simplicity, we'll just clear it for now but with a larger limit
            self.table.clear()
        self.table[(P, O)] = (depth, flag, eval_val, move)

    def lookup(self, P, O):
        return self.table.get((P, O), None)

def solve_endgame(P, O, alpha, beta, phase, start_time, time_limit):
    """
    Specialized solver for the final phase of the game.
    Aims for perfect play by maximizing coin difference.
    """
    if time.time() - start_time > time_limit:
        raise TimeoutError

    moves_bb = get_moves_bb(P, O)
    if moves_bb == 0:
        opp_moves_bb = get_moves_bb(O, P)
        if opp_moves_bb == 0:
            p_coins = count_bits(P)
            o_coins = count_bits(O)
            return p_coins - o_coins
        return -solve_endgame(O, P, -beta, -alpha, phase, start_time, time_limit)

    # Use simple move ordering for endgame
    moves_list = []
    temp = moves_bb
    while temp:
        lsb = temp & -temp
        idx = (lsb & -lsb).bit_length() - 1
        score = EARLY_WEIGHTS[idx // 8][idx % 8] # Positional still helps ordering
        moves_list.append((score, lsb))
        temp &= temp - 1
    moves_list.sort(reverse=True, key=lambda x: x[0])

    best_val = float('-inf')
    for _, move in moves_list:
        new_P, new_O = make_move_bb(P, O, move)
        val = -solve_endgame(new_O, new_P, -beta, -alpha, phase + 1, start_time, time_limit)
        best_val = max(best_val, val)
        alpha = max(alpha, val)
        if alpha >= beta:
            break
    return best_val

def alphabeta(P, O, depth, alpha, beta, phase, start_time, time_limit):

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

TT_PATTERN = TranspositionTable()
HISTORY_PATTERN = HistoryTable()

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

# Egaroucid-inspired Opening Book (Stores exact bitboard matches for opening sequences)
OPENING_BOOK = {
    (0x810000000, 0x1008000000): 0x2000000000,      # f5
    (0x8000000, 0x3810000000): 0x80000000000,      # d6
    (0x3010000000, 0x80808000000): 0x40000,        # c3
    (0x80800000000, 0x3018040000): 0x80000,        # d3
    (0x3010040000, 0x80808080000): 0x4000000,      # c4
    (0x80808000000, 0x3010100000): 0x80000,        # d3
    (0x3010100000, 0x80808080000): 0x4000000,      # c4
    (0x80800080000, 0x301c100000): 0x200000000000,  # f4
    (0x80800080000, 0x301c040000): 0x20000000,      # e3
    (0x201c040000, 0x81820080000): 0x400000000,     # c5
    (0x80020080000, 0x3c1c040000): 0x2000000,       # f6
    (0x3800040000, 0x8043e080000): 0x8000000000000, # f6
    (0x43e080000, 0x8083800040000): 0x100000000000, # c5
    (0x8082000040000, 0x101c3e080000): 0x200000000000, # b4
    (0xc36080000, 0x8383008040000): 0x4000000000,   # d7
    (0x8380008040000, 0x7c36080000): 0x800000000000, # g5
}

# --- Pattern Extraction Heuristics (Egaroucid-Inspired) ---
CORNERS = 0x8100000000000081
X_SQUARES = 0x0042000000004200
C_SQUARES = 0x4281000000008142
A_SQUARES = 0x0024000024000000 # Actually 0x24 on edges
# Correcting A and B squares masks
A_SQUARES = 0x2400810000810024 & ~CORNERS # Simplified
# Let's use more precise masks for edges
EDGE_MASK = 0xFF818181818181FF
INNER_MASK = 0x007E7E7E7E7E7E00

def get_stable_bb(P, O):
    """Iteratively compute stable discs (discs that can never be flipped)."""
    stable = P & CORNERS
    
    # Edges stability
    for _ in range(6):
        # Top edge
        stable |= (P & 0x00000000000000FF) & ((stable << 1) & 0xFE | (stable >> 1) & 0x7F)
        # Bottom edge
        stable |= (P & 0xFF00000000000000) & ((stable << 1) & 0xFE00000000000000 | (stable >> 1) & 0x7F00000000000000)
        # Left edge
        stable |= (P & 0x0101010101010101) & ((stable << 8) | (stable >> 8))
        # Right edge
        stable |= (P & 0x8080808080808080) & ((stable << 8) | (stable >> 8))
    
    # Full stability is harder, but edge stability is 90% of it.
    return stable

def evaluate_bb_pattern_v2(P, O, phase):
    """
    Advanced Pattern-Based Evaluation (V2).
    Focuses on Stability, Mobility, and Structural patterns.
    """
    p_moves_bb = get_moves_bb(P, O)
    o_moves_bb = get_moves_bb(O, P)
    p_moves = count_bits(p_moves_bb)
    o_moves = count_bits(o_moves_bb)
    
    # Game over or near end
    if phase >= 60 or (p_moves == 0 and o_moves == 0):
        p_coins = count_bits(P)
        o_coins = count_bits(O)
        if p_coins > o_coins: return 100000 + p_coins - o_coins
        if p_coins < o_coins: return -100000 + p_coins - o_coins
        return 0

    score = 0
    
    # 1. Stability (The most important pattern)
    p_stable = get_stable_bb(P, O)
    o_stable = get_stable_bb(O, P)
    score += (count_bits(p_stable) - count_bits(o_stable)) * 300
    
    # 2. Corners (High value even if not fully stable yet)
    p_corners = count_bits(P & CORNERS)
    o_corners = count_bits(O & CORNERS)
    score += (p_corners - o_corners) * 700
    
    # 3. Mobility (Crucial in mid-game)
    # Mobility weight decreases as game progresses
    mobility_weight = max(10, 60 - phase)
    score += (p_moves - o_moves) * mobility_weight
    
    # 4. Frontier (Lower is better)
    p_frontier = count_bits(get_frontier_bb(P, O))
    o_frontier = count_bits(get_frontier_bb(O, P))
    frontier_weight = 20 if phase < 40 else 5
    score += (o_frontier - p_frontier) * frontier_weight
    
    # 5. Dangerous Squares (X and C)
    empty_corners = ~(P | O) & CORNERS
    if empty_corners:
        # Penalize X-squares if corner is empty
        p_x = count_bits(P & X_SQUARES & (empty_corners << 9 | empty_corners >> 9 | empty_corners << 7 | empty_corners >> 7))
        o_x = count_bits(O & X_SQUARES & (empty_corners << 9 | empty_corners >> 9 | empty_corners << 7 | empty_corners >> 7))
        score -= (p_x - o_x) * 400
        
        # Penalize C-squares if corner is empty
        p_c = count_bits(P & C_SQUARES & (empty_corners << 1 | empty_corners >> 1 | empty_corners << 8 | empty_corners >> 8))
        o_c = count_bits(O & C_SQUARES & (empty_corners << 1 | empty_corners >> 1 | empty_corners << 8 | empty_corners >> 8))
        score -= (p_c - o_c) * 150

    # 6. Parity (Last move advantage)
    # If it's my turn and there are an even number of squares left, I move last.
    squares_left = 64 - phase
    if squares_left % 2 == 0:
        score += 50
    else:
        score -= 50

    return score

TT_V2 = TranspositionTable()
HISTORY_V2 = HistoryTable()

def alphabeta_v2(P, O, depth, alpha, beta, phase, start_time, time_limit):
    """PVS with Advanced Pattern-based evaluation (V2)."""
    if time.time() - start_time > time_limit:
        raise TimeoutError

    tt_entry = TT_V2.lookup(P, O)
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
        return evaluate_bb_pattern_v2(P, O, phase), None

    moves_bb = get_moves_bb(P, O)
    if moves_bb == 0:
        opp_moves_bb = get_moves_bb(O, P)
        if opp_moves_bb == 0:
            return evaluate_bb_pattern_v2(P, O, phase), None
        val, _ = alphabeta_v2(O, P, depth - 1, -beta, -alpha, phase, start_time, time_limit)
        return -val, None
        
    moves_list = []
    temp = moves_bb
    while temp:
        lsb = temp & -temp
        idx = (lsb & -lsb).bit_length() - 1
        # Use phase-aware weights for move ordering
        current_weights = EARLY_WEIGHTS if phase < 32 else MID_WEIGHTS
        score = current_weights[idx // 8][idx % 8] + HISTORY_V2.get_score(lsb)
        if lsb == tt_move: score = 1000000
        moves_list.append((score, lsb))
        temp &= temp - 1
    moves_list.sort(reverse=True, key=lambda x: x[0])
    
    best_move = None
    best_val = float('-inf')
    original_alpha = alpha
    
    for i, (_, move) in enumerate(moves_list):
        new_P, new_O = make_move_bb(P, O, move)
        if i == 0:
            val, _ = alphabeta_v2(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
            val = -val
        else:
            val, _ = alphabeta_v2(new_O, new_P, depth - 1, -alpha - 1, -alpha, phase + 1, start_time, time_limit)
            val = -val
            if alpha < val < beta:
                val, _ = alphabeta_v2(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
                val = -val
        if val > best_val:
            best_val = val
            best_move = move
        if val > alpha:
            alpha = val
            if alpha >= beta:
                HISTORY_V2.update(move, depth)
                break
            
    flag = EXACT
    if best_val <= original_alpha: flag = UPPERBOUND
    elif best_val >= beta: flag = LOWERBOUND

    TT_V2.store(P, O, depth, flag, best_val, best_move)
    return best_val, best_move

def get_best_move_v2(game, player, time_limit=1.5):
    """Search entry point for the V2 Pattern-based AI."""
    black_bb, white_bb = board_to_bb(game.board)
    P, O = (black_bb, white_bb) if player == BLACK else (white_bb, black_bb)
    phase = count_bits(P | O)
    start_time = time.time()
    
    # Check for Endgame Solve (Perfect Play)
    if phase >= 48:
        print(f"AI V2 Solving Endgame ({64 - phase} moves left)...")
        try:
            # We use a large window for exact score
            score = solve_endgame(P, O, -64, 64, phase, start_time, time_limit)
            # Find the move that leads to this score
            moves_bb = get_moves_bb(P, O)
            temp = moves_bb
            best_move = None
            while temp:
                move = temp & -temp
                new_P, new_O = make_move_bb(P, O, move)
                # Null window search around the expected score for efficiency
                val = -solve_endgame(new_O, new_P, -score, -score + 1, phase + 1, start_time, time_limit)
                if val >= score:
                    best_move = move
                    break
                temp &= temp - 1
            if best_move:
                print(f"AI V2 Found Perfect Move! Expected Score: {score}")
                return bb_to_move(best_move)
        except TimeoutError:
            print("Endgame solver timed out, falling back to heuristic.")

    best_move = None
    depth = 1
    alpha, beta = float('-inf'), float('inf')
    last_val = 0
    
    print(f"AI V2 Thinking ({'Black' if player == BLACK else 'White'}) Phase {phase}...")
    try:
        while True:
            val, move_bb = alphabeta_v2(P, O, depth, alpha, beta, phase, start_time, time_limit)
            if val <= alpha or val >= beta:
                alpha, beta = float('-inf'), float('inf')
                val, move_bb = alphabeta_v2(P, O, depth, alpha, beta, phase, start_time, time_limit)
            if move_bb:
                best_move = move_bb
                last_val = val
            alpha, beta = last_val - 50, last_val + 50
            if phase + depth >= 64: break
            depth += 1
    except TimeoutError: pass
    
    print(f"AI V2 Reached Depth: {depth-1}")
    if best_move is None:
        moves_bb = get_moves_bb(P, O)
        if moves_bb: best_move = moves_bb & -moves_bb
    return bb_to_move(best_move)

def evaluate_bb_pattern(P, O, phase):
    """Heuristic evaluation focused on structural patterns and stability."""
    p_moves_bb = get_moves_bb(P, O)
    o_moves_bb = get_moves_bb(O, P)
    p_moves = count_bits(p_moves_bb)
    o_moves = count_bits(o_moves_bb)
    
    if phase >= 60 or (p_moves == 0 and o_moves == 0):
        p_coins = count_bits(P)
        o_coins = count_bits(O)
        return 100000 + (p_coins - o_coins) if p_coins > o_coins else -100000 + (p_coins - o_coins)
    
    score = 0
    
    # Corner ownership (Very high value)
    p_corners = count_bits(P & CORNERS)
    o_corners = count_bits(O & CORNERS)
    score += (p_corners - o_corners) * 500
    
    # X-Squares and C-Squares (Danger zones)
    # Penalize only if adjacent corner is empty
    empty_corners = ~(P | O) & CORNERS
    if empty_corners:
        # Penalize player for being on X/C squares near empty corners
        score -= count_bits(P & X_SQUARES & (empty_corners << 9 | empty_corners >> 9 | empty_corners << 7 | empty_corners >> 7)) * 100
        score -= count_bits(P & C_SQUARES & (empty_corners << 1 | empty_corners >> 1 | empty_corners << 8 | empty_corners >> 8)) * 50
        # Reward if opponent is there
        score += count_bits(O & X_SQUARES & (empty_corners << 9 | empty_corners >> 9 | empty_corners << 7 | empty_corners >> 7)) * 100
        score += count_bits(O & C_SQUARES & (empty_corners << 1 | empty_corners >> 1 | empty_corners << 8 | empty_corners >> 8)) * 50

    # Mobility and Frontier
    mobility_score = (p_moves - o_moves) * 30
    p_frontier = count_bits(get_frontier_bb(P, O))
    o_frontier = count_bits(get_frontier_bb(O, P))
    frontier_score = (o_frontier - p_frontier) * 15
    
    return score + mobility_score + frontier_score

def alphabeta_pattern(P, O, depth, alpha, beta, phase, start_time, time_limit):
    """PVS with Pattern-based evaluation."""
    if time.time() - start_time > time_limit:
        raise TimeoutError

    tt_entry = TT_PATTERN.lookup(P, O)
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
        return evaluate_bb_pattern(P, O, phase), None

    moves_bb = get_moves_bb(P, O)
    if moves_bb == 0:
        opp_moves_bb = get_moves_bb(O, P)
        if opp_moves_bb == 0:
            return evaluate_bb_pattern(P, O, phase), None
        val, _ = alphabeta_pattern(O, P, depth - 1, -beta, -alpha, phase, start_time, time_limit)
        return -val, None
        
    moves_list = []
    temp = moves_bb
    while temp:
        lsb = temp & -temp
        idx = (lsb & -lsb).bit_length() - 1
        score = WEIGHTS[idx // 8][idx % 8] + HISTORY_PATTERN.get_score(lsb)
        if lsb == tt_move: score = 1000000
        moves_list.append((score, lsb))
        temp &= temp - 1
    moves_list.sort(reverse=True, key=lambda x: x[0])
    
    best_move = None
    best_val = float('-inf')
    original_alpha = alpha
    
    for i, (_, move) in enumerate(moves_list):
        new_P, new_O = make_move_bb(P, O, move)
        if i == 0:
            val, _ = alphabeta_pattern(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
            val = -val
        else:
            val, _ = alphabeta_pattern(new_O, new_P, depth - 1, -alpha - 1, -alpha, phase + 1, start_time, time_limit)
            val = -val
            if alpha < val < beta:
                val, _ = alphabeta_pattern(new_O, new_P, depth - 1, -beta, -alpha, phase + 1, start_time, time_limit)
                val = -val
        if val > best_val:
            best_val = val
            best_move = move
        if val > alpha:
            alpha = val
            if alpha >= beta:
                HISTORY_PATTERN.update(move, depth)
                break
            
    flag = EXACT
    if best_val <= original_alpha: flag = UPPERBOUND
    elif best_val >= beta: flag = LOWERBOUND

    TT_PATTERN.store(P, O, depth, flag, best_val, best_move)
    return best_val, best_move

def get_best_move_pattern(game, player, time_limit=1.5):
    black_bb, white_bb = board_to_bb(game.board)
    P, O = (black_bb, white_bb) if player == BLACK else (white_bb, black_bb)
    phase = count_bits(P | O)
    start_time = time.time()
    best_move = None
    depth = 1
    alpha, beta = float('-inf'), float('inf')
    last_val = 0
    try:
        while True:
            val, move_bb = alphabeta_pattern(P, O, depth, alpha, beta, phase, start_time, time_limit)
            if val <= alpha or val >= beta:
                alpha, beta = float('-inf'), float('inf')
                val, move_bb = alphabeta_pattern(P, O, depth, alpha, beta, phase, start_time, time_limit)
            if move_bb:
                best_move = move_bb
                last_val = val
            alpha, beta = last_val - 50, last_val + 50
            if phase + depth >= 64: break
            depth += 1
    except TimeoutError: pass
    if best_move is None:
        moves_bb = get_moves_bb(P, O)
        if moves_bb: best_move = moves_bb & -moves_bb
    return bb_to_move(best_move)

def get_best_move(game, player, time_limit=1.5, **kwargs):
    black_bb, white_bb = board_to_bb(game.board)
    P, O = (black_bb, white_bb) if player == BLACK else (white_bb, black_bb)
    phase = count_bits(P | O)
    
    # Check Opening Book for instant move
    if (P, O) in OPENING_BOOK:
        print("AI Playing from Opening Book...")
        return bb_to_move(OPENING_BOOK[(P, O)])
    
    start_time = time.time()

    # Check for Endgame Solve (Perfect Play)
    if phase >= 48:
        print(f"AI Solving Endgame ({64 - phase} moves left)...")
        try:
            score = solve_endgame(P, O, -64, 64, phase, start_time, time_limit)
            moves_bb = get_moves_bb(P, O)
            temp = moves_bb
            best_move = None
            while temp:
                move = temp & -temp
                new_P, new_O = make_move_bb(P, O, move)
                val = -solve_endgame(new_O, new_P, -score, -score + 1, phase + 1, start_time, time_limit)
                if val >= score:
                    best_move = move
                    break
                temp &= temp - 1
            if best_move:
                print(f"AI Found Perfect Move! Expected Score: {score}")
                return bb_to_move(best_move)
        except TimeoutError:
            print("Endgame solver timed out, falling back to heuristic.")

    best_move = None
    depth = 1
    
    # Egaroucid-inspired Aspiration Windows
    alpha = float('-inf')
    beta = float('inf')
    last_val = 0
    
    print(f"AI Thinking ({'Black' if player == BLACK else 'White'}) Phase {phase}...")
    try:
        while True:
            val, move_bb = alphabeta(P, O, depth, alpha, beta, phase, start_time, time_limit)
            
            if val <= alpha or val >= beta:
                alpha = float('-inf')
                beta = float('inf')
                val, move_bb = alphabeta(P, O, depth, alpha, beta, phase, start_time, time_limit)
                
            if move_bb:
                best_move = move_bb
                last_val = val
                
            alpha = last_val - 50
            beta = last_val + 50
                
            if phase + depth >= 64: break
            depth += 1
    except TimeoutError:
        pass
        
    print(f"AI Reached Depth: {depth-1}")
    if best_move is None:
        moves_bb = get_moves_bb(P, O)
        if moves_bb: best_move = moves_bb & -moves_bb
            
    return bb_to_move(best_move)
