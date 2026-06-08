import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

# Add root directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from reversi_logic import ReversiGame, WHITE
from reversi_ai import get_best_move, get_best_move_pattern

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(content_length))
        
        game = ReversiGame()
        game.board = data.get('board', game.board)
        player = data.get('player', WHITE)
        engine = data.get('aiEngine', 'standard')
        
        if engine == 'pattern':
            move = get_best_move_pattern(game, player, time_limit=1.5)
        else:
            move = get_best_move(game, player, time_limit=1.5)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"move": move}).encode('utf-8'))
        
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"API is running.")