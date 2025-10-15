/* =========================================================================
   PELIKOODI - SIIVOTTU VERSIO
   - Visa-peli, Mysteerisana(Hirsipuu) ja Muistipeli
   - Tausta-animaatiot
   - Saavutettavuus
   ========================================================================= */

// ==================== APUFUNKTIOT ====================
// Nopea ID-haku
const $ = (id) => document.getElementById(id);

// SVG-elementtien namespace
const NS = 'http://www.w3.org/2000/svg';

// CSS-muuttujan haku
const cssVar = (name, fallback = '') => 
  getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

// Cookie-arvon haku
function getCookie(name) {
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    const [key, value] = cookie.trim().split('=');
    if (key === name) return decodeURIComponent(value);
  }
  return null;
}

// Satunnaista järjestystä varten
function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}

// ==================== SAAVUTETTAVUUS ====================
// Tarkista käyttäjän saavutettavuusasetukset
function getAccessibilitySettings() {
  return {
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    highContrast: window.matchMedia('(prefers-contrast: high)').matches
  };
}

// Ilmoita ruudunlukijalle
function announceToScreenReader(message) {
  const announcer = $('game-announcer');
  if (announcer) {
    announcer.textContent = message;
  }
}

// ==================== LATAUSNÄKYMÄ ====================
// Poista latausoverlay
function removeLoadingOverlay() {
  const loadingOverlay = $('loading-overlay');
  if (loadingOverlay) {
    loadingOverlay.remove();
  }
}

// ==================== PELIN OVERLAY-NÄKYMÄT ====================
// Näytä overlay (lopetus, voitto, häviö)
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

  // Uudelleenpelaus-nappi
  if (showRestart && onRestart) {
    const btn = overlay.querySelector('#restartBtn');
    if (btn) {
      btn.addEventListener('click', () => {
        overlay.remove();
        onRestart();
      });
    }
  }

  // Automaattinen uudelleenaloitus ajastimella
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

// ==================== ÄÄNITEHOSTEET ====================
let audioContext = null;

// Luo tai palauta olemassa oleva AudioContext
function getAudioContext() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
  }
  return audioContext;
}

