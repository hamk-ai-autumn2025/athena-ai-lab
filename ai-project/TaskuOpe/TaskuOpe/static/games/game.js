/* =========================================================================
   PELIKOODI - KORJATTU VERSIO
   - AudioContext lazy initialization (luodaan vasta kun tarvitaan)
   - Loading overlay poistetaan kaikissa peleissä
   ========================================================================= */

// ==================== APUFUNKTIOT ====================
const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const cssVar = (name, fallback = '') => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

function getCookie(name) {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [key, value] = cookie.trim().split('=');
        if (key === name) return decodeURIComponent(value);
    }
    return null;
}

function shuffleArray(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
}

// ==================== SAAVUTETTAVUUS ====================
function getAccessibilitySettings() {
    return {
        reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
        highContrast: window.matchMedia('(prefers-contrast: high)').matches
    };
}

function announceToScreenReader(message) {
    const announcer = $('game-announcer');
    if (announcer) {
        announcer.textContent = message;
    }
}

// ==================== LOADING OVERLAY ====================
function removeLoadingOverlay() {
    const loadingOverlay = $('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.remove();
    }
}

// ==================== OVERLAY ====================
function showGameOverlay({ icon, title, message, showRestart = false, onRestart = null, countdown = 0 }) {
    removeLoadingOverlay();

    const overlay = document.createElement('div');
    overlay.className = 'game-overlay';
    overlay.innerHTML = `
        <div class="game-overlay-content">
            <div class="overlay-icon">${icon}</div>
            <h2 class="overlay-title">${title}</h2>
            <p class="overlay-message">${message}</p>
            ${countdown > 0 ? `<p class="overlay-timer">Uusi kierros alkaa: <strong id="countdown">${countdown}</strong>s</p>` : ''}
            <div class="overlay-buttons">
                ${showRestart ? '<button class="btn btn-primary" id="restartBtn">Pelaa uudelleen</button>' : ''}
                <a href="/" class="btn btn-outline-light">Takaisin etusivulle</a>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    announceToScreenReader(`${title}. ${message}`);

    if (showRestart && onRestart) {
        const btn = overlay.querySelector('#restartBtn');
        if (btn) btn.addEventListener('click', () => {
            overlay.remove();
            onRestart();
        });
    }

    if (countdown > 0) {
        let timeLeft = countdown;
        const countdownEl = overlay.querySelector('#countdown');
        const timer = setInterval(() => {
            timeLeft--;
            if (countdownEl) countdownEl.textContent = timeLeft;
            if (timeLeft <= 0) {
                clearInterval(timer);
                overlay.remove();
                if (onRestart) onRestart();
            }
        }, 1000);
    }
}

// ==================== ÄÄNET ====================
let audioContext = null;

function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

function playSound(type) {
    const a11y = getAccessibilitySettings();
    if (a11y.reducedMotion) return;

    try {
        const ctx = getAudioContext();
        
        if (ctx.state === 'suspended') {
            ctx.resume();
        }

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        const sounds = {
            correct: { freq: 523.25, duration: 0.2 },
            wrong: { freq: 130.81, duration: 0.3 },
            goal: { freq: 659.25, duration: 0.4 }
        };

        const sound = sounds[type] || sounds.correct;
        osc.frequency.setValueAtTime(sound.freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + sound.duration);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + sound.duration);
    } catch (error) {
        console.warn('Äänen soitto epäonnistui:', error);
    }
}

// ==================== PELIN SUORITUS ====================
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
            body: JSON.stringify({ score })
        });
        const data = await response.json();
        console.log('Suoritus lähetetty:', data);
    } catch (error) {
        console.error('Virhe suorituksen lähettämisessä:', error);
    }
}

// ==================== VISA-PELI ====================
let questions = [], qIndex = 0, score = 0, locked = false, position = 0;
let allCorrect = true, lastAnswerWasCorrect = null;
let timerId = null, qToken = 0;
let stops = [], gamePath = [];
let gameEnded = false;
let initialGameData = null;

const el = {
    score: $('score'),
    levelBadge: $('levelBadge'),
    question: $('question'),
    choices: $('choices'),
    feedback: $('feedback'),
    next: $('btnNext'),
    boardSvg: $('boardSvg'),
    hero: $('hero'),
    timer: $('timer'),
    restart: $('btnRestart')
};

const PATH_CONFIGS = {
    5: [
        {x:100,y:550},{x:250,y:600},{x:450,y:580},{x:700,y:520},{x:950,y:480},{x:1150,y:300}
    ],
    10: [
        {x:80,y:550},{x:180,y:620},{x:320,y:600},{x:420,y:500},{x:350,y:380},{x:500,y:280},
        {x:650,y:350},{x:800,y:280},{x:920,y:400},{x:1040,y:520},{x:1150,y:200}
    ],
    15: [
        {x:80,y:450},{x:150,y:580},{x:120,y:640},{x:280,y:650},{x:400,y:600},{x:500,y:640},
        {x:640,y:620},{x:720,y:540},{x:650,y:420},{x:550,y:320},{x:680,y:240},{x:820,y:280},
        {x:900,y:380},{x:980,y:500},{x:1080,y:560},{x:1150,y:200}
    ]
};

function setupGamePath(difficulty) {
    const lengths = { easy: 5, medium: 10, hard: 15 };
    const totalLen = lengths[difficulty] || 10;
    questions = questions.slice(0, totalLen);
    gamePath = Array(totalLen + 1).fill(0).map((_, i) => i);
    stops = PATH_CONFIGS[totalLen] || PATH_CONFIGS[10];
}

function generateGameBoard() {
    if (!el.boardSvg) return;
    el.boardSvg.innerHTML = '';

    for (let i = 0; i < stops.length - 1; i++) {
        const line = document.createElementNS(NS, 'line');
        line.setAttribute('x1', stops[i].x);
        line.setAttribute('y1', stops[i].y);
        line.setAttribute('x2', stops[i + 1].x);
        line.setAttribute('y2', stops[i + 1].y);
        line.setAttribute('class', 'path');
        el.boardSvg.appendChild(line);
    }

    stops.forEach((stop, i) => {
        const g = document.createElementNS(NS, 'g');
        const circle = document.createElementNS(NS, 'circle');
        circle.setAttribute('cx', stop.x);
        circle.setAttribute('cy', stop.y);
        circle.setAttribute('r', 28);
        circle.setAttribute('class', 'tile-circle');
        circle.setAttribute('data-index', i);

        const text = document.createElementNS(NS, 'text');
        text.setAttribute('x', stop.x);
        text.setAttribute('y', stop.y);
        text.setAttribute('class', i === stops.length - 1 ? 'goal-text' : 'tile-text');
        text.textContent = i === stops.length - 1 ? 'MAALI' : i;

        g.appendChild(circle);
        g.appendChild(text);
        el.boardSvg.appendChild(g);
    });
}

function positionHero(index, instant = false) {
    if (!el.hero || !stops[index]) return;

    const a11y = getAccessibilitySettings();
    const stop = stops[index];
    const offsetX = -24;
    const offsetY = -24;

    if (instant || a11y.reducedMotion) {
        el.hero.style.left = `${stop.x + offsetX}px`;
        el.hero.style.top = `${stop.y + offsetY}px`;
    } else {
        el.hero.style.transition = 'all 0.6s cubic-bezier(0.68, -0.55, 0.27, 1.55)';
        el.hero.style.left = `${stop.x + offsetX}px`;
        el.hero.style.top = `${stop.y + offsetY}px`;
    }

    updateBoardState(index);
}

function updateBoardState(currentIndex) {
    if (!el.boardSvg) return;

    const circles = el.boardSvg.querySelectorAll('.tile-circle');
    circles.forEach((circle, i) => {
        circle.classList.remove('visited', 'current');
        if (i < currentIndex) {
            circle.classList.add('visited');
        } else if (i === currentIndex) {
            circle.classList.add('current');
        }
    });
}

function clearTimer() {
    if (timerId) {
        clearInterval(timerId);
        timerId = null;
    }
}

function renderQuestion() {
    if (gameEnded || qIndex >= questions.length) return;

    if (qIndex === 0) {
        removeLoadingOverlay();
    }

    clearTimer();
    const lvl = questions[qIndex];
    const myToken = ++qToken;
    locked = false;

    if (el.question) el.question.textContent = lvl.question || '';
    if (el.levelBadge) el.levelBadge.textContent = `Kysymys ${qIndex + 1}/${questions.length}`;
    if (el.choices) el.choices.innerHTML = '';

    (lvl.choices || []).forEach((choice, i) => {
        const btn = document.createElement('button');
        btn.className = 'btn choice-btn';
        btn.textContent = choice;
        btn.onclick = () => handleAnswer(i, lvl.correct === i, myToken);
        if (el.choices) el.choices.appendChild(btn);
    });

    announceToScreenReader(`Kysymys ${qIndex + 1}: ${lvl.question}`);

    const startImage = $('start-image-container');
    if (qIndex === 0 && startImage) {
        startImage.style.opacity = '0';
        setTimeout(() => {
            startImage.style.visibility = 'hidden';
        }, 500);
    }
}

function handleAnswer(chosenIndex, isCorrect, token) {
    if (locked || token !== qToken || gameEnded) return;
    locked = true;

    const buttons = el.choices?.querySelectorAll('.choice-btn') || [];
    buttons.forEach((btn, i) => {
        btn.disabled = true;
        if (i === chosenIndex) {
            btn.classList.add(isCorrect ? 'correct' : 'wrong');
        }
    });

    playSound(isCorrect ? 'correct' : 'wrong');
    lastAnswerWasCorrect = isCorrect;

    if (isCorrect) {
        score++;
        if (el.score) el.score.textContent = score;
        announceToScreenReader('Oikein!');
    } else {
        allCorrect = false;
        announceToScreenReader('Väärin.');
    }

    setTimeout(() => advanceAfterAnswer(isCorrect), 1000);
}

function advanceAfterAnswer(wasCorrect) {
    if (gameEnded) return;

    if (wasCorrect) {
        position++;
        positionHero(position);
    }

    qIndex++;

    if (qIndex < questions.length) {
        setTimeout(() => renderQuestion(), 800);
    } else {
        setTimeout(() => endGame(), 1200);
    }
}

function endGame() {
    gameEnded = true;
    clearTimer();

    const percentage = Math.round((score / questions.length) * 100);

    if (position >= gamePath.length - 1) {
        playSound('goal');
        showGameOverlay({
            icon: '🎉',
            title: 'Onneksi olkoon!',
            message: `Pääsit maaliin!<br><br>Sait <strong>${score}/${questions.length}</strong> oikein (${percentage}%).`,
            showRestart: true,
            onRestart: () => resetGame()
        });
        submitGameCompletion(percentage);
    } else {
        showGameOverlay({
            icon: '😢',
            title: 'Peli ohi!',
            message: `Sait <strong>${score}/${questions.length}</strong> oikein (${percentage}%).<br><br>Yritä uudelleen!`,
            showRestart: true,
            onRestart: () => resetGame()
        });
        submitGameCompletion(percentage);
    }
}

function resetGame() {
    gameEnded = false;
    clearTimer();
    [qToken, allCorrect, locked, position, qIndex, score] = [0, true, false, 0, 0, 0];
    questions = initialGameData?.levels || [];

    if (el.score) el.score.textContent = '0';
    if (el.feedback) el.feedback.classList.add('d-none');
    if (el.restart) el.restart.classList.add('d-none');
    if (el.hero) el.hero.style.visibility = 'visible';

    const startImage = $('start-image-container');
    if (startImage) {
        startImage.style.opacity = '0';
        startImage.style.visibility = 'hidden';
    }

    const difficulty = initialGameData?.difficulty || 'medium';
    setupGamePath(difficulty);
    generateGameBoard();
    positionHero(0, true);
    renderQuestion();
}

// ==================== HIRSIPUU ====================
const HM_MAX_LIVES = 7;
const FI_ALPHABET = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ'];

let hmWordList = [];
let hmWordIndex = 0;
let hmWord = '';
let hmMasked = [];
let hmLivesLeft = HM_MAX_LIVES;
let hmGuessed = new Set();
let hmTopicStr = '';

function hmStartRound({ topic, word, words }) {
    gameEnded = false;
    hmTopicStr = topic;

    if (words && Array.isArray(words) && words.length > 0) {
        hmWordList = words;
        hmWord = String(hmWordList[hmWordIndex % hmWordList.length] || '').toUpperCase();
    } else if (word) {
        hmWordList = [word];
        hmWordIndex = 0;
        hmWord = String(word || '').toUpperCase();
    } else {
        console.error('Ei sanaa tai sanojen listaa!');
        return;
    }

    hmLivesLeft = HM_MAX_LIVES;
    hmGuessed = new Set();
    hmMasked = hmWord.split('');

    const livesEl = $('hmTriesLeft');
    if (livesEl) livesEl.textContent = hmLivesLeft;
    
    hmUpdateMasked();
    hmRenderLetters();
    hmRenderParts();

    removeLoadingOverlay();
    announceToScreenReader(`Hirsipuu aloitettu. Arvaa sana.`);
}

function hmUpdateMasked() {
    const display = hmMasked.map(c => (hmGuessed.has(c) ? c : '_')).join(' ');
    const maskedEl = $('hmMasked');
    if (maskedEl) maskedEl.textContent = display;
}

function hmRenderLetters() {
    const lettersEl = $('hmLetters');
    if (!lettersEl) return;

    lettersEl.innerHTML = '';
    FI_ALPHABET.forEach(letter => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-light';
        btn.textContent = letter;
        btn.disabled = hmGuessed.has(letter);
        btn.onclick = () => hmGuess(letter);
        lettersEl.appendChild(btn);
    });
}

function hmGuess(letter) {
    if (gameEnded || hmGuessed.has(letter)) return;

    hmGuessed.add(letter);

    if (hmWord.includes(letter)) {
        playSound('correct');
        announceToScreenReader(`Kirjain ${letter} on sanassa.`);
    } else {
        hmLivesLeft--;
        playSound('wrong');
        const livesEl = $('hmTriesLeft');
        if (livesEl) livesEl.textContent = hmLivesLeft;
        hmRenderParts();
        announceToScreenReader(`Kirjain ${letter} ei ole sanassa. ${hmLivesLeft} yritystä jäljellä.`);
    }

    hmUpdateMasked();
    hmRenderLetters();
    hmCheckEnd();
}

function hmCheckEnd() {
    const solved = hmMasked.every(c => hmGuessed.has(c));

    if (solved) {
        gameEnded = true;
        playSound('goal');
        showGameOverlay({
            icon: '🎉',
            title: 'Hienoa!',
            message: 'Arvasit sanan oikein!',
            showRestart: true,
            onRestart: () => {
                hmWordIndex++;
                hmStartRound({ topic: hmTopicStr, words: hmWordList });
            }
        });
        submitGameCompletion(100);
    } else if (hmLivesLeft <= 0) {
        gameEnded = true;
        showGameOverlay({
            icon: '😢',
            title: 'Hups!',
            message: `Oikea sana oli: <strong>${hmWord}</strong>`,
            showRestart: true,
            onRestart: () => {
                hmWordIndex++;
                hmStartRound({ topic: hmTopicStr, words: hmWordList });
            }
        });
        submitGameCompletion(0);
    }
}

function hmRenderParts() {
    const stickmanEl = $('hmStickman');
    if (!stickmanEl) return;

    const misses = HM_MAX_LIVES - hmLivesLeft;
    const stages = ['😊', '😐', '😟', '😧', '😨', '😱', '💀', '☠️'];
    stickmanEl.textContent = stages[misses] || '😊';
}

// ==================== MUISTIPELI (KORJATTU) ====================
let mmDeck = [];
let mmFirst = null;
let mmSecond = null;
let mmFoundCount = 0;
let mmTryCount = 0;
let mmLock = false;

function mmStartWithPairs(pairs) {
    gameEnded = false;
    [mmFoundCount, mmTryCount, mmFirst, mmSecond, mmLock] = [0, 0, null, null, false];

    const pairsEl = $('mmPairs');
    const totalEl = $('mmTotal');
    if (pairsEl) pairsEl.textContent = '0';
    if (totalEl) totalEl.textContent = pairs.length;

    const triesEl = $('mmTries');
    if (triesEl) triesEl.textContent = '0';

    mmDeck = [];

    (pairs || []).forEach((p, i) => {
        const values = Object.values(p);
        const text1 = String(values[0] || '');
        const text2 = String(values[1] || '');

        mmDeck.push({ text: text1, pairId: i, flipped: false, matched: false });
        mmDeck.push({ text: text2, pairId: i, flipped: false, matched: false });
    });

    shuffleArray(mmDeck);
    renderMmGrid();
    announceToScreenReader(`Muistipeli aloitettu. ${pairs.length} paria löydettävänä.`);

    removeLoadingOverlay();
}

function renderMmGrid() {
    const gridEl = $('mmGrid');
    if (!gridEl) return;

    gridEl.innerHTML = '';
    mmDeck.forEach((card, i) => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-light';
        btn.textContent = card.flipped || card.matched ? card.text : '❓';
        btn.disabled = card.matched;
        btn.onclick = () => mmFlip(i);
        
        // Lisää visuaaliset luokat
        if (card.matched) {
            btn.classList.add('mm-correct');
        }
        
        gridEl.appendChild(btn);
        card.btn = btn;
    });
}

function mmFlip(index) {
    if (mmLock || gameEnded) return;

    const card = mmDeck[index];
    if (!card || card.flipped || card.matched) return;

    card.flipped = true;
    card.btn.textContent = card.text;

    if (!mmFirst) {
        mmFirst = { card, index };
    } else if (!mmSecond && index !== mmFirst.index) {
        mmSecond = { card, index };
        mmTryCount++;
        const triesEl = $('mmTries');
        if (triesEl) triesEl.textContent = mmTryCount;
        mmLock = true;
        
        // Tarkista parit pienen viiveen jälkeen
        setTimeout(() => mmCheck(), 500);
    }
}

function mmCheck() {
    if (!mmFirst || !mmSecond) {
        mmLock = false;
        return;
    }

    const isMatch = mmFirst.card.pairId === mmSecond.card.pairId;

    if (isMatch) {
        // OIKEIN - Vihreä reuna ja lukitse kortit
        [mmFirst.card, mmSecond.card].forEach(c => {
            c.matched = true;
            c.btn.classList.add('mm-correct');
            c.btn.disabled = true;
        });

        mmFoundCount++;
        const pairsEl = $('mmPairs');
        if (pairsEl) pairsEl.textContent = mmFoundCount;

        playSound('correct');
        announceToScreenReader('Pari löytyi!');

        // Vapauta lukitus heti
        mmFirst = mmSecond = null;
        mmLock = false;

        // Tarkista voitto
        if (mmFoundCount === mmDeck.length / 2) {
            setTimeout(() => mmWin(), 500);
        }
    } else {
        // VÄÄRIN - Näytä punainen reuna hetken
        [mmFirst.card, mmSecond.card].forEach(c => {
            c.btn.classList.add('mm-wrong');
        });

        playSound('wrong');
        announceToScreenReader('Ei pari.');

        // Käännä kortit takaisin 1 sekunnin jälkeen
        setTimeout(() => {
            [mmFirst.card, mmSecond.card].forEach(c => {
                c.flipped = false;
                c.btn.textContent = '❓';
                c.btn.classList.remove('mm-wrong');
            });
            
            // Vapauta lukitus VASTA kun kortit on käännetty
            mmFirst = mmSecond = null;
            mmLock = false;
        }, 1000);
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

// ==================== TAUSTA-ANIMAATIO ====================
let canvas, ctx, stars = [];
let animationFrameId = null;
let isAnimationPaused = false;

function setupBackground() {
    const a11y = getAccessibilitySettings();

    if (a11y.reducedMotion) {
        isAnimationPaused = true;
        const btn = $('btnToggleBackground');
        if (btn) {
            btn.textContent = '⏸️ Animaatiot pois päältä';
            btn.disabled = true;
            btn.title = 'Reduced motion -asetus aktiivinen';
        }
        return;
    }

    canvas = $('space-canvas');
    if (!canvas) return;

    ctx = canvas.getContext('2d', { alpha: false });

    resize();
    window.addEventListener('resize', resize);
    animate();
}

function resize() {
    if (!canvas) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    stars = [];
    for (let i = 0; i < 100; i++) {
        stars.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            radius: Math.random() * 1.5 + 0.5,
            alpha: Math.random() * 0.5 + 0.5,
            speed: (Math.random() * 0.2 + 0.1) / 4
        });
    }
}

function animate() {
    if (isAnimationPaused || !ctx) return;

    ctx.fillStyle = cssVar('--bg-dark', '#0a0f2a');
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    stars.forEach(star => {
        star.y -= star.speed;
        if (star.y < 0) {
            star.y = canvas.height;
            star.x = Math.random() * canvas.width;
        }

        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${star.alpha})`;
        ctx.fill();
    });

    animationFrameId = requestAnimationFrame(animate);
}

