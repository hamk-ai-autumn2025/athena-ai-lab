/* =========================================================================
    Pelikoodi - LOPPURUUTU VERSIO
   ========================================================================= */

// Apufunktioita
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Loppuruudun näyttäminen
function showGameOverlay({ icon, title, message, showRestart = false, onRestart = null }) {
    const overlay = $('gameOverlay');
    const overlayIcon = $('overlayIcon');
    const overlayTitle = $('overlayTitle');
    const overlayMessage = $('overlayMessage');
    const overlayRestart = $('overlayRestart');
    const overlayTimer = $('overlayTimer');
    
    if (!overlay) return;
    
    if (overlayIcon) overlayIcon.textContent = icon;
    if (overlayTitle) overlayTitle.textContent = title;
    if (overlayMessage) overlayMessage.innerHTML = message;
    
    if (overlayRestart) {
        if (showRestart) {
            overlayRestart.classList.remove('d-none');
            overlayRestart.onclick = () => {
                overlay.classList.add('d-none');
                if (onRestart) onRestart();
            };
        } else {
            overlayRestart.classList.add('d-none');
        }
    }
    
    overlay.classList.remove('d-none');
    
    // Lähetä completion
    const gameInfo = document.getElementById('game-info');
    if (gameInfo) {
        const completionUrl = gameInfo.dataset.completionUrl;
        if (completionUrl) {
            const csrftoken = getCookie('csrftoken');
            fetch(completionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({
                    score: 100,
                    completed: true
                })
            }).catch(error => console.error('Virhe:', error));
        }
    }
    
    // Ajastin
    let countdown = 8;
    if (overlayTimer) overlayTimer.textContent = `Palataan etusivulle ${countdown} sekunnin kuluttua...`;
    
    const timer = setInterval(() => {
        countdown--;
        if (overlayTimer) overlayTimer.textContent = `Palataan etusivulle ${countdown} sekunnin kuluttua...`;
        if (countdown <= 0) {
            clearInterval(timer);
            window.location.href = 'http://127.0.0.1:8000/';
        }
    }, 1000);
}

const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const cssVar = (name, fallback) => (getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback);
function shuffleArray(a) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[a[i], a[j]] = [a[j], a[i]]; } }

let actx;
function playSound(type) {
    if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)();
    const o = actx.createOscillator(); const g = actx.createGain();
    o.connect(g); g.connect(actx.destination); g.gain.setValueAtTime(0, actx.currentTime);
    const t0 = actx.currentTime;
    if (type === 'correct') { o.frequency.setValueAtTime(800, t0); o.frequency.linearRampToValueAtTime(1200, t0 + 0.1); }
    else if (type === 'wrong') { o.frequency.setValueAtTime(400, t0); o.frequency.linearRampToValueAtTime(200, t0 + 0.1); }
    else if (type === 'goal') { o.type = 'triangle'; o.frequency.setValueAtTime(523.25, t0); o.frequency.setValueAtTime(659.25, t0 + 0.2); o.frequency.setValueAtTime(783.99, t0 + 0.4); o.frequency.setValueAtTime(1046.50, t0 + 0.6); }
    g.gain.linearRampToValueAtTime(type === 'goal' ? 0.1 : 0.05, t0 + 0.02);
    g.gain.linearRampToValueAtTime(0, t0 + (type === 'goal' ? 1.2 : 0.2));
    o.start(t0); o.stop(t0 + (type === 'goal' ? 1.2 : 0.2));
}

// ================== VISA-PELIN KAIKKI KOODI ================== 
let questions = [], qIndex = 0, score = 0, locked = false, position = 0;
let allCorrect = true, lastAnswerWasCorrect = null, timeLeft = 20;
let timerId = null, qToken = 0, stops = [], gamePath = [];
let gameEnded = false;
let initialGameData = null;