// Soita yksinkertainen ääni
function playSound(type) {
  const a11y = getAccessibilitySettings();
  if (a11y.reducedMotion) return; // Ei ääniä jos käyttäjä haluaa vähemmän liikettä

  try {
    const ctx = getAudioContext();
    
    if (ctx.state === 'suspended') {
      ctx.resume();
    }

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    // Äänityypit
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

// ==================== PELIN SUORITUS PALVELIMELLE ====================
// Lähetä pelin tulos palvelimelle
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
// Globaalit muuttujat visa-pelille
let questions = [];
let qIndex = 0;
let score = 0;
let locked = false;
let position = 0;
let allCorrect = true;
let lastAnswerWasCorrect = null;
let timerId = null;
let qToken = 0;
let timeLeft = 0;
let stops = [];
let gamePath = [];
let gameEnded = false;
let initialGameData = null;
let gameStarted = false;

// Ajastin-asetukset
const TIME_LIMIT_SECONDS = 20;

// DOM-elementit visa-pelille
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

// Pelilaudan polkukonfiguraatiot (5, 10, 15 kysymystä)
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

// Aseta pelin polku vaikeustason mukaan
function setupGamePath(difficulty) {
  const lengths = { easy: 5, medium: 10, hard: 15 };
  const totalLen = lengths[difficulty] || 10;
  questions = questions.slice(0, totalLen);
  gamePath = Array(totalLen + 1).fill(0).map((_, i) => i);
  stops = PATH_CONFIGS[totalLen] || PATH_CONFIGS[10];
}

// Generoi pelilauta SVG:nä
function generateGameBoard() {
  if (!el.boardSvg) return;
  el.boardSvg.innerHTML = '';

  // Piirrä polku
  for (let i = 0; i < stops.length - 1; i++) {
    const line = document.createElementNS(NS, 'line');
    line.setAttribute('x1', stops[i].x);
    line.setAttribute('y1', stops[i].y);
    line.setAttribute('x2', stops[i + 1].x);
    line.setAttribute('y2', stops[i + 1].y);
    line.setAttribute('class', 'path');
    el.boardSvg.appendChild(line);
  }

  // Piirrä ruudut
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

// Siirrä pelihahmo ruutuun
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

// Päivitä pelilaudan tila (vieraillut ruudut)
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

// ==================== AJASTIN ====================
// Tyhjennä ajastin
function clearTimer() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
}

// Käynnistä ajastin
function startTimer(tokenForThisQuestion) { 
  clearTimer();
  timeLeft = TIME_LIMIT_SECONDS;
  
  if (!el.timer) return;
  
  el.timer.textContent = `${timeLeft}s`;
  el.timer.classList.remove('critical', 'low');
  el.timer.style.color = '#ffffff';
  
  timerId = setInterval(() => {
    timeLeft--;
    
    if (el.timer) {
      el.timer.classList.remove('critical', 'low');
      
      // Värikoodaus: punainen < 6s, keltainen < 11s, valkoinen muuten
      if (timeLeft >= 0 && timeLeft <= 5) {
        el.timer.classList.add('critical');
        el.timer.style.color = '#dc3545';
      } else if (timeLeft >= 6 && timeLeft <= 10) {
        el.timer.classList.add('low');
        el.timer.style.color = '#ffc107';
      } else {
        el.timer.style.color = '#ffffff';
      }
      el.timer.textContent = `${timeLeft}s`;
    }
    
    if (timeLeft <= 0) {
      clearTimer();
      onTimeout(tokenForThisQuestion);
    }
  }, 1000);
}

// Aika loppui
function onTimeout(myToken) {
  if (myToken !== qToken || locked || gameEnded) return;
  
  locked = true;
  lastAnswerWasCorrect = false;
  playSound('wrong');
  
  announceToScreenReader('Aika loppui!');
  
  const buttons = el.choices?.querySelectorAll('.choice-btn') || [];
  buttons.forEach((btn) => {
    btn.disabled = true;
  });
  
  setTimeout(() => {
    advanceAfterAnswer(false);
  }, 1500);
}

// ==================== ALOITUSNÄKYMÄ ====================
// Näytä aloitusruutu
function showStartScreen() {
  if (!el.question || !el.choices) return;
  
  removeLoadingOverlay();

  // Piilota pelilauta ja näytä aloituskuva
  const boardCard = $('quiz-board-card');
  const startImage = $('start-image-container');

  if (boardCard) {
    boardCard.style.opacity = '1';
    boardCard.style.visibility = 'hidden';
  }
  if (startImage) {
    startImage.style.opacity = '1';
    startImage.style.visibility = 'visible';
  }
  
  el.question.textContent = 'Valmis aloittamaan?';
  el.choices.innerHTML = '';
  
  // Aloitusnappi
  const startBtn = document.createElement('button');
  startBtn.className = 'btn btn-primary btn-lg';
  startBtn.textContent = '🚀 Aloita peli';
  startBtn.style.fontSize = '1.5rem';
  startBtn.style.padding = '1rem 2rem';
  startBtn.onclick = () => {
    gameStarted = true;
    
    // Näytä pelilauta ja piilota aloituskuva
    if (boardCard) {
      boardCard.style.visibility = 'visible';
      boardCard.style.opacity = '1';
    }
    if (startImage) {
      startImage.style.opacity = '0';
      setTimeout(() => { startImage.style.visibility = 'hidden'; }, 500);
    }
    
    renderQuestion();
  };
  
  el.choices.appendChild(startBtn);
  
  if (el.levelBadge) el.levelBadge.textContent = '';
  if (el.timer) {
    el.timer.textContent = '—';
    el.timer.style.color = '#ffffff';
  }
}

// ==================== KYSYMYKSEN NÄYTTÄMINEN ====================
// Renderöi kysymys
function renderQuestion() {
  if (gameEnded || qIndex >= questions.length) return;

  if (qIndex === 0 && !gameStarted) {
    showStartScreen();
    return;
  }

  clearTimer();
  const lvl = questions[qIndex];
  const myToken = ++qToken;
  locked = false;

  if (el.question) el.question.textContent = lvl.question || '';
  if (el.levelBadge) el.levelBadge.textContent = `Kysymys ${qIndex + 1}/${questions.length}`;
  if (el.choices) el.choices.innerHTML = '';

  // Sekoita vastausvaihtoehdot
  const choices = lvl.choices || [];
  const shuffledChoices = [...choices];
  shuffleArray(shuffledChoices);

  // Luo vastausnapit
  shuffledChoices.forEach((choiceString) => {
    const btn = document.createElement('button');
    btn.className = 'btn choice-btn';
    btn.textContent = choiceString;

    // Tarkista oikea vastaus
    const correctIndex = lvl.correct;
    const correctAnswerString = lvl.choices[correctIndex];
    const isCorrect = (choiceString === correctAnswerString);
    
    btn.setAttribute('data-correct', isCorrect ? 'true' : 'false');
    
    btn.addEventListener('click', function() {
      handleAnswer(this, isCorrect, correctAnswerString, myToken);
    });
    
    if (el.choices) el.choices.appendChild(btn);
  });

  announceToScreenReader(`Kysymys ${qIndex + 1}: ${lvl.question}`);
  
  startTimer(myToken);
}

// ==================== VASTAUKSEN KÄSITTELY ====================
// Käsittele vastaus
function handleAnswer(clickedBtn, isCorrect, correctIndex, token) {
  if (locked || token !== qToken || gameEnded) {
    return;
  }

  try {
    locked = true;
    clearTimer();

    const buttons = el.choices?.querySelectorAll('.choice-btn') || [];

    // Merkitse oikea vastaus vihreäksi
    buttons.forEach((btn) => {
      btn.disabled = true;
      if (btn.getAttribute('data-correct') === 'true') {
        btn.classList.add('correct');
        btn.style.backgroundColor = '#28a745';
        btn.style.borderColor = '#28a745';
        btn.style.color = '#ffffff';
      }
    });

    // Merkitse väärä vastaus punaiseksi
    if (!isCorrect) {
      clickedBtn.classList.add('wrong');
      clickedBtn.style.backgroundColor = '#dc3545';
      clickedBtn.style.borderColor = '#dc3545';
      clickedBtn.style.color = '#ffffff';
    }

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

    setTimeout(() => advanceAfterAnswer(isCorrect), 1500);

  } catch (error) {
    console.error("Virhe vastauksen käsittelyssä:", error);
    locked = false;
  }
}

// Siirry seuraavaan kysymykseen
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

// ==================== PELIN LOPETUS ====================
// Apufunktio: valitse ikoni pistemäärän perusteella
function getResultIcon(percentage) {
  if (percentage === 100) return '🎉';
  if (percentage >= 90) return '🌟';
  if (percentage >= 70) return '😊';
  if (percentage >= 40) return '😐';
  if (percentage >= 30) return '🤔';
  return '😢';
}

// Apufunktio: valitse otsikko pistemäärän perusteella
function getResultTitle(percentage) {
  if (percentage === 100) return 'Täydellinen suoritus!';
  if (percentage >= 90) return 'Loistavaa!';
  if (percentage >= 70) return 'Hyvä yritys!';
  if (percentage >= 40) return 'Melkein!';
  if (percentage >= 30) return 'Kokeile uudelleen!';
  return 'Harjoittele lisää!';
}

// Lopeta peli ja näytä tulos
function endGame() {
  gameEnded = true;
  clearTimer();

  const percentage = Math.round((score / questions.length) * 100);
  const icon = getResultIcon(percentage);
  const title = position >= gamePath.length - 1 ? 'Onneksi olkoon!' : getResultTitle(percentage);

  // Peli katsotaan suoritetuksi jos pistemäärä on 80% tai enemmän
  const isCompleted = percentage >= 80;

  if (position >= gamePath.length - 1) {
    playSound('goal');
    showGameOverlay({
      icon: icon,
      title: title,
      message: `Pääsit maaliin!<br><br>Sait <strong>${score}/${questions.length}</strong> oikein (${percentage}%).${isCompleted ? '<br><br>✅ Tehtävä suoritettu!' : ''}`,
      showRestart: true,
      onRestart: () => resetGame()
    });
    submitGameCompletion(percentage);
  } else {
    showGameOverlay({
      icon: icon,
      title: title,
      message: `Sait <strong>${score}/${questions.length}</strong> oikein (${percentage}%).<br><br>${isCompleted ? '✅ Tehtävä suoritettu!<br><br>' : ''}Yritä uudelleen!`,
      showRestart: true,
      onRestart: () => resetGame()
    });
    submitGameCompletion(percentage);
  }
}

// Nollaa peli
function resetGame() {
  gameEnded = false;
  gameStarted = false;
  clearTimer();
  [qToken, allCorrect, locked, position, qIndex, score, timeLeft] = [0, true, false, 0, 0, 0, 0];
  questions = initialGameData?.levels || [];

  if (el.score) el.score.textContent = '0';
  if (el.timer) {
    el.timer.textContent = '—';
    el.timer.classList.remove('critical', 'low');
    el.timer.style.color = '#ffffff';
  }
  if (el.feedback) el.feedback.classList.add('d-none');
  if (el.restart) el.restart.classList.add('d-none');
  if (el.hero) el.hero.style.visibility = 'visible';

  // Nollaa näkymä
  const startImage = $('start-image-container');
  const boardCard = $('quiz-board-card');

  if (startImage) {
    startImage.style.opacity = '1';
    startImage.style.visibility = 'visible';
  }
  if (boardCard) {
    boardCard.style.opacity = '0';
    boardCard.style.visibility = 'hidden';
  }

  const difficulty = initialGameData?.difficulty || 'medium';
  setupGamePath(difficulty);
  generateGameBoard();
  positionHero(0, true);
  renderQuestion();
}

// ==================== MYSTEERISANA(HIRSIPUU) ====================
// Mysteerisanan vakiot
const HM_MAX_LIVES = 7;
const FI_ALPHABET = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ'];

// Mysteerisanan muuttujat
let hmWordList = [];
let hmWordIndex = 0;
let hmWord = '';
let hmMasked = [];
let hmLivesLeft = HM_MAX_LIVES;
let hmGuessed = new Set();
let hmTopicStr = '';

// Aloita Mysteerisana-kierros
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
  announceToScreenReader(`Mysteerisana aloitettu. Arvaa sana.`);
}

// Päivitä peitetty sana
function hmUpdateMasked() {
  const display = hmMasked.map(c => (hmGuessed.has(c) ? c : '_')).join(' ');
  const maskedEl = $('hmMasked');
  if (maskedEl) maskedEl.textContent = display;
}

// Renderöi kirjainnapit
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

// Arvaa kirjain
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

// Tarkista onko peli päättynyt
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
      title: 'Peli ohi!',
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

// Renderöi hirttopuun osat (emoji-versio)
function hmRenderParts() {
  const stickmanEl = $('hmStickman');
  if (!stickmanEl) return;

  const misses = HM_MAX_LIVES - hmLivesLeft;
  const stages = ['😊', '😐', '😟', '😧', '😨', '😱', '💀', '☠️'];
  stickmanEl.textContent = stages[misses] || '😊';
}

// ==================== MUISTIPELI ====================
// Muistipelin muuttujat
let mmDeck = [];
let mmFirst = null;
let mmSecond = null;
let mmFoundCount = 0;
let mmTryCount = 0;
let mmLock = false;

// Aloita muistipeli
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

  // Luo kortit pareista
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

// Renderöi muistipelin ruudukko
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
    
    if (card.matched) {
      btn.classList.add('mm-correct');
    }
    
    gridEl.appendChild(btn);
    card.btn = btn;
  });
}

