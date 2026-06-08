from reversi_logic import ReversiGame, BLACK, WHITE

def test_initial_state():
    game = ReversiGame()
    assert game.board[3][3] == BLACK
    assert game.board[4][4] == BLACK
    assert game.board[3][4] == WHITE
    assert game.board[4][3] == WHITE

def test_legal_moves():
    game = ReversiGame()
    moves = game.get_legal_moves(BLACK)
    expected = [(2, 4), (3, 5), (4, 2), (5, 3)]
    assert sorted(moves) == sorted(expected)

def test_make_move():
    game = ReversiGame()
    assert game.make_move(2, 4, BLACK)
    assert game.board[2][4] == BLACK
    assert game.board[3][4] == BLACK

if __name__ == "__main__":
    test_initial_state()
    test_legal_moves()
    test_make_move()
    print("Tests passed.")