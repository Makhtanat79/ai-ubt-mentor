"""Қазақша оқу платформасының бағалау және сақтау логикасы."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DB = Path(os.environ.get('MENTOR_DB', Path(__file__).parent / 'data' / 'mentor.db'))
ROOT = Path(__file__).parent

def load_content():
    return tuple(json.loads((ROOT / name).read_text(encoding='utf-8')) for name in ('questions.json', 'chapters.json', 'variants.json'))

def question_points(q):
    return 2 if q.get('type') in ('multi', 'match') else 1

def answer_complete(q, a):
    kind = q.get('type', 'single')
    if kind == 'multi':
        return isinstance(a, list) and len(a) > 0
    if kind == 'match':
        return isinstance(a, list) and len(a) == len(q['left']) and all(v is not None for v in a)
    return a is not None

def answer_valid(q, a):
    if not answer_complete(q, a):
        return False
    values = a if isinstance(a, list) else [a]
    if not all(type(v) is int and 0 <= v < len(q['options']) for v in values):
        return False
    if q.get('type') == 'multi' and len(set(values)) != len(values):
        return False
    return True

def grade(questions, answers):
    if not questions or len(questions) != len(answers) or any(not answer_valid(q, a) for q, a in zip(questions, answers)):
        raise ValueError('Барлық тапсырмаға жарамды жауап беріңіз.')
    topics, details = {}, []
    for q, a in zip(questions, answers):
        correct = set(a) == set(q['answer']) if q.get('type') == 'multi' else a == q['answer']
        maximum = question_points(q)
        points = maximum if correct else 0
        stat = topics.setdefault(q['topic'], {'correct': 0, 'total': 0, 'points': 0, 'max_points': 0})
        stat['total'] += 1
        stat['correct'] += int(correct)
        stat['points'] += points
        stat['max_points'] += maximum
        details.append({**q, 'selected': a, 'correct': correct, 'points': points, 'max_points': maximum})
    points = sum(d['points'] for d in details)
    maximum = sum(d['max_points'] for d in details)
    return {'score': sum(d['correct'] for d in details), 'total': len(questions), 'points': points, 'max_points': maximum, 'percent': round(points / maximum * 100), 'topics': topics, 'details': details, 'version': 2}

@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=15)
    try:
        with con:
            con.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, profile TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL)')
            yield con
    finally:
        con.close()

def save_attempt(attempt_id, profile, result):
    with connect() as con:
        con.execute('INSERT OR IGNORE INTO attempts VALUES (?, ?, ?, ?)', (attempt_id, profile, datetime.now(ZoneInfo('Asia/Almaty')).isoformat(timespec='seconds'), json.dumps(result, ensure_ascii=False)))

def history(profile):
    with connect() as con:
        rows = con.execute('SELECT created, payload FROM attempts WHERE profile = ? ORDER BY created DESC, rowid DESC', (profile,)).fetchall()
    return [{'created': date, **json.loads(payload)} for date, payload in rows]

def plan(topics, minutes):
    if not topics:
        return []
    ordered = sorted(topics, key=lambda t: topics[t]['correct'] / topics[t]['total'])
    tasks = ['Теорияны оқып, негізгі ережелерді өз сөзіңізбен жазыңыз.', 'Шешілген мысалды өзіңіз қайта шығарып, тарау тестін орындаңыз.', 'Қате жауаптардың түсіндірмесін оқып, тестті қайта орындаңыз.']
    return [{'day': i + 1, 'topic': ordered[i % len(ordered)], 'minutes': minutes, 'task': tasks[i % 3]} for i in range(7)]