// Käännä kortti
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
    
    setTimeout(() => mmCheck(), 500);
  }
}

// Tarkista parit
function mmCheck() {
  if (!mmFirst || !mmSecond) {
    mmLock = false;
    return;
  }

  const isMatch = mmFirst.card.pairId === mmSecond.card.pairId;

  if (isMatch) {
    // Oikein - vihreä ja lukitse
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

    mmFirst = mmSecond = null;
    mmLock = false;

    // Tarkista voitto
    if (mmFoundCount === mmDeck.length / 2) {
      setTimeout(() => mmWin(), 500);
    }
  } else {
    // Väärin - punainen reuna hetken
    [mmFirst.card, mmSecond.card].forEach(c => {
      c.btn.classList.add('mm-wrong');
    });

    playSound('wrong');
    announceToScreenReader('Ei pari.');

    // Käännä kortit takaisin
    setTimeout(() => {
      [mmFirst.card, mmSecond.card].forEach(c => {
        c.flipped = false;
        c.btn.textContent = '❓';
        c.btn.classList.remove('mm-wrong');
      });
      
      mmFirst = mmSecond = null;
      mmLock = false;
    }, 1000);
  }
}

// Muistipeli voitettu
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
// Animaation muuttujat
let canvas, ctx;
let stars = [];
let planets = [];
let asteroids = [];
let comets = [];
let animationFrameId = null;
let isAnimationPaused = false;