const el = {
    score: $('score'), levelBadge: $('levelBadge'), question: $('question'), choices: $('choices'), feedback: $('feedback'),
    next: $('btnNext'), boardSvg: $('boardSvg'), hero: $('hero'), timer: $('timer'), restart: $('btnRestart')
};
const PATH_LENGTHS = { easy: 5, medium: 10, hard: 15 };
const predefinedPaths = {
  '5':  [ 
    {x:100,y:550},{x:250,y:600},{x:450,y:580},{x:700,y:520},{x:950,y:480},{x:1150,y:300}
  ],
  '10': [ 
    {x:80,y:550},{x:180,y:620},{x:320,y:600},{x:420,y:500},{x:350,y:380},{x:500,y:280},{x:650,y:350},{x:800,y:280},{x:920,y:400},{x:1040,y:520},{x:1150,y:200}
  ],
  '15': [ 
    {x:80,y:450},{x:150,y:580},{x:120,y:640},{x:280,y:650},{x:400,y:600},{x:500,y:640},{x:640,y:620},{x:720,y:540},{x:650,y:420},{x:550,y:320},{x:680,y:240},{x:820,y:280},{x:900,y:380},{x:980,y:500},{x:1080,y:560},{x:1150,y:200}
  ]
};

function createStarfieldSVG(width, height) {
    let content = `<rect width="${width}" height="${height}" fill="${cssVar('--bg-main', '#0a0f2a')}"/>`;
    for (let i = 0; i < 150; i++) {
        const r = Math.random() * 1.5;
        content += `<circle cx="${Math.random()*width}" cy="${Math.random()*height}" r="${r}" fill="white" opacity="${Math.random()*0.6 + 0.2}"/>`;
    }
    return content;
}

function drawBoardBackground() {
    if(!el.boardSvg) return;
    el.boardSvg.innerHTML = createStarfieldSVG(1200, 675);
}

function setupGamePathByDifficulty(difficulty) {
    const totalLen = PATH_LENGTHS[difficulty] || 10;
    questions = questions.slice(0, totalLen);
    gamePath = Array.from({ length: totalLen }, () => ({ type: 'question' }));
}


function generateGameBoard() {
    if (!el.boardSvg) return;
    
    el.boardSvg.setAttribute('viewBox', '0 0 1200 675');
    el.boardSvg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    el.boardSvg.innerHTML = '';
    
    // Tausta
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', '0'); rect.setAttribute('y', '0');
    rect.setAttribute('width', '1200'); rect.setAttribute('height', '675');
    rect.setAttribute('fill', '#0a0f2a');
    el.boardSvg.appendChild(rect);
    
    // Tähdet
    for (let i = 0; i < 200; i++) {
        const star = document.createElementNS(NS, 'circle');
        star.setAttribute('cx', Math.random() * 1200);
        star.setAttribute('cy', Math.random() * 675);
        star.setAttribute('r', Math.random() * 1.8 + 0.3);
        star.setAttribute('fill', 'white');
        star.setAttribute('opacity', Math.random() * 0.7 + 0.2);
        el.boardSvg.appendChild(star);
    }
    
    const pathData = predefinedPaths[String(gamePath.length)];
    if (!pathData) return;
    stops = pathData;
    
    // Polku (kulkee KAIKISTA pisteistä, myös maaliin)
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('class', 'path');
    path.setAttribute('d', `M${stops[0].x},${stops[0].y}` + stops.slice(1).map((p, i) => ` C${(stops[i].x + p.x) / 2},${stops[i].y} ${(stops[i].x + p.x) / 2},${p.y} ${p.x},${p.y}`).join(''));
    el.boardSvg.appendChild(path);
    
    // Numeroruudut (EI maali)
    for (let i = 0; i < gamePath.length; i++) {
        const g = document.createElementNS(NS, 'g');
        g.id = `tile-${i}`; g.classList.add('tile');
        g.setAttribute('transform', `translate(${stops[i].x},${stops[i].y})`);
        g.innerHTML = `<circle class="tile-circle" r="35"></circle><text class="tile-text">${i+1}</text>`;
        el.boardSvg.appendChild(g);
    }
    
    // Maali (viimeinen piste)
    const goalPoint = stops[gamePath.length];
    const goalGroup = document.createElementNS(NS, 'g');
    goalGroup.id = `tile-${gamePath.length}`;
    goalGroup.setAttribute('transform', `translate(${goalPoint.x}, ${goalPoint.y}) scale(1.2)`);
    goalGroup.innerHTML = `<defs><filter id="goal-glow"><feGaussianBlur stdDeviation="7" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><g filter="url(#goal-glow)"><path d="M-30,10 C-30,-20 30,-20 30,10 Q0,25 -30,10 Z" fill="#c0c0c0" stroke="#546e7a" stroke-width="4"/><path d="M-15,-15 C-15,-30 15,-30 15,-15 Z" fill="${cssVar('--accent','#3ddcff')}" stroke="#546e7a" stroke-width="3"/></g><text y="-40" text-anchor="middle" class="goal-text">Maali</text>`;
    el.boardSvg.appendChild(goalGroup);
}

