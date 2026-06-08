"""
reversi_gui.py

Tkinter-based GUI for the Reversi game.
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
from reversi_logic import ReversiGame, BLACK, WHITE, EMPTY
from reversi_ai import get_best_move, get_best_move_v2, get_best_move_pattern

CELL_SIZE = 60
BOARD_MARGIN = 20
CANVAS_SIZE = CELL_SIZE * 8 + 2 * BOARD_MARGIN

class ReversiGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Reversi Master AI")
        
        self.game = ReversiGame()
        self.player_color = BLACK
        self.ai_color = WHITE
        self.is_ai_thinking = False
        
        # AI selection: "Standard", "Pattern V1", "Pattern V2 (Advanced)"
        self.ai_mode = tk.StringVar(value="Standard")
        # Time selection: 1.0, 3.0, 5.0, 10.0
        self.thinking_time = tk.DoubleVar(value=1.5)
        
        self.setup_ui()
        self.ask_player_color()
        self.draw_board()

    def setup_ui(self):
        # Create menu for AI selection and Search settings
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        self.ai_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="AI Engine", menu=self.ai_menu)
        self.ai_menu.add_radiobutton(label="Standard (Phase-Based)", variable=self.ai_mode, value="Standard")
        self.ai_menu.add_radiobutton(label="Pattern V1 (Basic)", variable=self.ai_mode, value="Pattern V1")
        self.ai_menu.add_radiobutton(label="Pattern V2 (Advanced)", variable=self.ai_mode, value="Pattern V2")

        self.search_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Search Time", menu=self.search_menu)
        self.search_menu.add_radiobutton(label="Quick (0.5s)", variable=self.thinking_time, value=0.5)
        self.search_menu.add_radiobutton(label="Normal (1.5s)", variable=self.thinking_time, value=1.5)
        self.search_menu.add_radiobutton(label="Deep (5.0s)", variable=self.thinking_time, value=5.0)
        self.search_menu.add_radiobutton(label="Ultra (15.0s)", variable=self.thinking_time, value=15.0)

        self.canvas = tk.Canvas(self.root, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="#2e7d32")
        self.canvas.pack(pady=10)
        self.canvas.bind("<Button-1>", self.handle_click)
        
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, padx=20)
        
        self.score_label = tk.Label(self.status_frame, text="Black: 2 | White: 2", font=("Helvetica", 12, "bold"))
        self.score_label.pack(side=tk.LEFT)
        
        self.turn_label = tk.Label(self.status_frame, text="Turn: Black", font=("Helvetica", 12))
        self.turn_label.pack(side=tk.RIGHT)
        
        self.footer_label = tk.Label(self.root, text="shayan matin sucks", font=("Helvetica", 16, "bold"), fg="red")
        self.footer_label.pack(side=tk.BOTTOM, pady=10)

    def ask_player_color(self):
        response = messagebox.askyesno("Color Selection", "Do you want to play as Black? (Black moves first)")
        if response:
            self.player_color = BLACK
            self.ai_color = WHITE
        else:
            self.player_color = WHITE
            self.ai_color = BLACK
            self.root.after(500, self.trigger_ai_turn)

    def draw_board(self):
        self.canvas.delete("all")
        
        # Draw grid
        for i in range(9):
            # Vertical lines
            x = BOARD_MARGIN + i * CELL_SIZE
            self.canvas.create_line(x, BOARD_MARGIN, x, CANVAS_SIZE - BOARD_MARGIN, fill="#1b5e20")
            # Horizontal lines
            y = BOARD_MARGIN + i * CELL_SIZE
            self.canvas.create_line(BOARD_MARGIN, y, CANVAS_SIZE - BOARD_MARGIN, y, fill="#1b5e20")
            
        # Draw pieces
        for r in range(8):
            for c in range(8):
                piece = self.game.board[r][c]
                if piece != EMPTY:
                    x0 = BOARD_MARGIN + c * CELL_SIZE + 4
                    y0 = BOARD_MARGIN + r * CELL_SIZE + 4
                    x1 = x0 + CELL_SIZE - 8
                    y1 = y0 + CELL_SIZE - 8
                    color = "black" if piece == BLACK else "white"
                    outline = "gray" if piece == WHITE else "white"
                    self.canvas.create_oval(x0, y0, x1, y1, fill=color, outline=outline, width=2)

        # Highlight legal moves for the player
        if self.game.current_player == self.player_color and not self.is_ai_thinking:
            legal_moves = self.game.get_legal_moves(self.player_color)
            for r, c in legal_moves:
                x0 = BOARD_MARGIN + c * CELL_SIZE + CELL_SIZE // 4
                y0 = BOARD_MARGIN + r * CELL_SIZE + CELL_SIZE // 4
                x1 = x0 + CELL_SIZE // 2
                y1 = y0 + CELL_SIZE // 2
                self.canvas.create_oval(x0, y0, x1, y1, outline="#a5d6a7", width=2, dash=(5, 5))

        self.update_status()

    def update_status(self):
        scores = self.game.get_score()
        self.score_label.config(text=f"Black: {scores[BLACK]} | White: {scores[WHITE]}")
        turn_text = "Black" if self.game.current_player == BLACK else "White"
        self.turn_label.config(text=f"Turn: {turn_text}")

    def handle_click(self, event):
        if self.is_ai_thinking or self.game.current_player != self.player_color:
            return
            
        col = (event.x - BOARD_MARGIN) // CELL_SIZE
        row = (event.y - BOARD_MARGIN) // CELL_SIZE
        
        if 0 <= row < 8 and 0 <= col < 8:
            if self.game.make_move(row, col, self.player_color):
                self.post_move_cleanup()

    def post_move_cleanup(self):
        if self.game.is_game_over():
            self.draw_board()
            print("Game Over detected.")
            self.end_game()
            return
            
        self.game.switch_player()
        print(f"Turn switched to: {'Black' if self.game.current_player == BLACK else 'White'}")
        
        # Check if the next player has moves
        if not self.game.get_legal_moves(self.game.current_player):
            self.draw_board() # Show board state before pass
            messagebox.showinfo("Pass", f"{'Black' if self.game.current_player == BLACK else 'White'} has no moves. Skipping turn.")
            self.game.switch_player()
            print(f"Turn skipped, back to: {'Black' if self.game.current_player == BLACK else 'White'}")
            
            if not self.game.get_legal_moves(self.game.current_player):
                self.draw_board()
                print("Game Over detected after pass.")
                self.end_game()
                return
        
        # Always redraw after switching to the new active player
        self.draw_board()
        
        if self.game.current_player == self.ai_color:
            self.root.after(500, self.trigger_ai_turn)

    def trigger_ai_turn(self):
        self.is_ai_thinking = True
        self.turn_label.config(text="AI is thinking...")
        print("Triggering AI turn...")
        threading.Thread(target=self.ai_turn_worker, daemon=True).start()

    def ai_turn_worker(self):
        try:
            # AI calculation based on selected mode and time
            mode = self.ai_mode.get()
            t_limit = self.thinking_time.get()
            print(f"AI Thinking using mode: {mode}, Time: {t_limit}s")
            
            if mode == "Standard":
                move = get_best_move(self.game, self.ai_color, time_limit=t_limit)
            elif mode == "Pattern V1":
                move = get_best_move_pattern(self.game, self.ai_color, time_limit=t_limit)
            else: # Pattern V2
                move = get_best_move_v2(self.game, self.ai_color, time_limit=t_limit)
                
            time.sleep(0.2) # Small delay for visual flow
            self.root.after(0, self.complete_ai_turn, move)
        except Exception as e:
            print(f"Error in AI worker: {e}")
            self.root.after(0, self.reset_ai_thinking)

    def reset_ai_thinking(self):
        self.is_ai_thinking = False
        self.update_status()

    def complete_ai_turn(self, move):
        print(f"Completing AI turn with move: {move}")
        if move:
            self.game.make_move(move[0], move[1], self.ai_color)
        else:
            print("AI found no valid move.")
        
        self.is_ai_thinking = False
        self.post_move_cleanup()

    def end_game(self):
        scores = self.game.get_score()
        if scores[BLACK] > scores[WHITE]:
            winner = "Black wins!"
        elif scores[WHITE] > scores[BLACK]:
            winner = "White wins!"
        else:
            winner = "It's a draw!"
        
        messagebox.showinfo("Game Over", f"{winner}\nFinal Score - Black: {scores[BLACK]}, White: {scores[WHITE]}")
        self.root.destroy()