// ==================== ALUSTUS ====================
document.addEventListener('DOMContentLoaded', () => {
    setupBackground();

    const btnToggle = $('btnToggleBackground');
    if (btnToggle) {
        btnToggle.addEventListener('click', () => {
            isAnimationPaused = !isAnimationPaused;
            if (isAnimationPaused) {
                if (animationFrameId) cancelAnimationFrame(animationFrameId);
                btnToggle.textContent = '▶️ Käynnistä tausta';
            } else {
                animate();
                btnToggle.textContent = '⏸️ Pysäytä tausta';
            }
        });
    }

    const dataEl = $('game-data');
    if (!dataEl) {
        console.error('Pelin data-elementtiä ei löytynyt!');
        removeLoadingOverlay();
        return;
    }

    try {
        initialGameData = JSON.parse(dataEl.textContent || '{}');
    } catch (error) {
        console.error('Virhe pelin datan parsimisessa:', error);
        removeLoadingOverlay();
        return;
    }

    const gameDifficulty = initialGameData.difficulty || 'medium';

    function startGame() {
        const cards = [$('quiz-board-card'), $('quiz-card'), $('hangman-card'), $('memory-card')];
        cards.forEach(c => c?.classList.add('d-none'));

        if (initialGameData?.levels) {
            $('quiz-board-card')?.classList.remove('d-none');
            $('quiz-card')?.classList.remove('d-none');
            questions = initialGameData.levels;
            setupGamePath(gameDifficulty);
            generateGameBoard();
            positionHero(0, true);
            renderQuestion();
        } else if (initialGameData?.words || initialGameData?.word) {
            $('hangman-card')?.classList.remove('d-none');
            hmStartRound({
                topic: initialGameData.topic,
                words: initialGameData.words,
                word: initialGameData.word
            });
        } else if (initialGameData?.pairs) {
            $('memory-card')?.classList.remove('d-none');
            mmStartWithPairs(initialGameData.pairs);
        } else {
            console.error('Tuntematon pelityyppi tai puuttuva data');
            removeLoadingOverlay();
        }
    }

    if (el.next) {
        el.next.addEventListener('click', () => {
            advanceAfterAnswer(lastAnswerWasCorrect);
        });
    }

    startGame();
});