function positionHero(pos, instant = false) {
    if (!stops || !stops[pos]) {
        // Jos pos on gamePath.length (maali), käytä maalikoordinaattia
        if (pos === gamePath.length) {
            const pathConfig = predefinedPaths[String(gamePath.length)];
            if (!pathConfig) return;
            const goalPos = pathConfig.goal;
            el.hero.style.transition = instant ? 'none' : 'left .6s ease-in-out, top .6s ease-in-out';
            el.hero.style.left = `${(goalPos.x / 1200) * 100}%`;
            el.hero.style.top = `${(goalPos.y / 675) * 100}%`;
            return;
        }
        return;
    }
    
    const { x, y } = stops[pos];
    el.hero.style.transition = instant ? 'none' : 'left .6s ease-in-out, top .6s ease-in-out';
    el.hero.style.left = `${(x / 1200) * 100}%`;
    el.hero.style.top = `${(y / 675) * 100}%`;
    document.querySelectorAll('.tile.current').forEach(t => t.classList.remove('current'));
    $(`tile-${pos}`)?.classList.add('current');
}

function clearTimer() { if (timerId) clearInterval(timerId); timerId = null; }

function startTimer() {
    clearTimer(); timeLeft = 20; if(el.timer) el.timer.textContent = `${timeLeft}s`;
    const myToken = ++qToken;
    timerId = setInterval(() => {
        timeLeft--; if(el.timer) el.timer.textContent = `${timeLeft}s`;
        if(el.timer) {
            el.timer.classList.toggle('critical', timeLeft <= 5);
            el.timer.classList.toggle('low', timeLeft > 5 && timeLeft <= 10);
        }
        if (timeLeft <= 0) { clearTimer(); onTimeout(myToken); }
    }, 1000);
}

function onTimeout(myToken) {
    if (myToken !== qToken || locked || gameEnded) return;
    locked = true; lastAnswerWasCorrect = false; playSound('wrong');
    $(`tile-${position}`)?.classList.add('wrong');
    if(el.feedback) {
        el.feedback.className = 'alert alert-warning mt-4';
        el.feedback.textContent = 'Aika loppui!';
        el.feedback.classList.remove('d-none');
    }
    if (isLastQuestion()) setTimeout(() => advanceAfterAnswer(false), 600);
    else if(el.next) { el.next.disabled = false; el.next.classList.remove('d-none'); }
}

function currentQuestion() { return questions[qIndex] || null; }
function isLastQuestion() { return qIndex === questions.length - 1; }

function getShuffledChoices(level) {
    const arr = level.choices.map((text, i) => ({ text, isCorrect: i === level.correct }));
    shuffleArray(arr); return arr;
}

function renderQuestion() {
    if (gameEnded) return;
    
    const L = currentQuestion();
    if (!L || !el.choices) { endGame(allCorrect); return; }
    locked = false; 
    
    if(el.feedback) el.feedback.classList.add('d-none');
    
    if(el.levelBadge) el.levelBadge.textContent = `Kysymys ${qIndex + 1}/${gamePath.length}`;
    if(el.question) el.question.textContent = L.question;
    el.choices.innerHTML = '';
    getShuffledChoices(L).forEach(opt => {
        const b = document.createElement('button');
        b.className = 'btn btn-outline-secondary choice-btn';
        b.textContent = opt.text; b.dataset.correct = opt.isCorrect;
        b.onclick = onChoose; el.choices.appendChild(b);
    });
    if(el.next) { el.next.classList.add('d-none'); el.next.disabled = true; }
    startTimer();
}

