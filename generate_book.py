
import sys
from reversi_ai import board_to_bb, make_move_bb, get_moves_bb
from reversi_logic import BLACK, WHITE, EMPTY

def move_to_bb(move_str):
    col = ord(move_str[0]) - ord('a')
    row = int(move_str[1]) - 1
    return 1 << (row * 8 + col)

def simulate_sequence(sequence_str):
    moves = sequence_str.split()
    # Initial board state
    # B: (3,4), (4,3) -> 1<<28, 1<<35
    # W: (3,3), (4,4) -> 1<<27, 1<<36
    P = (1 << 28) | (1 << 35) # BLACK
    O = (1 << 27) | (1 << 36) # WHITE
    
    player = BLACK
    book_entries = []
    
    current_P, current_O = P, O
    
    for move_str in moves:
        move_bb = move_to_bb(move_str)
        # Store entry: (Current Player Bitboard, Current Opponent Bitboard) -> Move
        # Note: OPENING_BOOK stores (P, O) where P is the player about to move.
        if player == BLACK:
            book_entries.append(((current_P, current_O), move_bb))
            current_P, current_O = make_move_bb(current_P, current_O, move_bb)
        else:
            book_entries.append(((current_O, current_P), move_bb))
            current_O, current_P = make_move_bb(current_O, current_P, move_bb)
        
        player = WHITE if player == BLACK else BLACK
        
    return book_entries

sequences = {
    "Tiger": "f5 d6 c3 d3 c4",
    "Rabbit": "f5 d6 c3 d3 f4",
    "Cow": "f5 d6 e3 d3 c4",
    "Parallel": "f5 d6 c5",
    "Heath": "f5 d6 e3 d3 c4 f6",
    "Rose": "f5 d6 c3 d3 c4 f4 c5 b4 d7 e6 f6 g5 h6"
}

all_entries = {}
for name, seq in sequences.items():
    entries = simulate_sequence(seq)
    for key, val in entries:
        all_entries[key] = val

print("OPENING_BOOK = {")
for (p, o), m in all_entries.items():
    print(f"    ({hex(p)}, {hex(o)}): {hex(m)},")
print("}")
