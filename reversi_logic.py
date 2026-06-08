EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]

class ReversiGame:
    def __init__(self):
        self.board = [[EMPTY] * 8 for _ in range(8)]
        # Updated starting position
        self.board[3][3] = BLACK
        self.board[4][4] = BLACK
        self.board[3][4] = WHITE
        self.board[4][3] = WHITE
        self.current_player = BLACK

    def is_on_board(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def get_legal_moves(self, player):
        return [(r, c) for r in range(8) for c in range(8) if self.is_legal_move(r, c, player)]

    def is_legal_move(self, r, c, player):
        if self.board[r][c] != EMPTY:
            return False
        
        opp = WHITE if player == BLACK else BLACK
        
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if self.is_on_board(nr, nc) and self.board[nr][nc] == opp:
                nr += dr
                nc += dc
                while self.is_on_board(nr, nc):
                    if self.board[nr][nc] == player:
                        return True
                    if self.board[nr][nc] == EMPTY:
                        break
                    nr += dr
                    nc += dc
        return False

    def make_move(self, r, c, player):
        if not self.is_legal_move(r, c, player):
            return False
        
        self.board[r][c] = player
        opp = WHITE if player == BLACK else BLACK
        
        for dr, dc in DIRECTIONS:
            flips = []
            nr, nc = r + dr, c + dc
            while self.is_on_board(nr, nc) and self.board[nr][nc] == opp:
                flips.append((nr, nc))
                nr += dr
                nc += dc
            
            if self.is_on_board(nr, nc) and self.board[nr][nc] == player:
                for fr, fc in flips:
                    self.board[fr][fc] = player
                    
        return True

    def get_score(self):
        return {
            BLACK: sum(row.count(BLACK) for row in self.board),
            WHITE: sum(row.count(WHITE) for row in self.board)
        }

    def is_game_over(self):
        return not self.get_legal_moves(BLACK) and not self.get_legal_moves(WHITE)

    def switch_player(self):
        self.current_player = WHITE if self.current_player == BLACK else BLACK
