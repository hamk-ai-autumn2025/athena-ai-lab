/* =========================================================================
   Lautapeli
   ========================================================================= */

/* ------------------------------ PELIVALINTA -------------------------------- */
let GAME_MODE = null; // 'quiz' | 'hangman' | 'memory'

function showMode(mode) {
  GAME_MODE = mode;

  const quizBoardCard = document.getElementById('quiz-board-card');
  const quizCard = document.getElementById('quiz-card');
  const hangCard  = document.getElementById('hangman-card');
  const memCard   = document.getElementById('memory-card');
  const allCards = [quizBoardCard, quizCard, hangCard, memCard];
  
  allCards.forEach(c => c?.classList.add('d-none'));

  const acQuiz = document.getElementById('ai-controls-quiz');
  const acHangman = document.getElementById('ai-controls-hangman');
  const acMemory = document.getElementById('ai-controls-memory');
  [acQuiz, acHangman, acMemory].forEach(c => c?.classList.add('d-none'));

  if (!mode) {
    el.startImageContainer.classList.remove('hidden');
    quizBoardCard?.classList.remove('d-none');
    return;
  }
  
  el.startImageContainer.classList.add('hidden');

  if (mode === 'quiz') {
    quizBoardCard?.classList.remove('d-none');
    quizCard?.classList.remove('d-none');
    el.intro.classList.remove('d-none');
    el.game.classList.add('d-none');
    if(acQuiz) acQuiz.classList.remove('d-none');
  } else if (mode === 'hangman') {
    hangCard?.classList.remove('d-none');
    // Automaattinen demo-käynnistys poistettu
    if(acHangman) acHangman.classList.remove('d-none');
  } else if (mode === 'memory') {
    memCard?.classList.remove('d-none');
    // Automaattinen demo-käynnistys poistettu
    if(acMemory) acMemory.classList.remove('d-none');
  }
}

/* ------------------------------ ASETUKSET -------------------------------- */
const TIME_LIMIT_SECONDS = 20;
const BATCH_SIZE = 30;

/* ------------------------------- APUFUNKT -------------------------------- */
const $  = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const cssVar = (name, fallback) =>
  (getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback);

const schemaOk = (d) =>
  d && Array.isArray(d.levels) && d.levels.every(l =>
    typeof l.question === 'string' &&
    Array.isArray(l.choices) && l.choices.length >= 3 &&
    Number.isInteger(l.correct)
  );

function shuffleArray(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
}

function fiUpperLettersOnly(s){
  const allowed = 'ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ';
  let out = '';
  for (const ch of String(s || '').toUpperCase()){
    if (allowed.includes(ch)) out += ch;
  }
  return out;
}

/* ------------------------------- ÄÄNIMOOTTORI --------------------------- */
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

/* --------------------------------- TILA (VISA) --------------------------------- */
let questions = [], qIndex = 0, score = 0, locked = false, position = 0;
let allCorrect = true, lastAnswerWasCorrect = null, timeLeft = TIME_LIMIT_SECONDS;
let timerId = null, qToken = 0, stops = [], gamePath = [];

/* -------------- DOM-viitteet --------------- */
const el = {
  score: $('score'), levelBadge: $('levelBadge'), intro: $('intro'), game: $('game'),
  question: $('question'), choices: $('choices'), feedback: $('feedback'),
  restart: $('btnRestart'), next: $('btnNext'), boardSvg: $('boardSvg'),
  hero: $('hero'), startImageContainer: $('start-image-container'), timer: $('timer'),
  genStatus: $('genStatus'), btnGenerate: $('btnGenerate'),
  btnClearKey: $('btnClearKey'), apiKey: $('apiKey'), title: $('title'),
  difficulty: $('difficulty'), spaceBg: $('space-background'),
  btnStartMockQuiz: $('btnStartMockQuiz')
};

/* ------------------------------ PELIN POLKU (VISA) ------------------------------ */
const PATH_LENGTHS = { easy: 5, medium: 10, hard: 15 };
const predefinedPaths = {
  '5':  [ {x:150,y:420},{x:380,y:520},{x:630,y:500},{x:880,y:460},{x:1080,y:400},{x:1120,y:280} ],
  '10': [ {x:130,y:450},{x:260,y:560},{x:400,y:500},{x:360,y:370},{x:500,y:300},{x:640,y:360},{x:760,y:300},{x:900,y:360},{x:980,y:490},{x:1100,y:430},{x:1120,y:280} ],
  '15': [ {x:120,y:320},{x:240,y:420},{x:160,y:540},{x:310,y:600},{x:450,y:540},{x:560,y:600},{x:690,y:540},{x:600,y:420},{x:500,y:310},{x:650,y:230},{x:800,y:300},{x:730,y:420},{x:860,y:490},{x:980,y:430},{x:900,y:310},{x:1120,y:280} ]
};

function setupGamePathByDifficulty(difficulty) {
  const totalLen = PATH_LENGTHS[difficulty] || PATH_LENGTHS.medium;
  gamePath = Array.from({ length: totalLen }, () => ({ type: 'question' }));
}