function onChoose(e) {
    if (locked || gameEnded) return;
    locked = true; clearTimer();
    const btn = e.currentTarget;
    const ok = btn.dataset.correct === 'true';
    lastAnswerWasCorrect = ok;
    playSound(ok ? 'correct' : 'wrong');
    if(el.choices) {
        el.choices.querySelectorAll('button').forEach(b => {
            b.disabled = true; if (b.dataset.correct === 'true') b.classList.add('correct');
        });
    }
    if (!ok) btn.classList.add('wrong');
    const L = currentQuestion();
    if(el.feedback) {
        el.feedback.className = ok ? 'alert alert-success mt-4' : 'alert alert-danger mt-4';
        el.feedback.textContent = L.explanation || (ok ? 'Oikein!' : 'Väärin!');
        el.feedback.classList.remove('d-none');
    }
    $(`tile-${position}`)?.classList.add(ok ? 'correct' : 'wrong');
    if (isLastQuestion()) setTimeout(() => advanceAfterAnswer(ok), 800);
    else if(el.next) { el.next.disabled = false; el.next.classList.remove('d-none'); }
}

function advanceAfterAnswer(ok) {
    if (gameEnded) return;
    
    if (!ok) allCorrect = false;
    if (ok) { score++; if(el.score) el.score.textContent = String(score); }
    position++; qIndex++;
    if (position >= gamePath.length) { 
        endGame(allCorrect); 
        return; 
    }
    positionHero(position);
    setTimeout(renderQuestion, 600);
}

function endGame(won) {
    gameEnded = true;
    clearTimer();
    if (el.next) el.next.classList.add('d-none');
    
    if (won) {
        if(el.hero) positionHero(gamePath.length);
        playSound('goal');
        
        showGameOverlay({
            icon: '🎉',
            title: 'Hienoa!',
            message: `Pääsit maaliin!<br><br>Sait <strong>${score}/${gamePath.length}</strong> pistettä.`,
            showRestart: true,
            onRestart: () => {
                const difficulty = initialGameData?.difficulty || 'medium';
                resetGameWith({ difficulty, initialQuestions: initialGameData?.levels || [] });
            }
        });
    } else {
        showGameOverlay({
            icon: '😢',
            title: 'Peli ohi!',
            message: `Sait <strong>${score}/${gamePath.length}</strong> pistettä.<br><br>Yritä uudelleen!`,
            showRestart: true,
            onRestart: () => {
                const difficulty = initialGameData?.difficulty || 'medium';
                resetGameWith({ difficulty, initialQuestions: initialGameData?.levels || [] });
            }
        });
    }
}

function resetGameWith({ difficulty, initialQuestions }) {
    gameEnded = false;
    clearTimer(); [qToken, allCorrect, locked, position, qIndex, score] = [0, true, false, 0, 0, 0];
    questions = initialQuestions || [];
    if(el.score) el.score.textContent = '0';
    if($('game')) $('game').classList.remove('d-none');
    if(el.feedback) el.feedback.classList.add('d-none');
    if(el.restart) el.restart.classList.add('d-none');
    if(el.hero) el.hero.style.visibility = 'visible';

    const startImageContainer = $('start-image-container');
    if (startImageContainer) {
        startImageContainer.style.opacity = '0';
        startImageContainer.style.visibility = 'hidden';
    }

    setupGamePathByDifficulty(difficulty);
    generateGameBoard();
    positionHero(0, true);
    renderQuestion();
}

