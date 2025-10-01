# TaskuOpe/ops_chunks.py
# Kevyt OPS-chunk-haku ilman vektoreita ja ilman RapidFuzzia.
# Lukee JSONin: TaskuOpe/ops_data/opetussuunnitelma_1-6_API_data.json

import json
import os
import time
from typing import List, Dict, Optional, Tuple
from django.conf import settings
import re
from collections import Counter

JSON_FILENAME = "opetussuunnitelma_1-6_API_data.json"

_DATA: List[Dict] = []
_FACETS: Dict[str, List[str]] = {}
_LOADED_PATH = ""
_LOADED_MTIME = 0.0

WORD_RE = re.compile(r"\w+", re.UNICODE)

def _json_path() -> str:
    import os
    from django.conf import settings
    # BASE_DIR osoittaa yleensä .../TaskuOpe
    return os.path.join(settings.BASE_DIR, "ops_data", JSON_FILENAME)

def _build_facets(rows: List[Dict]) -> Dict[str, List[str]]:
    subs, grades, ctypes = set(), set(), set()
    for r in rows:
        subs.add((r.get("subject") or "").strip())
        grades.add((r.get("grade_context") or "").strip())
        ctypes.add((r.get("content_type") or "").strip())
    clean = lambda s: sorted([x for x in s if x])
    return {
        "subjects": clean(subs),
        "grades": clean(grades),
        "content_types": clean(ctypes),
    }

def _tokenize(text: str) -> List[str]:
    # yksinkertainen tokenisointi ja pienennys
    return [t.lower() for t in WORD_RE.findall(text)]

def _load_data(force: bool = False) -> None:
    global _DATA, _FACETS, _LOADED_PATH, _LOADED_MTIME
    path = _json_path()
    st = os.stat(path)
    if (not force) and _LOADED_PATH == path and _LOADED_MTIME == st.st_mtime and _DATA:
        return

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    norm: List[Dict] = []
    for i, r in enumerate(raw):
        txt = (r.get("content") or "").strip()
        if not txt:
            continue
        subj = (r.get("subject") or "").strip()
        grade = (r.get("grade_context") or "").strip()
        ctype = (r.get("content_type") or "").strip()
        src = (r.get("source") or "POPS_2014").strip()
        tokens = _tokenize(txt)
        tf = Counter(tokens)
        norm.append({
            "id": f"ops-{i}",
            "text": txt,
            "subject": subj,
            "grade_context": grade,
            "content_type": ctype,
            "source": src,
            "_tokens": tokens,
            "_tf": tf,                  # term frequencies
            "_len": max(len(tokens), 1) # pituus normaaliin
        })

    _DATA = norm
    _FACETS = _build_facets(norm)
    _LOADED_PATH = path
    _LOADED_MTIME = st.st_mtime

def get_facets() -> Dict[str, List[str]]:
    _load_data()
    return _FACETS

def _score(query_tokens: List[str], row: Dict) -> float:
    """
    Yksinkertainen avainsanapisteytys:
    - summaa kyselytermien esiintymät (TF)
    - normalisoi kevyesti dokumentin pituudella
    - bonus jos kaikki termit löytyvät
    """
    if not query_tokens:
        return 0.0
    tf = row["_tf"]
    hits = sum(tf.get(t, 0) for t in query_tokens)
    if hits == 0:
        return 0.0
    coverage = len({t for t in query_tokens if tf.get(t, 0) > 0}) / len(set(query_tokens))
    base = hits / (0.5 + 0.5 * row["_len"])  # kevyt pituuspenalti
    return base * (1.0 + coverage)           # palkitse kattavuudesta (1–2x)

def retrieve_chunks(
    query: str = "",
    k: int = 8,
    subjects: Optional[List[str]] = None,
    grades: Optional[List[str]] = None,
    ctypes: Optional[List[str]] = None,
    min_score: float = 0.0
) -> List[Dict]:
    """
    Palauttaa top-k chunkit ilman RapidFuzzia. Jos query on tyhjä,
    palauttaa k lyhyintä riviä valituilla suodattimilla.
    """
    _load_data()
    subj_set = {s.strip().lower() for s in (subjects or []) if s}
    grade_set = {g.strip().lower() for g in (grades or []) if g}
    type_set = {t.strip().lower() for t in (ctypes or []) if t}

    rows: List[Dict] = []
    for r in _DATA:
        if subj_set and r["subject"].lower() not in subj_set:
            continue
        if grade_set and r["grade_context"].lower() not in grade_set:
            continue
        if type_set and r["content_type"].lower() not in type_set:
            continue
        rows.append(r)

    if not query.strip():
        rows.sort(key=lambda x: len(x["text"]))
        rows = rows[:k]
        return [_public_fields(x, score=None) for x in rows]

    q_tokens = _tokenize(query)
    scored = []
    for r in rows:
        s = _score(q_tokens, r)
        if s > min_score:
            scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [_public_fields(r, score=float(s)) for s, r in scored[:k]]

def _public_fields(row: Dict, score: Optional[float]) -> Dict:
    out = {
        "id": row["id"],
        "text": row["text"],
        "subject": row["subject"],
        "grade_context": row["grade_context"],
        "content_type": row["content_type"],
        "source": row["source"],
    }
    if score is not None:
        out["score"] = round(score, 6)
    return out

def format_for_llm(chunks: List[Dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        meta = f"{c['subject']} | {c['grade_context']} | {c['content_type']}"
        lines.append(f"[{i}] ({meta})\n{c['text']}")
    return "\n\n".join(lines)