/* ======================= LISÄTTY APUFUNKTIO TÄHTITAIVAALLE ======================== */
function createStarfieldSVG(width, height) {
    let content = `<rect width="${width}" height="${height}" fill="${cssVar('--bg-main', '#0a0f2a')}"/>`;
    for (let i = 0; i < 150; i++) { // Fewer stars for the board
        const r = Math.random() * 1.5;
        content += `<circle cx="${Math.random()*width}" cy="${Math.random()*height}" r="${r}" fill="white" opacity="${Math.random()*0.6 + 0.2}"/>`;
    }
    return content;
}

/* --------------------------- LAUDAN PIIRTÄMINEN (VISA) -------------------------- */
function drawBoardBackground() {
    if(!el.boardSvg) return;
    // VAIHDETTU: Käytetään uutta, yksinkertaisempaa tähtitaivasta pelilaudalla.
    el.boardSvg.innerHTML = createStarfieldSVG(1200, 675);
}

function generateGameBoard() {
  drawBoardBackground();
  const pathData = predefinedPaths[String(gamePath.length)];
  if (!pathData) return;
  stops = pathData;
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('class', 'path');
  path.setAttribute('d', `M${stops[0].x},${stops[0].y}` + stops.slice(1).map((p, i) => ` C${(stops[i].x + p.x) / 2},${stops[i].y} ${(stops[i].x + p.x) / 2},${p.y} ${p.x},${p.y}`).join(''));
  el.boardSvg.appendChild(path);
  for (let i = 0; i < gamePath.length; i++) {
    const g = document.createElementNS(NS, 'g');
    g.id = `tile-${i}`; g.classList.add('tile'); g.setAttribute('transform', `translate(${stops[i].x},${stops[i].y})`);
    g.innerHTML = `<circle class="tile-circle" r="35"></circle><text class="tile-text">${i+1}</text>`;
    el.boardSvg.appendChild(g);
  }
  const goalPoint = stops[gamePath.length];
  const goalGroup = document.createElementNS(NS,'g');
  goalGroup.id = `tile-${gamePath.length}`; goalGroup.setAttribute('transform', `translate(${goalPoint.x}, ${goalPoint.y}) scale(1.2)`);
  goalGroup.innerHTML = `<defs><filter id="goal-glow"><feGaussianBlur stdDeviation="7" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><g filter="url(#goal-glow)"><path d="M-30,10 C-30,-20 30,-20 30,10 Q0,25 -30,10 Z" fill="#c0c0c0" stroke="#546e7a" stroke-width="4"/><path d="M-15,-15 C-15,-30 15,-30 15,-15 Z" fill="${cssVar('--accent','#3ddcff')}" stroke="#546e7a" stroke-width="3"/></g><text y="-40" text-anchor="middle" class="goal-text">Maali</text>`;
  el.boardSvg.appendChild(goalGroup);
}

function positionHero(pos, instant = false) {
  if (!stops || !stops[pos]) return;
  const { x, y } = stops[pos];
  el.hero.style.transition = instant ? 'none' : 'left .6s ease-in-out, top .6s ease-in-out';
  el.hero.style.left = `${(x / 1200) * 100}%`;
  el.hero.style.top  = `${(y / 675) * 100}%`;
  document.querySelectorAll('.tile.current').forEach(t => t.classList.remove('current'));
  $(`tile-${pos}`)?.classList.add('current');
}

/* ------------------------------- AJASTIN (VISA) -------------------------------- */
function clearTimer() { if (timerId) clearInterval(timerId); timerId = null; }

function startTimer() {
  clearTimer(); timeLeft = TIME_LIMIT_SECONDS; el.timer.textContent = `${timeLeft}s`;
  const myToken = ++qToken;
  timerId = setInterval(() => {
    timeLeft--; el.timer.textContent = `${timeLeft}s`;
    el.timer.classList.toggle('critical', timeLeft <= 5);
    el.timer.classList.toggle('low', timeLeft > 5 && timeLeft <= 10);
    if (timeLeft <= 0) { clearTimer(); onTimeout(myToken); }
  }, 1000);
}

function onTimeout(myToken) {
  if (myToken !== qToken || locked) return;
  locked = true; lastAnswerWasCorrect = false; playSound('wrong');
  $(`tile-${position}`)?.classList.add('wrong');
  el.feedback.className = 'alert alert-warning mt-4'; el.feedback.textContent = 'Aika loppui!';
  el.feedback.classList.remove('d-none');
  if (isLastQuestion()) setTimeout(() => advanceAfterAnswer(false), 600);
  else { el.next.disabled = false; el.next.classList.remove('d-none'); }
}

/* ----------------------------- PELILOGIIKKA (VISA) ----------------------------- */
function currentQuestion() { return questions[qIndex] || null; }
function isLastQuestion() { return qIndex === questions.length - 1; }

function getShuffledChoices(level) {
  const arr = level.choices.map((text, i) => ({ text, isCorrect: i === level.correct }));
  shuffleArray(arr); return arr;
}

