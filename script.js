const EMPTY = 0, BLACK = 1, WHITE = 2;
const DIRS = [[0,1],[0,-1],[1,0],[-1,0],[1,1],[1,-1],[-1,1],[-1,-1]];

let board = [];
let currentPlayer = BLACK;
let isAiThinking = false;

const boardEl = document.getElementById('board');
const statusMsg = document.getElementById('status-message');
const scores = {
    [BLACK]: document.getElementById('black-score'),
    [WHITE]: document.getElementById('white-score')
};
const scoreDivs = {
    [BLACK]: document.querySelector('.black-score'),
    [WHITE]: document.querySelector('.white-score')
};

const initGame = () => {
    board = Array.from({ length: 8 }, () => Array(8).fill(EMPTY));
    board[3][3] = BLACK;
    board[4][4] = BLACK;
    board[3][4] = WHITE;
    board[4][3] = WHITE;
    currentPlayer = BLACK;
    isAiThinking = false;
    render();
};

const isLegalMove = (r, c, player) => {
    if (board[r][c] !== EMPTY) return false;
    const opp = player === BLACK ? WHITE : BLACK;
    
    for (const [dr, dc] of DIRS) {
        let nr = r + dr, nc = c + dc;
        if (board[nr]?.[nc] === opp) {
            while (board[nr += dr]?.[nc += dc] !== undefined) {
                if (board[nr][nc] === player) return true;
                if (board[nr][nc] === EMPTY) break;
            }
        }
    }
    return false;
};

const getMoves = (player) => {
    const moves = [];
    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            if (isLegalMove(r, c, player)) moves.push([r, c]);
        }
    }
    return moves;
};

const applyMove = (r, c, player) => {
    if (!isLegalMove(r, c, player)) return false;
    
    board[r][c] = player;
    const opp = player === BLACK ? WHITE : BLACK;
    
    for (const [dr, dc] of DIRS) {
        const flips = [];
        let nr = r + dr, nc = c + dc;
        
        while (board[nr]?.[nc] === opp) {
            flips.push([nr, nc]);
            nr += dr; nc += dc;
        }
        
        if (board[nr]?.[nc] === player) {
            for (const [fr, fc] of flips) board[fr][fc] = player;
        }
    }
    return true;
};

const render = () => {
    boardEl.innerHTML = '';
    const validMoves = (currentPlayer === BLACK && !isAiThinking) ? getMoves(BLACK) : [];
    let counts = { [BLACK]: 0, [WHITE]: 0 };

    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            const val = board[r][c];
            if (val) counts[val]++;

            const cell = document.createElement('div');
            cell.className = 'cell';
            
            const disc = document.createElement('div');
            disc.className = `cell-disc ${val === BLACK ? 'black' : val === WHITE ? 'white' : ''}`;
            
            if (val === EMPTY && validMoves.some(([mr, mc]) => mr === r && mc === c)) {
                disc.classList.add('valid-move');
            }
            
            cell.appendChild(disc);
            cell.onclick = () => handleMove(r, c);
            boardEl.appendChild(cell);
        }
    }

    scores[BLACK].textContent = counts[BLACK];
    scores[WHITE].textContent = counts[WHITE];

    scoreDivs[BLACK].classList.toggle('active', currentPlayer === BLACK);
    scoreDivs[WHITE].classList.toggle('active', currentPlayer === WHITE);

    const blackMoves = getMoves(BLACK).length;
    const whiteMoves = getMoves(WHITE).length;

    if (!blackMoves && !whiteMoves) {
        const diff = counts[BLACK] - counts[WHITE];
        statusMsg.textContent = diff > 0 ? "You Win!" : diff < 0 ? "AI Wins!" : "Tie Game!";
    } else if (isAiThinking) {
        statusMsg.textContent = "Thinking...";
    } else {
        statusMsg.textContent = currentPlayer === BLACK ? "Your move" : "AI's move";
    }
};

const handleMove = async (r, c) => {
    if (isAiThinking || currentPlayer !== BLACK || !applyMove(r, c, BLACK)) return;
    
    currentPlayer = WHITE;
    render();
    setTimeout(playAI, 50);
};

const playAI = async () => {
    if (!getMoves(WHITE).length) {
        currentPlayer = BLACK;
        render();
        return;
    }

    isAiThinking = true;
    render();

    try {
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ board, player: WHITE })
        });
        const { move } = await res.json();
        if (move) applyMove(move[0], move[1], WHITE);
    } catch (err) {
        console.error("AI Error:", err);
        statusMsg.textContent = "Connection error";
    }

    isAiThinking = false;
    currentPlayer = BLACK;
    
    if (!getMoves(BLACK).length && getMoves(WHITE).length) {
        render();
        setTimeout(() => {
            currentPlayer = WHITE;
            playAI();
        }, 1000);
    } else {
        render();
    }
};

document.getElementById('restart-btn').onclick = initGame;
initGame();