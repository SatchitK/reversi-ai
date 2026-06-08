const EMPTY = 0, BLACK = 1, WHITE = 2;
const START_GP = 'gp', START_NORMAL = 'normal';
const DIRS = [[0,1],[0,-1],[1,0],[-1,0],[1,1],[1,-1],[-1,1],[-1,-1]];

let board = [];
let currentPlayer = BLACK; 
let userColor = BLACK;
let aiColor = WHITE;
let isAiThinking = false;
let startMode = START_GP;
let aiEngine = 'standard';
let gameState = 'setup'; // 'setup' or 'playing'
let lastMove = null; // Track the last move made [r, c]

const boardEl = document.getElementById('board');
const statusMsg = document.getElementById('status-message');
const restartBtn = document.getElementById('restart-btn');
const scores = {
    [BLACK]: document.getElementById('black-score'),
    [WHITE]: document.getElementById('white-score')
};
const scoreDivs = {
    [BLACK]: document.querySelector('.black-score'),
    [WHITE]: document.querySelector('.white-score')
};

// Persistent DOM elements for the board
const cellElements = [];
const discElements = [];

const createBoard = () => {
    boardEl.innerHTML = '';
    cellElements.length = 0;
    discElements.length = 0;
    
    for (let r = 0; r < 8; r++) {
        cellElements[r] = [];
        discElements[r] = [];
        for (let c = 0; c < 8; c++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            
            const disc = document.createElement('div');
            disc.className = 'cell-disc';
            
            cell.appendChild(disc);
            cell.onclick = () => handleMove(r, c);
            boardEl.appendChild(cell);
            
            cellElements[r][c] = cell;
            discElements[r][c] = disc;
        }
    }
};

const initGame = () => {
    if (cellElements.length === 0) createBoard();
    
    board = Array.from({ length: 8 }, () => Array(8).fill(EMPTY));
    if (startMode === START_GP) {
        board[3][3] = BLACK;
        board[4][4] = BLACK;
        board[3][4] = WHITE;
        board[4][3] = WHITE;
    } else {
        board[3][3] = WHITE;
        board[4][4] = WHITE;
        board[3][4] = BLACK;
        board[4][3] = BLACK;
    }
    currentPlayer = BLACK;
    isAiThinking = false;
    gameState = 'setup';
    lastMove = null;
    
    // UI state
    document.querySelectorAll('.color-btn, .setting-btn, .engine-btn').forEach(btn => btn.disabled = false);
    restartBtn.textContent = 'Start Game';
    boardEl.classList.add('setup');
    
    render();
};

const startGame = () => {
    gameState = 'playing';
    document.querySelectorAll('.color-btn, .setting-btn, .engine-btn').forEach(btn => btn.disabled = true);
    restartBtn.textContent = 'Restart Game';
    boardEl.classList.remove('setup');
    
    render();

    if (currentPlayer === aiColor) {
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
    const validMoves = (gameState === 'playing' && currentPlayer === userColor && !isAiThinking) ? getMoves(userColor) : [];
    let counts = { [BLACK]: 0, [WHITE]: 0 };

    for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
            const val = board[r][c];
            if (val) counts[val]++;

            const disc = discElements[r][c];
            disc.className = 'cell-disc';
            
            if (val === BLACK) disc.classList.add('black');
            else if (val === WHITE) disc.classList.add('white');
            
            if (lastMove && lastMove[0] === r && lastMove[1] === c) {
                disc.classList.add('last-move');
            }
            
            if (val === EMPTY && validMoves.some(([mr, mc]) => mr === r && mc === c)) {
                disc.classList.add('valid-move');
            }
        }
    }

    scores[BLACK].textContent = counts[BLACK];
    scores[WHITE].textContent = counts[WHITE];

    scoreDivs[BLACK].classList.toggle('active', currentPlayer === BLACK);
    scoreDivs[WHITE].classList.toggle('active', currentPlayer === WHITE);

    if (gameState === 'setup') {
        statusMsg.textContent = "Select options & Start";
        return;
    }

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
    if (gameState !== 'playing' || isAiThinking || currentPlayer !== userColor || !applyMove(r, c, userColor)) return;
    
    lastMove = [r, c];
    currentPlayer = aiColor;
    render();
    setTimeout(playAI, 50);
};

const playAI = async () => {
    if (gameState !== 'playing') return;
    
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
            body: JSON.stringify({ board, player: aiColor, aiEngine })
        });
        const { move } = await res.json();
        if (move && gameState === 'playing') {
            applyMove(move[0], move[1], aiColor);
            lastMove = [move[0], move[1]];
        }
    } catch (err) {
        console.error("AI Error:", err);
        statusMsg.textContent = "Connection error";
    }

    isAiThinking = false;
    currentPlayer = userColor;
    
    if (gameState === 'playing') {
        if (!getMoves(userColor).length && getMoves(aiColor).length) {
            render();
            setTimeout(() => {
                if (gameState === 'playing') {
                    currentPlayer = aiColor;
                    playAI();
                }
            }, 1000);
        } else {
            render();
        }
    }
};

// UI Handlers
const updateSelectionUI = () => {
    // Play as
    document.getElementById('select-black').classList.toggle('active', userColor === BLACK);
    document.getElementById('select-white').classList.toggle('active', userColor === WHITE);
    
    // Start mode
    document.getElementById('start-gp').classList.toggle('active', startMode === START_GP);
    document.getElementById('start-normal').classList.toggle('active', startMode === START_NORMAL);
    
    // AI Engine
    document.getElementById('engine-standard').classList.toggle('active', aiEngine === 'standard');
    document.getElementById('engine-pattern').classList.toggle('active', aiEngine === 'pattern');
};

restartBtn.onclick = () => {
    if (gameState === 'setup') {
        startGame();
    } else {
        initGame();
    }
};

document.getElementById('select-black').onclick = () => {
    if (userColor === BLACK || gameState === 'playing') return;
    userColor = BLACK;
    aiColor = WHITE;
    updateSelectionUI();
    initGame();
};

document.getElementById('select-white').onclick = () => {
    if (userColor === WHITE || gameState === 'playing') return;
    userColor = WHITE;
    aiColor = BLACK;
    updateSelectionUI();
    initGame();
};

document.getElementById('start-gp').onclick = () => {
    if (startMode === START_GP || gameState === 'playing') return;
    startMode = START_GP;
    updateSelectionUI();
    initGame();
};

document.getElementById('start-normal').onclick = () => {
    if (startMode === START_NORMAL || gameState === 'playing') return;
    startMode = START_NORMAL;
    updateSelectionUI();
    initGame();
};

document.getElementById('engine-standard').onclick = () => {
    if (aiEngine === 'standard' || gameState === 'playing') return;
    aiEngine = 'standard';
    updateSelectionUI();
};

document.getElementById('engine-pattern').onclick = () => {
    if (aiEngine === 'pattern' || gameState === 'playing') return;
    aiEngine = 'pattern';
    updateSelectionUI();
};

initGame();
updateSelectionUI();