function renderQuestion() {
  const L = currentQuestion();
  if (!L) { endGame(allCorrect); return; }
  locked = false; el.feedback.classList.add('d-none');
  el.levelBadge.textContent = `Kysymys ${qIndex + 1}/${gamePath.length}`;
  el.question.textContent = L.question;
  el.choices.innerHTML = '';
  getShuffledChoices(L).forEach(opt => {
    const b = document.createElement('button');
    b.className = 'btn btn-outline-secondary choice-btn';
    b.textContent = opt.text; b.dataset.correct = opt.isCorrect;
    b.onclick = onChoose; el.choices.appendChild(b);
  });
  el.next.classList.add('d-none'); el.next.disabled = true;
  startTimer();
}

function onChoose(e) {
  if (locked) return;
  locked = true; clearTimer();
  const btn = e.currentTarget;
  const ok = btn.dataset.correct === 'true';
  lastAnswerWasCorrect = ok;
  playSound(ok ? 'correct' : 'wrong');
  el.choices.querySelectorAll('button').forEach(b => {
    b.disabled = true; if (b.dataset.correct === 'true') b.classList.add('correct');
  });
  if (!ok) btn.classList.add('wrong');
  const L = currentQuestion();
  el.feedback.className = ok ? 'alert alert-success mt-4' : 'alert alert-danger mt-4';
  el.feedback.textContent = L.explanation || (ok ? 'Oikein!' : 'Väärin!');
  el.feedback.classList.remove('d-none');
  $(`tile-${position}`)?.classList.add(ok ? 'correct' : 'wrong');
  if (isLastQuestion()) setTimeout(() => advanceAfterAnswer(ok), 800);
  else { el.next.disabled = false; el.next.classList.remove('d-none'); }
}

function advanceAfterAnswer(ok) {
  if (!ok) allCorrect = false;
  if (ok) { score++; el.score.textContent = String(score); }
  position++; qIndex++;
  if (position >= gamePath.length) { endGame(allCorrect); return; }
  positionHero(position);
  setTimeout(renderQuestion, 600);
}

function endGame(won) {
  clearTimer(); el.next.classList.add('d-none'); el.next.disabled = true;
  let msg = `Peli ohi! Sait ${score}/${gamePath.length} pistettä. `;
  if (won) { positionHero(gamePath.length); playSound('goal'); msg += "Hienoa, pääsit avaruusalukselle!"; }
  else msg += "Hyvä yritys!";
  el.feedback.className = 'alert alert-info mt-4'; el.feedback.textContent = msg;
  el.feedback.classList.remove('d-none');
  el.question.textContent = ''; el.choices.innerHTML = ''; el.restart.classList.remove('d-none');
}

function resetGameWith({ difficulty, initialQuestions }) {
  clearTimer(); [qToken, allCorrect, locked, position, qIndex, score] = [0, true, false, 0, 0, 0];
  const need = PATH_LENGTHS[difficulty] || PATH_LENGTHS.medium;
  questions = (initialQuestions || []).slice(0, need);
  el.score.textContent = '0'; el.intro.classList.add('d-none');
  el.game.classList.remove('d-none'); el.feedback.classList.add('d-none');
  el.restart.classList.add('d-none');
  setupGamePathByDifficulty(difficulty); generateGameBoard();
  el.hero.style.visibility = 'visible';
  positionHero(0, true); renderQuestion();
}

/* ------------------------------- API-HAUT (VISA) ------------------------------- */
let cachedQuestions = null; // Tallenna kysymykset uudelleenpeluuta varten

async function fetchQuestionBatch({ key, title, difficulty }) {
    const userPrompt = `
Rooli: Toimi suomalaisena opettajana ja tietokirjailijana.

Tehtävä: Laadi ${BATCH_SIZE} laadukasta monivalintakysymystä.
Aihe: "${title}"
Vaikeustaso: ${difficulty}

Säännöt:
1. **Faktojen on oltava oikein.** Älä arvaa tietoja.
2. Kysymysten on oltava **selkeitä ja yksiselitteisiä**.
3. Vastausvaihtoehdoista vain **yksi saa olla oikein**.
4. Varmista, että JSON-objektin \`correct\`-indeksi vastaa oikean vastauksen paikkaa \`choices\`-taulukossa.

ESIMERKKI (Suomen eläimet):
{
  "levels": [
    {
      "question": "Mikä on Suomen suurin petoeläin?",
      "choices": ["Karhu", "Susi", "Ilves", "Ahma"],
      "correct": 0,
      "explanation": "Karhu on Suomen suurin petoeläin."
    }
  ]
}

Vastauksen muoto:
- Palauta VAIN JSON-objekti.
- Kaikki tekstit suomeksi.
- Noudata tarkasti tätä rakennetta: \`{"levels":[{"question":"...","choices":["..."],"correct":0,"explanation":"..."}]}\`
`;
    
    const resp = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST", headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model: "gpt-4.1", response_format: { type: "json_object" }, messages: [{ role: "user", content: userPrompt }] })
    });
    if (!resp.ok) { const e = await resp.json().catch(()=>({})); throw new Error(`API virhe ${resp.status}: ${e?.error?.message || 'Tuntematon virhe'}`); }
    const data = await resp.json();
    const parsed = JSON.parse(data.choices[0].message.content);
    if (!schemaOk(parsed)) throw new Error("Tekoälyn data oli virheellistä.");
    
    cachedQuestions = parsed.levels; // Tallenna kysymykset
    return parsed.levels;
}