// ================== HIRSIPUU-PELIN KAIKKI KOODI ==================
const HM_MAX_LIVES = 7;
const FI_ALPHABET = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ'];
let hmWord = '', hmMasked = [], hmLivesLeft = HM_MAX_LIVES, hmGuessed = new Set(), hmTopicStr = '';
const hmEl = { lives: $('hmLives'), topic: $('hmTopic'), masked: $('hmMasked'), letters: $('hmLetters'), feedback: $('hmFeedback') };

function hmStartRound({ topic, word }) {
    gameEnded = false;
    hmTopicStr = topic;
    hmWord = String(word || '').toUpperCase();
    hmLivesLeft = HM_MAX_LIVES;
    hmGuessed.clear();
    hmMasked = Array.from(hmWord, () => '_');
    if(hmEl.topic) hmEl.topic.textContent = hmTopicStr;
    if(hmEl.lives) hmEl.lives.textContent = String(hmLivesLeft);
    if(hmEl.masked) hmEl.masked.textContent = hmMasked.join(' ');
    if(hmEl.feedback) hmEl.feedback.classList.add('d-none');
    if(hmEl.letters) {
        hmEl.letters.innerHTML = '';
        FI_ALPHABET.forEach(letter => {
            const b = document.createElement('button');
            b.className = 'btn btn-outline-secondary btn-sm'; b.textContent = letter;
            b.onclick = () => hmGuess(letter, b);
            hmEl.letters.appendChild(b);
        });
    }
    hmRenderParts();
}

function hmGuess(letter, btn) {
    if (gameEnded || hmLivesLeft <= 0 || hmMasked.join('') === hmWord || hmGuessed.has(letter)) return;
    hmGuessed.add(letter);
    const hits = hmWord.split('').reduce((acc, ch, i) => (ch === letter ? [...acc, i] : acc), []);
    if (hits.length) {
        playSound('correct');
        hits.forEach(i => hmMasked[i] = letter);
        if(hmEl.masked) hmEl.masked.textContent = hmMasked.join(' ');
        btn.className += ' correct';
        btn.disabled = true;
        if (hmMasked.join('') === hmWord) {
            setTimeout(() => hmLoseWin(true), 300);
        }
    } else {
        playSound('wrong');
        hmLivesLeft--;
        if(hmEl.lives) hmEl.lives.textContent = String(hmLivesLeft);
        btn.className += ' wrong';
        btn.disabled = true;
        hmRenderParts();
        if (hmLivesLeft <= 0) {
            setTimeout(() => hmLoseWin(false), 300);
        }
    }
}

function hmLoseWin(won) {
    gameEnded = true;
    
    if (won) {
        playSound('goal');
        showGameOverlay({
            icon: '🎉',
            title: 'Hienoa!',
            message: 'Arvasit sanan oikein!',
            showRestart: false
        });
        submitGameCompletion(100);
    } else {
        showGameOverlay({
            icon: '😢',
            title: 'Hups!',
            message: `Oikea sana oli: <strong>${hmWord}</strong>`,
            showRestart: false
        });
        submitGameCompletion(0);
    }
}

function hmRenderParts() {
    const svg = $('hmSvg'); if(!svg) return;
    const misses = HM_MAX_LIVES - hmLivesLeft;
    const teline = `<line x1="20" y1="210" x2="180" y2="210" stroke-width="6" stroke="${cssVar('--accent')}"/>` + `<line x1="40" y1="210" x2="40" y2="20" stroke-width="6"/>` + `<line x1="40" y1="20" x2="130" y2="20" stroke-width="6"/>` + `<line x1="130" y1="20" x2="130" y2="50" stroke-width="4"/>`;
    const parts = [
        `<circle cx="130" cy="65" r="15" fill="none" stroke-width="4"/>`, `<line x1="130" y1="80" x2="130" y2="125" stroke-width="4"/>`,
        `<line x1="130" y1="92" x2="110" y2="110" stroke-width="4"/>`, `<line x1="130" y1="92" x2="150" y2="110" stroke-width="4"/>`,
        `<line x1="130" y1="125" x2="112" y2="155" stroke-width="4"/>`, `<line x1="130" y1="125" x2="148" y2="155" stroke-width="4"/>`,
        `<g stroke-width="2.5"><line x1="124" y1="60" x2="128" y2="64"/><line x1="128" y1="60" x2="124" y2="64"/><line x1="132" y1="60" x2="136" y2="64"/><line x1="136" y1="60" x2="132" y2="64"/></g>`
    ];
    svg.innerHTML = teline + `<g stroke-linecap="round" stroke="${cssVar('--text-light')}">${parts.slice(0, misses).join('')}</g>`;
}