// Alusta tausta-animaatio
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
  
  // Kuuntele teeman vaihdoksia
  const observer = new MutationObserver(() => {
    if (!isAnimationPaused) {
      resize();
    }
  });
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-bs-theme']
  });
  
  animate();
}

// Hae nykyinen teema
function getTheme() {
  const theme = document.documentElement.getAttribute('data-bs-theme');
  return theme === 'light' ? 'light' : 'dark';
}

// Muuta canvas-kokoa ja generoi elementit uudelleen
function resize() {
  if (!canvas) return;

  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const isLight = getTheme() === 'light';
    
  // Generoi tähdet
  stars = [];
  for (let i = 0; i < 350; i++) {
    stars.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.5 + 0.5,
      alpha: Math.random() * 0.3 + 0.7,
      speed: (Math.random() * 0.2 + 0.1) / 8
    });
  }

  // Generoi planeetat
  planets = [];
  const planetCount = 3;
  for (let i = 0; i < planetCount; i++) {
    planets.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 30 + 20,
      color: isLight ? 
        `rgba(${100 + Math.random() * 100}, ${150 + Math.random() * 80}, ${200 + Math.random() * 55}, 0.75)` :
        `rgba(${100 + Math.random() * 155}, ${100 + Math.random() * 155}, ${200 + Math.random() * 55}, 0.6)`,
      speed: (Math.random() * 0.05 + 0.02) / 8,
      hasRing: Math.random() > 0.5
    });
  }
  
  // Generoi asteroidit
  asteroids = [];
  const asteroidCount = 8;
  for (let i = 0; i < asteroidCount; i++) {
    asteroids.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      size: Math.random() * 4 + 2,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 0.01,
      speed: (Math.random() * 0.15 + 0.08) / 8,
      color: isLight ? 'rgba(80, 80, 80, 0.5)' : 'rgba(180, 180, 180, 0.5)'
    });
  }
  
  // Generoi komeetat
  comets = [];
  const cometCount = 2;
  for (let i = 0; i < cometCount; i++) {
    comets.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height * 0.5,
      speed: (Math.random() * 0.8 + 0.5) / 2,
      angle: Math.random() * Math.PI / 4 + Math.PI / 6,
      tailLength: Math.random() * 60 + 40,
      color: isLight ? 'rgba(255, 255, 255, 0.7)' : 'rgba(255, 255, 255, 0.8)'
    });
  }
}