/* ------------------------------ MOCK-DATA (VISA) ------------------------------- */
const MOCK_LEVELS = [
  { question: "Mikä planeetta on lähimpänä Aurinkoa?", choices: ["Venus", "Maa", "Merkurius"], correct: 2, explanation: "Merkurius on aurinkokunnan pienin ja Aurinkoa lähin planeetta." },
  { question: "Mikä on Jupiterin kuuluisa 'punainen pilkku'?", choices: ["Tulivuori", "Valtava myrsky", "Jäätikkö"], correct: 1, explanation: "Jupiterin Suuri punainen pilkku on jättimäinen, vuosisatoja raivonnut myrsky." },
  { question: "Minkä niminen on oma kotigalaksimme?", choices: ["Andromeda", "Linnunrata", "Kolmion galaksi"], correct: 1, explanation: "Aurinkokuntamme sijaitsee Linnunrata-nimisessä kierteisgalaksissa." },
  { question: "Mikä voima pitää planeetat kiertoradoillaan Auringon ympäri?", choices: ["Magnetismi", "Painovoima", "Keskipakoisvoima"], correct: 1, explanation: "Auringon valtava massa aiheuttaa painovoiman, joka pitää planeetat kiertoradoillaan." },
  { question: "Mistä tähdet pääasiassa koostuvat?", choices: ["Kivenlohkareista", "Kuumasta plasmasta", "Jäätyneistä kaasuista"], correct: 1, explanation: "Tähdet ovat pääasiassa vety- ja heliumplasmaa, jotka fuusioituvat vapauttaen energiaa." },
  { question: "Mikä on aurinkokuntamme suurin planeetta?", choices: ["Saturnus", "Jupiter", "Neptunus"], correct: 1, explanation: "Jupiter on massaltaan ja halkaisijaltaan aurinkokuntamme suurin planeetta." },
  { question: "Minkä planeetan vuorokausi on lyhin?", choices: ["Maa", "Jupiter", "Mars"], correct: 1, explanation: "Jupiter pyörii nopeimmin, ja sen vuorokausi on vain noin 10 tuntia." },
  { question: "Kuinka kauan valolta kestää matkustaa Auringosta Maahan?", choices: ["Noin 8 sekuntia", "Noin 8 minuuttia", "Noin 8 tuntia"], correct: 1, explanation: "Valon matka Auringosta Maahan kestää keskimäärin noin 8 minuuttia ja 20 sekuntia." },
  { question: "Mikä näistä luokitellaan kääpiöplaneetaksi?", choices: ["Mars", "Kuu", "Pluto"], correct: 2, explanation: "Pluto luokiteltiin kääpiöplaneetaksi vuonna 2006, koska se ei ole 'puhdistanut' omaa kiertorataansa." },
  { question: "Mitä musta aukko on?", choices: ["Tyhjä kohta avaruudessa", "Alue, josta edes valo ei pääse pakoon", "Erittäin tiheä tähti"], correct: 1, explanation: "Musta aukko on aika-avaruuden alue, jonka painovoima on niin voimakas, ettei mikään, edes valo, pääse sieltä pakoon." },
  { question: "Mikä on maailmankaikkeuden yleisin alkuaine?", choices: ["Happi", "Vety", "Hiili"], correct: 1, explanation: "Vety on ylivoimaisesti yleisin alkuaine maailmankaikkeudessa." },
  { question: "Mitä supernova tarkoittaa?", choices: ["Uuden tähden syntyä", "Tähden räjähdysmäistä kuolemaa", "Planeetan hajoamista"], correct: 1, explanation: "Supernova on massiivisen tähden elinkaaren loppuvaiheessa tapahtuva valtava räjähdys." },
  { question: "Mitä komeetat ovat?", choices: ["Palavia asteroideja", "Likaisia jääpalloja", "Kaukaisia tähtiä"], correct: 1, explanation: "Komeetat ovat pääasiassa jäästä, kivestä ja pölystä koostuvia kappaleita, joille kasvaa pyrstö Auringon lähellä." },
  { question: "Mikä on valovuosi?", choices: ["Ajan yksikkö", "Matka, jonka valo kulkee vuodessa", "Energian yksikkö"], correct: 1, explanation: "Valovuosi on etäisyyden mittayksikkö, ei ajan." },
  { question: "Mikä on ISS?", choices: ["Kaukainen komeetta", "Kansainvälinen avaruusasema", "Suuri asteroidi"], correct: 1, explanation: "ISS on Kansainvälinen avaruusasema (International Space Station), joka kiertää Maata." }
];

