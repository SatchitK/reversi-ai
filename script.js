const EMPTY = 0, BLACK = 1, WHITE = 2;
const DIRS = [[0,1],[0,-1],[1,0],[-1,0],[1,1],[1,-1],[-1,1],[-1,-1]];

let board = [];
let currentPlayer = BLACK; // Black always starts in Reversi
let userColor = BLACK;
let aiColor = WHITE;
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

    if (userColor === WHITE) {
        setTimeout(playAI, 500);
    }
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
    const validMoves = (currentPlayer === userColor && !isAiThinking) ? getMoves(userColor) : [];
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
        const userScore = counts[userColor];
        const aiScore = counts[aiColor];
        statusMsg.textContent = userScore > aiScore ? "You Win!" : aiScore > userScore ? "AI Wins!" : "Tie Game!";
    } else if (isAiThinking) {
        statusMsg.textContent = "AI is thinking...";
    } else {
        statusMsg.textContent = currentPlayer === userColor ? "Your move" : "AI's move";
    }
};

const handleMove = async (r, c) => {
    if (isAiThinking || currentPlayer !== userColor || !applyMove(r, c, userColor)) return;
    
    currentPlayer = aiColor;
    render();
    setTimeout(playAI, 50);
};

const playAI = async () => {
    const moves = getMoves(aiColor);
    if (!moves.length) {
        currentPlayer = userColor;
        render();
        return;
    }

    isAiThinking = true;
    render();

    try {
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ board, player: aiColor })
        });
        const { move } = await res.json();
        if (move) applyMove(move[0], move[1], aiColor);
    } catch (err) {
        console.error("AI Error:", err);
        statusMsg.textContent = "Connection error";
    }

    isAiThinking = false;
    currentPlayer = userColor;
    
    if (!getMoves(userColor).length && getMoves(aiColor).length) {
        render();
        setTimeout(() => {
            currentPlayer = aiColor;
            playAI();
        }, 1000);
    } else {
        render();
    }
};

// UI Handlers
document.getElementById('restart-btn').onclick = initGame;

document.getElementById('select-black').onclick = () => {
    if (userColor === BLACK) return;
    userColor = BLACK;
    aiColor = WHITE;
    document.getElementById('select-black').classList.add('active');
    document.getElementById('select-white').classList.remove('active');
    initGame();
};

document.getElementById('select-white').onclick = () => {
    if (userColor === WHITE) return;
    userColor = WHITE;
    aiColor = BLACK;
    document.getElementById('select-white').classList.add('active');
    document.getElementById('select-black').classList.remove('active');
    initGame();
};

initGame();