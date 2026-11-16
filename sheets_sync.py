"""Қолтаңбалы Google Sheets жіберімі; құпия дерек журналға жазылмайды."""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from urllib.request import Request, urlopen
from urllib.error import URLError
import mentor_core as core


def valid_url(url):
    return bool(re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url or ''))


def settings():
    url = os.environ.get('MENTOR_SHEETS_URL', '')
    secret = os.environ.get('MENTOR_SHEETS_SECRET', '')
    if not url or not secret:
        import streamlit as st
        try:
            block = st.secrets.get('google_sheets', {})
            url = url or block.get('web_app_url', '')
            secret = secret or block.get('shared_secret', '')
        except FileNotFoundError:
            pass
    return str(url).strip(), str(secret).strip()


def delivery_payload(user, result):
    # Тек бекітілген бағандар; құпиясөз, токен және жауаптар тізімі жіберілмейді.
    return {'username': user['username'], 'school_class': user['school_class'], 'test_title': result.get('title', 'Жаттығу'), 'correct': result['score'], 'total': result['total'], 'points': result.get('points', result['score']), 'max_points': result.get('max_points', result['total']), 'percent': result['percent']}


def envelope(payload, secret, now=None):
    body = json.dumps({'sent_at': int(time.time() if now is None else now), 'result': payload}, ensure_ascii=False, separators=(',', ':'))
    signature = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
    return {'payload': body, 'signature': signature}


def send(payload, url, secret):
    if not valid_url(url) or len(secret) < 32:
        return False, 'configuration'
    request = Request(url, data=json.dumps(envelope(payload, secret), ensure_ascii=False).encode('utf-8'), headers={'Content-Type':'application/json; charset=utf-8'}, method='POST')
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(8193)
        if len(raw) > 8192:
            return False, 'response'
        reply = json.loads(raw)
        if reply.get('ok') is True and reply.get('attempt_id') == payload['attempt_id']:
            return True, ''
        return False, 'rejected'
    except (OSError, URLError, ValueError, TypeError, AttributeError):
        return False, 'connection'


def sync_pending(profile, url, secret, limit=1):
    """Кезекте тек осы аккаунттың нәтижелері алынады. Қайталануды сервер тежейді."""
    if not valid_url(url) or len(secret) < 32:
        return {'sent': 0, 'failed': 0, 'configured': False}
    with core.connect() as con:
        rows = con.execute('SELECT o.attempt_id, o.payload FROM sheets_outbox o JOIN attempts a ON a.id=o.attempt_id WHERE a.profile=? AND o.delivered_at IS NULL ORDER BY a.rowid LIMIT ?', (profile, max(1,min(limit,3)))).fetchall()
    sent, failed = 0, 0
    for attempt_id, raw in rows:
        ok, code = send(json.loads(raw), url, secret)
        with core.connect() as con:
            con.execute('UPDATE sheets_outbox SET tries=tries+1, last_error=?, delivered_at=CASE WHEN ? THEN ? ELSE delivered_at END WHERE attempt_id=?', (code, int(ok), int(time.time()), attempt_id))
        sent += int(ok)
        failed += int(not ok)
    return {'sent':sent, 'failed':failed, 'configured':True}


def counts(profile):
    with core.connect() as con:
        rows = con.execute('SELECT o.delivered_at FROM sheets_outbox o JOIN attempts a ON a.id=o.attempt_id WHERE a.profile=?', (profile,)).fetchall()
    return {'sent':sum(r[0] is not None for r in rows), 'pending':sum(r[0] is None for r in rows)}