/* ========================= HIRSI PUU ========================= */
const HM_MAX_LIVES = 7;
const FI_ALPHABET = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ'];
let hmWord = '', hmMasked = [], hmLivesLeft = HM_MAX_LIVES, hmGuessed = new Set(), hmTopicStr = 'Avaruus';
const hmEl = { lives: $('hmLives'), topic: $('hmTopic'), masked: $('hmMasked'), letters: $('hmLetters'), feedback: $('hmFeedback'), restart: $('hmRestart'),};

// game.js

async function hmStartAI({key, topic}){
    const prompt = `Toimi suomenkielisenä opettajana. Anna YKSI suomenkielinen sana annetusta aiheesta hirsipuupeliin. Säännöt: Vain kirjaimia (A-Ö), 5-12 merkkiä pitkä, yleiskielinen. Palauta VAIN JSON-muodossa: {"topic":"aihe","word":"sana"}. Aihe: ${topic}`;
    
    const resp = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST", headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model: "gpt-4.1", response_format: { type: "json_object" }, messages: [{ role: "user", content: prompt }] })
    });
    if (!resp.ok) { const e = await resp.json().catch(()=>({})); throw new Error(`OpenAI-virhe ${resp.status}: ${e?.error?.message || 'Tuntematon virhe'}`); }
    const data = await resp.json();
    const parsed = JSON.parse(data.choices[0].message.content);
    const safeWord = fiUpperLettersOnly(parsed.word || '');
    if (!safeWord || safeWord.length < 4) throw new Error("AI:n antama sana oli kelvoton.");
    hmStartRound({ topic: parsed.topic || topic, word: safeWord });
}

function hmStartDemo(){ hmStartRound({ topic: 'Avaruus', word: 'GALAKSI' }); }

function hmStartRound({topic, word}){
  hmTopicStr = topic; hmWord = word; hmLivesLeft = HM_MAX_LIVES; hmGuessed.clear();
  hmMasked = Array.from(hmWord, () => '_');
  hmEl.topic.textContent = hmTopicStr; hmEl.lives.textContent = String(hmLivesLeft);
  hmEl.masked.textContent = hmMasked.join(' ');
  hmEl.feedback.classList.add('d-none');
  hmEl.letters.innerHTML = '';
  FI_ALPHABET.forEach(letter => {
    const b = document.createElement('button');
    b.className = 'btn btn-outline-secondary btn-sm'; b.textContent = letter;
    b.onclick = () => hmGuess(letter, b);
    hmEl.letters.appendChild(b);
  });
  hmRenderParts();
}

function hmGuess(letter, btn){
  if (hmLivesLeft <= 0 || hmMasked.join('') === hmWord || hmGuessed.has(letter)) return;
  hmGuessed.add(letter);
  const hits = hmWord.split('').reduce((acc, ch, i) => (ch === letter ? [...acc, i] : acc), []);
  if (hits.length) {
    playSound('correct'); hits.forEach(i => hmMasked[i] = letter);
    hmEl.masked.textContent = hmMasked.join(' ');
    btn.className += ' correct'; btn.disabled = true;
    if (hmMasked.join('') === hmWord) hmLoseWin(true);
  } else {
    playSound('wrong'); hmLivesLeft--; hmEl.lives.textContent = String(hmLivesLeft);
    btn.className += ' wrong'; btn.disabled = true;
    hmRenderParts();
    if (hmLivesLeft <= 0) hmLoseWin(false);
  }
}

function hmLoseWin(won){
  hmEl.feedback.className = `alert mt-4 alert-${won ? 'success' : 'danger'}`;
  hmEl.feedback.textContent = won ? 'Hienoa! Arvasit sanan.' : `Hups! Sana oli: ${hmWord}`;
  hmEl.feedback.classList.remove('d-none');
}