// Animaatiosilmukka
function animate() {
  if (isAnimationPaused || !ctx) return;

  const isLight = getTheme() === 'light';
  
  // Tausta
  ctx.fillStyle = isLight ? '#87CEEB' : '#0a1540';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Piirrä planeetat
  planets.forEach(planet => {
    planet.y -= planet.speed;
    if (planet.y + planet.radius < 0) {
      planet.y = canvas.height + planet.radius;
      planet.x = Math.random() * canvas.width;
    }

    ctx.beginPath();
    ctx.arc(planet.x, planet.y, planet.radius, 0, Math.PI * 2);
    ctx.fillStyle = planet.color;
    ctx.fill();
    
    // Renkaat
    if (planet.hasRing) {
      ctx.beginPath();
      ctx.ellipse(planet.x, planet.y, planet.radius * 1.5, planet.radius * 0.3, 0, 0, Math.PI * 2);
      ctx.strokeStyle = isLight ? 'rgba(100, 100, 150, 0.5)' : 'rgba(200, 200, 255, 0.3)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  });

  // Piirrä asteroidit
  asteroids.forEach(asteroid => {
    asteroid.y -= asteroid.speed;
    asteroid.rotation += asteroid.rotationSpeed;
    
    if (asteroid.y < -10) {
      asteroid.y = canvas.height + 10;
      asteroid.x = Math.random() * canvas.width;
    }

    ctx.save();
    ctx.translate(asteroid.x, asteroid.y);
    ctx.rotate(asteroid.rotation);
    
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (i / 6) * Math.PI * 2;
      const radius = asteroid.size * (0.8 + Math.random() * 0.4);
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = asteroid.color;
    ctx.fill();
    ctx.restore();
  });

  // Piirrä komeetat
  comets.forEach(comet => {
    const dx = Math.cos(comet.angle) * comet.speed;
    const dy = -Math.sin(comet.angle) * comet.speed;
    
    comet.x += dx;
    comet.y += dy;
    
    if (comet.x > canvas.width + 100 || comet.y < -100) {
      comet.x = -50;
      comet.y = Math.random() * canvas.height * 0.5;
    }

    // Pyrstö
    const gradient = ctx.createLinearGradient(
      comet.x, comet.y,
      comet.x - Math.cos(comet.angle) * comet.tailLength,
      comet.y + Math.sin(comet.angle) * comet.tailLength
    );
    gradient.addColorStop(0, comet.color);
    gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    
    ctx.beginPath();
    ctx.moveTo(comet.x, comet.y);
    ctx.lineTo(
      comet.x - Math.cos(comet.angle) * comet.tailLength,
      comet.y + Math.sin(comet.angle) * comet.tailLength
    );
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 3;
    ctx.stroke();
    
    // Pää
    ctx.beginPath();
    ctx.arc(comet.x, comet.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = isLight ? 'rgba(255, 255, 200, 0.9)' : '#ffffff';
    ctx.fill();
  });

  // Piirrä tähdet
  stars.forEach(star => {
    star.y -= star.speed;
    if (star.y < 0) {
      star.y = canvas.height;
      star.x = Math.random() * canvas.width;
    }

    ctx.beginPath();
    ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
    const starColor = isLight ? 
      `rgba(255, 255, 255, ${star.alpha * 0.9})` : 
      `rgba(255, 255, 255, ${star.alpha})`;
    ctx.fillStyle = starColor;
    ctx.fill();
  });

  animationFrameId = requestAnimationFrame(animate);
}

// ==================== ALUSTUS ====================
// Käynnistä peli kun sivu on ladattu
document.addEventListener('DOMContentLoaded', () => {
  setupBackground();

  // Tausta-animaation pysäytys/käynnistys -nappi
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

  // Lataa pelin data
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

  // Käynnistä oikea peli datan perusteella
  function startGame() {
    const cards = [$('quiz-board-card'), $('quiz-card'), $('hangman-card'), $('memory-card')];
    cards.forEach(c => c?.classList.add('d-none'));

    if (initialGameData?.levels) {
      // Visa-peli
      $('quiz-board-card')?.classList.remove('d-none');
      $('quiz-card')?.classList.remove('d-none');
      questions = initialGameData.levels;
      setupGamePath(gameDifficulty);
      generateGameBoard();
      positionHero(0, true);
      renderQuestion();
    } else if (initialGameData?.words || initialGameData?.word) {
      // Mysteerisana(Hirsipuu)
      $('hangman-card')?.classList.remove('d-none');
      hmStartRound({
        topic: initialGameData.topic,
        words: initialGameData.words,
        word: initialGameData.word
      });
    } else if (initialGameData?.pairs) {
      // Muistipeli
      $('memory-card')?.classList.remove('d-none');
      mmStartWithPairs(initialGameData.pairs);
    } else {
      console.error('Tuntematon pelityyppi tai puuttuva data');
      removeLoadingOverlay();
    }
  }

  startGame();
});