// ================== MUISTIPELI-PELIN KAIKKI KOODI ==================
let mmDeck = [], mmFirst = null, mmSecond = null, mmFoundCount = 0, mmTryCount = 0, mmLock = false;
const mmEl = { grid:$('mmGrid'), found:$('mmFound'), tries:$('mmTries'), feedback:$('mmFeedback') };

function mmStartWithPairs(pairs) {
    gameEnded = false;
    [mmFoundCount, mmTryCount, mmFirst, mmSecond, mmLock] = [0, 0, null, null, false];
    if(mmEl.found) mmEl.found.textContent = '0';
    if(mmEl.tries) mmEl.tries.textContent = '0';
    if(mmEl.feedback) mmEl.feedback.classList.add('d-none');
    mmDeck = [];
    
    (pairs || []).forEach((p, i) => {
        // Ota kaksi ensimmäistä arvoa objektista, kentän nimestä riippumatta
        const values = Object.values(p);
        const text1 = String(values[0] || '');
        const text2 = String(values[1] || '');
        
        mmDeck.push({ text: text1, pairId: i, flipped: false, matched: false });
        mmDeck.push({ text: text2, pairId: i, flipped: false, matched: false });
    });
    
    shuffleArray(mmDeck);
    renderMmGrid();
}

function renderMmGrid() {
    if(!mmEl.grid) return;
    mmEl.grid.innerHTML = '';
    mmDeck.forEach((card) => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-secondary w-100 p-3';
        btn.style.minHeight = '72px';
        btn.textContent = '❓';
        btn.onclick = () => mmFlip(card, btn);
        const col = document.createElement('div');
        col.className = 'col-6 col-md-3 col-lg-2-4';
        col.appendChild(btn);
        mmEl.grid.appendChild(col);
    });
}

function mmFlip(card, btn) {
    if (gameEnded || mmLock || card.flipped || card.matched) return;
    card.flipped = true; btn.textContent = card.text;
    if (!mmFirst) { mmFirst = {card, btn}; return; }
    mmSecond = {card, btn};
    mmCheck();
}

function mmCheck() {
    mmLock = true; mmTryCount++; if(mmEl.tries) mmEl.tries.textContent = String(mmTryCount);
    const samePair = mmFirst.card.pairId === mmSecond.card.pairId;
    if (samePair) {
        playSound('correct');
        [mmFirst, mmSecond].forEach(c => { c.card.matched = true; c.btn.classList.add('correct'); });
        mmFoundCount++; if(mmEl.found) mmEl.found.textContent = String(mmFoundCount);
        if (mmFoundCount === (mmDeck.length / 2)) setTimeout(() => mmWin(), 300);
        setTimeout(() => { mmFirst = mmSecond = null; mmLock = false; }, 300);
    } else {
        playSound('wrong');
        setTimeout(() => {
            [mmFirst, mmSecond].forEach(c => { c.card.flipped = false; c.btn.textContent = '❓'; });
            mmFirst = mmSecond = null; mmLock = false;
        }, 800);
    }
}

function mmWin() {
    gameEnded = true;
    playSound('goal');
    
    showGameOverlay({
        icon: '🎉',
        title: 'Hienoa!',
        message: `Kaikki parit löydetty <strong>${mmTryCount}</strong> yrityksellä!`,
        showRestart: false
    });
    submitGameCompletion(100);
}