function hmRenderParts(){
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

/* ======================== MUISTIPELI ======================== */
const mmEl = { grid:$('mmGrid'), found:$('mmFound'), tries:$('mmTries'), feedback:$('mmFeedback'), restart:$('mmRestart') };
let mmDeck = [], mmFirst = null, mmSecond = null, mmFoundCount = 0, mmTryCount = 0, mmLock = false;
const MM_DEMO_PAIRS = [ {q:'Pluto',a:'kääpiöplaneetta'}, {q:'Jupiter',a:'kaasujättiläinen'}, {q:'Mars',a:'punainen planeetta'}, {q:'Andromeda',a:'naapurigalaksi'}, {q:'Galaksi',a:'tähtijärjestelmä'}, {q:'Aurinko',a:'tähti'}, {q:'Komeetta',a:'"likainen lumipallo"'}, {q:'Saturnus',a:'renkaat'}, {q:'Merkurius',a:'lähimpänä Aurinkoa'}, {q:'Neptunus',a:'sininen planeetta'} ];

// Apufunktio laskutoimituksen normalisointiin
function normalizeQuestion(q) {
    const str = String(q).trim();
    // Jos on yhteenlasku, järjestä numerot
    const addMatch = str.match(/^(\d+)\s*\+\s*(\d+)$/);
    if (addMatch) {
        const [a, b] = [parseInt(addMatch[1]), parseInt(addMatch[2])].sort((x,y) => x-y);
        return `${a}+${b}`;
    }
    // Jos on kertolasku, järjestä numerot
    const mulMatch = str.match(/^(\d+)\s*[×x*]\s*(\d+)$/);
    if (mulMatch) {
        const [a, b] = [parseInt(mulMatch[1]), parseInt(mulMatch[2])].sort((x,y) => x-y);
        return `${a}×${b}`;
    }
    return str;
}

async function mmStartAI({key, topic}){
    const prompt = `Toimi suomenkielisenä opettajana. Laadi TÄSMÄLLEEN 10 muistipelikorttiparia aiheesta.
AIHE: ${topic}

KRIITTISET SÄÄNNÖT:
1. **JOKAISEN VASTAUKSEN ON OLTAVA UNIIKKI** - Ei kahta samaa vastausta! 
   Esimerkki pluslaskuista: Jos vastauksia ovat 5,7,9,11,13,15,17,19,21,23 → KAIKKI ERILAISIA!
2. **JOKAISEN KYSYMYKSEN ON OLTAVA UNIIKKI** - Älä käytä peilikuvia (2+7 ja 7+2 ovat sama asia).
3. **KÄYTÄ LAAJAA NUMEROVALIKOIMAA** - Älä rajoitu 1-10 väliin. Käytä esim. 2+3=5, 4+8=12, 6+9=15, 7+11=18, jne.
4. Tekstit lyhyitä (max 15 merkkiä).

ESIMERKKI HYVÄSTÄ PLUSLASKUPAKETISTA:
{"pairs":[
  {"q":"2+3","a":"5"},
  {"q":"4+8","a":"12"},
  {"q":"6+9","a":"15"},
  {"q":"7+11","a":"18"},
  {"q":"5+8","a":"13"},
  {"q":"9+7","a":"16"},
  {"q":"3+11","a":"14"},
  {"q":"8+9","a":"17"},
  {"q":"4+15","a":"19"},
  {"q":"6+14","a":"20"}
]}

Huomaa: Kaikki vastaukset (5,12,15,18,13,16,14,17,19,20) ovat erilaisia!

Palauta VAIN JSON: {"pairs":[{"q":"...","a":"..."}, ... (10 kpl)]}.`;

    const maxRetries = 7;
    for (let i = 0; i < maxRetries; i++) {
        const resp = await fetch("https://api.openai.com/v1/chat/completions", {
            method: "POST", headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
            body: JSON.stringify({ 
                model: "gpt-4o", 
                temperature: 0.8,
                response_format: { type: "json_object" }, 
                messages: [{ role: "user", content: prompt }] 
            })
        });

        if (!resp.ok){ const e = await resp.json().catch(()=>({})); throw new Error(`OpenAI-virhe ${resp.status}: ${e?.error?.message || 'Tuntematon virhe'}`); }
        
        const data = await resp.json();
        const parsed = JSON.parse(data.choices[0].message.content);
        
        let rawPairs = (parsed.pairs || []).filter(p => p.q && p.a).slice(0, 10);

        if (rawPairs.length === 10) {
            const pairs = rawPairs.map(p => ({
                q: String(p.q).trim(),
                a: String(p.a).trim()
            }));

            // Tarkista vastausten uniikkius
            const answers = pairs.map(p => p.a);
            const uniqueAnswers = new Set(answers);

            // Tarkista kysymysten uniikkius (normalisoituna)
            const normalizedQuestions = pairs.map(p => normalizeQuestion(p.q));
            const uniqueQuestions = new Set(normalizedQuestions);

            // Hyväksy vain jos SEKÄ vastaukset ETTÄ kysymykset ovat uniikkeja
            if (answers.length === uniqueAnswers.size && normalizedQuestions.length === uniqueQuestions.size) {
                mmStartWithPairs(pairs);
                return; 
            }
        }
    }

    throw new Error("Tekoäly ei onnistunut luomaan uniikkeja pareja 7 yrityksellä. Yritä uudelleen tai vaihda aihetta.");
}

function mmStartDemo(){ mmStartWithPairs(MM_DEMO_PAIRS); }

function mmStartWithPairs(pairs){
  [mmFoundCount, mmTryCount, mmFirst, mmSecond, mmLock] = [0, 0, null, null, false];
  mmEl.found.textContent = '0'; mmEl.tries.textContent = '0';
  mmEl.feedback.classList.add('d-none');
  mmDeck = [];
  pairs.forEach((p, i) => {
    mmDeck.push({ text: p.q, pairId: i, flipped: false, matched: false });
    mmDeck.push({ text: p.a, pairId: i, flipped: false, matched: false });
  });
  shuffleArray(mmDeck);
  renderMmGrid();
}

function renderMmGrid(){
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

function mmFlip(card, btn){
  if (mmLock || card.flipped || card.matched) return;
  card.flipped = true; btn.textContent = card.text;
  if (!mmFirst) { mmFirst = {card, btn}; return; }
  mmSecond = {card, btn};
  mmCheck();
}

function mmCheck(){
  mmLock = true; mmTryCount++; mmEl.tries.textContent = String(mmTryCount);
  const samePair = mmFirst.card.pairId === mmSecond.card.pairId;
  if (samePair) {
    playSound('correct');
    [mmFirst, mmSecond].forEach(c => { c.card.matched = true; c.btn.classList.add('correct'); });
    mmFoundCount++; mmEl.found.textContent = String(mmFoundCount);
    if (mmFoundCount === 10) mmWin();
    setTimeout(() => { mmFirst = mmSecond = null; mmLock = false; }, 300);
  } else {
    playSound('wrong');
    setTimeout(() => {
      [mmFirst, mmSecond].forEach(c => { c.card.flipped = false; c.btn.textContent = '❓'; });
      mmFirst = mmSecond = null; mmLock = false;
    }, 800);
  }
}

function mmWin(){
  mmEl.feedback.className = 'alert alert-success mt-4';
  mmEl.feedback.textContent = 'Kaikki parit löydetty! ';
  mmEl.feedback.classList.remove('d-none');
}

/* ======================== DYNAAMINEN CANVAS-TAUSTA (VERSIO 7 - Pysäytys korjattu) ======================== */
let animationFrameId = null;
let isAnimationPaused = false;

// Siirretään animaation piirtämiseen liittyvät muuttujat laajempaan näkyvyyteen
let canvas, ctx, stars = [], planets = [], asteroids = [], comets = [];
let width, height;
let planetColors, createAsteroidShape, createComet;

function setupBackground() {
    canvas = document.getElementById('space-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');

    planetColors = [
        { main: "#d9534f" }, { main: "#ffc107" }, { main: "#4fc3f7" },
        { main: "#6fde6f" }, { main: "#f39c12" }, { main: "#9c27b0" }
    ];

    createAsteroidShape = (radius) => {
        const shape = [];
        const segments = Math.floor(Math.random() * 5) + 7;
        for (let i = 0; i < segments; i++) {
            const angle = (i / segments) * Math.PI * 2;
            const dist = radius * (Math.random() * 0.4 + 0.8);
            shape.push({ x: Math.cos(angle) * dist, y: Math.sin(angle) * dist });
        }
        return shape;
    };

    createComet = () => {
        comets.push({
            x: Math.random() * width, y: 0, radius: Math.random() * 2 + 1,
            speed: { x: ((Math.random() - 0.5) * 8) / 3, y: (Math.random() * 6 + 4) / 3 },
            tail: [], tailLength: 20
        });
    };
    
    window.addEventListener('resize', resize);
    resize(); // Asetetaan elementit kerran
    animate(); // Käynnistetään animaatio
}

function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    
    stars = [];
    for (let i = 0; i < 200; i++) { stars.push({ x: Math.random() * width, y: Math.random() * height, radius: Math.random() * 1.5 + 0.5, alpha: Math.random(), speed: (Math.random() * 0.2 + 0.1) / 4 }); }
    planets = [];
    for (let i = 0; i < 5; i++) { const colorSet = planetColors[i % planetColors.length]; planets.push({ x: Math.random() * width, y: Math.random() * height, radius: Math.random() * 30 + 20, speed: (Math.random() * 0.05 + 0.02) / 4, mainColor: colorSet.main, hasRing: Math.random() > 0.6 }); }
    asteroids = [];
    for (let i = 0; i < 10; i++) { const radius = Math.random() * 15 + 5; asteroids.push({ x: Math.random() * width, y: Math.random() * height, shape: createAsteroidShape(radius), rotation: Math.random() * Math.PI * 2, rotationSpeed: (Math.random() - 0.5) * 0.005, speed: (Math.random() * 0.1 + 0.05) / 4, color: `hsl(0, 0%, ${Math.floor(Math.random() * 20) + 30}%)`, borderColor: `hsl(0, 0%, ${Math.floor(Math.random() * 10) + 20}%)` }); }
}

function animate() {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--bg-main').trim();
    ctx.fillRect(0, 0, width, height);

    const galaxyGradient = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, Math.max(width, height) / 2);
    galaxyGradient.addColorStop(0, 'rgba(255, 255, 255, 0.08)');
    galaxyGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = galaxyGradient;
    ctx.fillRect(0, 0, width, height);

    asteroids.forEach(a => { a.y -= a.speed; a.rotation += a.rotationSpeed; if (a.y < -30) { a.y = height + 30; a.x = Math.random() * width; } ctx.save(); ctx.translate(a.x, a.y); ctx.rotate(a.rotation); ctx.beginPath(); ctx.moveTo(a.shape[0].x, a.shape[0].y); a.shape.forEach(p => ctx.lineTo(p.x, p.y)); ctx.closePath(); ctx.fillStyle = a.color; ctx.strokeStyle = a.borderColor; ctx.lineWidth = 2; ctx.fill(); ctx.stroke(); ctx.restore(); });
    planets.forEach(p => { p.y -= p.speed; if (p.y < -p.radius * 2) { p.y = height + p.radius * 2; p.x = Math.random() * width; } ctx.fillStyle = p.mainColor; ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill(); const hg = ctx.createRadialGradient(p.x - p.radius * 0.3, p.y - p.radius * 0.4, 0, p.x, p.y, p.radius * 1.2); hg.addColorStop(0, 'rgba(255, 255, 255, 0.3)'); hg.addColorStop(1, 'rgba(255, 255, 255, 0)'); ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2); ctx.fill(); if (p.hasRing) { ctx.strokeStyle = `rgba(255, 255, 255, 0.4)`; ctx.lineWidth = p.radius * 0.1; ctx.beginPath(); ctx.ellipse(p.x, p.y, p.radius * 1.5, p.radius * 0.4, Math.PI / 8, 0, Math.PI * 2); ctx.stroke(); } });
    stars.forEach(star => { star.y -= star.speed; if (star.y < 0) { star.y = height; star.x = Math.random() * width; } ctx.beginPath(); ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2); ctx.fillStyle = `rgba(255, 255, 255, ${star.alpha})`; ctx.fill(); });
    if (Math.random() > 0.998 && comets.length < 3) { createComet(); }
    comets.forEach((comet, index) => { comet.x += comet.speed.x; comet.y += comet.speed.y; comet.tail.push({ x: comet.x, y: comet.y, radius: comet.radius }); if (comet.tail.length > comet.tailLength) { comet.tail.shift(); } comet.tail.forEach((t, i) => { const alpha = (i / comet.tailLength) * 0.5; ctx.beginPath(); ctx.arc(t.x, t.y, t.radius * (i / comet.tailLength), 0, Math.PI * 2); ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`; ctx.fill(); }); ctx.beginPath(); ctx.arc(comet.x, comet.y, comet.radius, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'; ctx.fill(); if (comet.x < -10 || comet.x > width + 10 || comet.y > height + 10) { comets.splice(index, 1); } });

    // Pyydetään seuraavaa animaatiokehystä ja tallennetaan sen ID
    animationFrameId = requestAnimationFrame(animate);
}

/* ------------------------------- INIT JA TAPAHTUMAT ----------------------------------- */
function startMockQuiz() {
  showMode('quiz');
  resetGameWith({
    difficulty: el.difficulty.value || 'medium',
    initialQuestions: MOCK_LEVELS
  });
}

function restartQuiz() {
    if (cachedQuestions) {
        // Käynnistä peli uudelleen samoilla kysymyksillä
        resetGameWith({
            difficulty: el.difficulty.value || 'medium',
            initialQuestions: cachedQuestions
        });
    } else {
        // Jos ei ole cachea, käytä mock-dataa
        startMockQuiz();
    }
}

async function handleGenerateGame() {
    const key = el.apiKey.value.trim();
    if (!key) { el.genStatus.textContent = "Syötä API-avain."; return; }
    if (!GAME_MODE) { el.genStatus.textContent = "Valitse ensin pelimuoto."; return; }
    
    showMode(GAME_MODE);
    el.genStatus.textContent = "Luodaan sisältöä tekoälyllä...";
    el.btnGenerate.disabled = true;

    try {
        const title = el.title.value.trim() || 'yleistieto';
        if (GAME_MODE === 'quiz') {
            const difficulty = el.difficulty.value;
            const questions = await fetchQuestionBatch({ key, title, difficulty });
            resetGameWith({ difficulty, initialQuestions: questions });
        } else if (GAME_MODE === 'hangman') {
            await hmStartAI({ key, topic: title });
        } else if (GAME_MODE === 'memory') {
            await mmStartAI({ key, topic: title });
        }
        el.genStatus.textContent = "Valmis! Peli voi alkaa.";
    } catch (error) {
        el.genStatus.textContent = `Virhe: ${error.message}`;
    } finally {
        el.btnGenerate.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setupBackground();
    drawBoardBackground();
    showMode(null);

    document.getElementById('mode-quiz').addEventListener('click', () => showMode('quiz'));
    document.getElementById('mode-hangman').addEventListener('click', () => showMode('hangman'));
    document.getElementById('mode-memory').addEventListener('click', () => showMode('memory'));
    
    el.btnStartMockQuiz.addEventListener('click', startMockQuiz);
    el.btnGenerate.addEventListener('click', handleGenerateGame);
    el.restart.addEventListener('click', restartQuiz); // MUUTETTU TÄHÄN
    el.next.addEventListener('click', () => advanceAfterAnswer(lastAnswerWasCorrect));
    el.btnClearKey?.addEventListener('click', () => { el.apiKey.value = ''; });

    $('hmRestart').addEventListener('click', hmStartDemo);
    $('mmRestart').addEventListener('click', mmStartDemo);

    const btnToggle = document.getElementById('btnToggleBackground');
    if (btnToggle) {
        btnToggle.addEventListener('click', () => {
            isAnimationPaused = !isAnimationPaused;

            if (isAnimationPaused) {
                cancelAnimationFrame(animationFrameId);
                btnToggle.textContent = 'Käynnistä tausta';
            } else {
                animate();
                btnToggle.textContent = 'Pysäytä tausta';
            }
        });
    }
});