// ================== PELIN SUORITTAMISEN LÄHETTÄMINEN ==================
async function submitGameCompletion(score) {
    const gameInfo = $('game-info');
    if (!gameInfo) return;
    
    const completionUrl = gameInfo.dataset.completionUrl;
    if (!completionUrl) return;
    
    try {
        const response = await fetch(completionUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ score: score })
        });
        
        const data = await response.json();
        console.log('Game completion:', data);
    } catch (error) {
        console.error('Error submitting completion:', error);
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// ================== TAUSTA-ANIMAATIO ==================
let isAnimationPaused = false;
let animationFrameId = null;
let canvas, ctx, stars = [], planets = [], asteroids = [], comets = [];
let width, height;
let planetColors, createAsteroidShape, createComet;

function setupBackground() {
    canvas = document.getElementById('space-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    planetColors = [ { main: "#d9534f" }, { main: "#ffc107" }, { main: "#4fc3f7" }, { main: "#6fde6f" }, { main: "#f39c12" }, { main: "#9c27b0" } ];
    createAsteroidShape = (radius) => { const shape = []; const segments = Math.floor(Math.random() * 5) + 7; for (let i = 0; i < segments; i++) { const angle = (i / segments) * Math.PI * 2; const dist = radius * (Math.random() * 0.4 + 0.8); shape.push({ x: Math.cos(angle) * dist, y: Math.sin(angle) * dist }); } return shape; };
    createComet = () => { comets.push({ x: Math.random() * width, y: 0, radius: Math.random() * 2 + 1, speed: { x: ((Math.random() - 0.5) * 8) / 3, y: (Math.random() * 6 + 4) / 3 }, tail: [], tailLength: 20 }); };
    window.addEventListener('resize', resize);
    resize();
    animate();
}

function resize() {
    const wrapper = document.querySelector('.game-content-wrapper') || document.body;
    width = wrapper.clientWidth;
    height = wrapper.clientHeight;
    
    if (!canvas) return;
    canvas.width = width;
    canvas.height = height;
    stars = []; for (let i = 0; i < 200; i++) { stars.push({ x: Math.random() * width, y: Math.random() * height, radius: Math.random() * 1.5 + 0.5, alpha: Math.random(), speed: (Math.random() * 0.2 + 0.1) / 4 }); }
    planets = []; for (let i = 0; i < 5; i++) { const colorSet = planetColors[i % planetColors.length]; planets.push({ x: Math.random() * width, y: Math.random() * height, radius: Math.random() * 30 + 20, speed: (Math.random() * 0.05 + 0.02) / 4, mainColor: colorSet.main, hasRing: Math.random() > 0.6 }); }
    asteroids = []; for (let i = 0; i < 10; i++) { const radius = Math.random() * 15 + 5; asteroids.push({ x: Math.random() * width, y: Math.random() * height, shape: createAsteroidShape(radius), rotation: Math.random() * Math.PI * 2, rotationSpeed: (Math.random() - 0.5) * 0.005, speed: (Math.random() * 0.1 + 0.05) / 4, color: `hsl(0, 0%, ${Math.floor(Math.random() * 20) + 30}%)`, borderColor: `hsl(0, 0%, ${Math.floor(Math.random() * 10) + 20}%)` }); }
}

function animate() {
    if (isAnimationPaused) return;
    
    if (!ctx) { 
        if (animationFrameId) cancelAnimationFrame(animationFrameId); 
        return; 
    }
    
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = cssVar('--bg-main', '#0a0f2a');
    ctx.fillRect(0, 0, width, height);
    asteroids.forEach(a => { a.y -= a.speed; a.rotation += a.rotationSpeed; if (a.y < -30) { a.y = height + 30; a.x = Math.random() * width; } ctx.save(); ctx.translate(a.x, a.y); ctx.rotate(a.rotation); ctx.beginPath(); ctx.moveTo(a.shape[0].x, a.shape[0].y); a.shape.forEach(p => ctx.lineTo(p.x, p.y)); ctx.closePath(); ctx.fillStyle = a.color; ctx.strokeStyle = a.borderColor; ctx.lineWidth = 2; ctx.fill(); ctx.stroke(); ctx.restore(); });
    planets.forEach(p => { p.y -= p.speed; if (p.y < -p.radius * 2) { p.y = height + p.radius * 2; p.x = Math.random() * width; } ctx.fillStyle = p.mainColor; ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill(); const hg = ctx.createRadialGradient(p.x - p.radius * 0.3, p.y - p.radius * 0.4, 0, p.x, p.y, p.radius * 1.2); hg.addColorStop(0, 'rgba(255, 255, 255, 0.3)'); hg.addColorStop(1, 'rgba(255, 255, 255, 0)'); ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill(); if (p.hasRing) { ctx.strokeStyle = `rgba(255, 255, 255, 0.4)`; ctx.lineWidth = p.radius * 0.1; ctx.beginPath(); ctx.ellipse(p.x, p.y, p.radius * 1.5, p.radius * 0.4, Math.PI / 8, 0, Math.PI * 2); ctx.stroke(); } });
    stars.forEach(star => { star.y -= star.speed; if (star.y < 0) { star.y = height; star.x = Math.random() * width; } ctx.beginPath(); ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2); ctx.fillStyle = `rgba(255, 255, 255, ${star.alpha})`; ctx.fill(); });
    if (Math.random() > 0.998 && comets.length < 3) { createComet(); }
    comets.forEach((comet, index) => { comet.x += comet.speed.x; comet.y += comet.speed.y; comet.tail.push({ x: comet.x, y: comet.y, radius: comet.radius }); if (comet.tail.length > comet.tailLength) { comet.tail.shift(); } comet.tail.forEach((t, i) => { const alpha = (i / comet.tailLength) * 0.5; ctx.beginPath(); ctx.arc(t.x, t.y, t.radius * (i / comet.tailLength), 0, Math.PI * 2); ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`; ctx.fill(); }); ctx.beginPath(); ctx.arc(comet.x, comet.y, comet.radius, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'; ctx.fill(); if (comet.x < -10 || comet.x > width + 10 || comet.y > height + 10) { comets.splice(index, 1); } });
    animationFrameId = requestAnimationFrame(animate);
}

// ================== SIVUN KÄYNNISTYS ==================
document.addEventListener('DOMContentLoaded', () => {
    setupBackground();

    const btnToggle = document.getElementById('btnToggleBackground');
    if (btnToggle) {
        btnToggle.addEventListener('click', () => {
            isAnimationPaused = !isAnimationPaused;
            if (isAnimationPaused) {
                cancelAnimationFrame(animationFrameId);
                btnToggle.textContent = '▶️ Käynnistä tausta';
                btnToggle.classList.add('paused');
            } else {
                animate();
                btnToggle.textContent = '⏸️ Pysäytä tausta';
                btnToggle.classList.remove('paused');
            }
        });
    }

    const dataEl = document.getElementById('game-data');
    if (!dataEl) { 
        console.error("Pelin data-elementtiä ei löytynyt!"); 
        return; 
    }

    initialGameData = JSON.parse(dataEl.textContent || '{}');
    let gameDifficulty = initialGameData.difficulty || 'medium';

    function startGame() {
        const cards = [$('quiz-board-card'), $('quiz-card'), $('hangman-card'), $('memory-card')];
        cards.forEach(c => c?.classList.add('d-none'));

        if (initialGameData && initialGameData.levels) {
            if ($('quiz-board-card')) $('quiz-board-card').classList.remove('d-none');
            if ($('quiz-card')) $('quiz-card').classList.remove('d-none');
            resetGameWith({ difficulty: gameDifficulty, initialQuestions: initialGameData.levels });
        } else if (initialGameData && initialGameData.word) {
            if ($('hangman-card')) $('hangman-card').classList.remove('d-none');
            hmStartRound({ topic: initialGameData.topic, word: initialGameData.word });
        } else if (initialGameData && initialGameData.pairs) {
            if ($('memory-card')) $('memory-card').classList.remove('d-none');
            mmStartWithPairs(initialGameData.pairs);
        }
    }

    if (el.next) {
        el.next.addEventListener('click', () => {
            advanceAfterAnswer(lastAnswerWasCorrect);
        });
    }

    startGame();
});