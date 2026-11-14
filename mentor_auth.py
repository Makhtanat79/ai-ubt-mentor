"""Құпиясөз хэші, мерзімді сессия және кіру әрекеттерін шектеу."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
import unicodedata
from uuid import uuid4
import mentor_core as core

SESSION_SECONDS = 12 * 60 * 60
LOCK_SECONDS = 15 * 60


def setup(con):
    con.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, school_class TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires INTEGER NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS login_limits (username TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until INTEGER NOT NULL)')


def normalize(username):
    return unicodedata.normalize('NFKC', username).strip().casefold()


def password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024, dklen=32).hex()


def register(username, school_class, password):
    username = normalize(username)
    if not re.fullmatch(r'[\w.-]{3,32}', username, re.UNICODE):
        raise ValueError('Пайдаланушы аты 3–32 әріптен, саннан немесе _ . - таңбаларынан тұрсын.')
    if school_class not in ('10-сынып', '11-сынып'):
        raise ValueError('Сыныпты таңдаңыз.')
    if not 12 <= len(password) <= 128:
        raise ValueError('Құпиясөз ұзындығы 12–128 таңба болсын. Бірнеше сөзден тұратын тіркес қолдануға болады.')
    salt = secrets.token_hex(16)
    digest = password_hash(password, salt)
    user_id = str(uuid4())
    try:
        with core.connect() as con:
            setup(con)
            con.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?)', (user_id, username, school_class, salt, digest))
    except sqlite3.IntegrityError:
        raise ValueError('Бұл пайдаланушы аты бос емес. Басқа атау таңдаңыз.') from None
    return user_id


def login(username, password):
    username = normalize(username)
    if not username or len(username) > 128 or not isinstance(password, str) or len(password) > 128:
        return None
    now = int(time.time())
    with core.connect() as con:
        setup(con)
        con.execute('BEGIN IMMEDIATE')
        limit = con.execute('SELECT failures, locked_until FROM login_limits WHERE username = ?', (username,)).fetchone()
        if limit and limit[1] > now:
            return None
        user = con.execute('SELECT id, salt, password_hash FROM users WHERE username = ?', (username,)).fetchone()
        # Жоқ пайдаланушыда да хэш есептеледі.
        salt = user[1] if user else '00' * 16
        digest = password_hash(password, salt)
        valid = bool(user and hmac.compare_digest(digest, user[2]))
        if not valid:
            failures = (limit[0] if limit and limit[1] == 0 else 0) + 1
            locked_until = now + LOCK_SECONDS if failures >= 5 else 0
            con.execute('INSERT OR REPLACE INTO login_limits VALUES (?, ?, ?)', (username, failures, locked_until))
            return None
        con.execute('DELETE FROM login_limits WHERE username = ?', (username,))
        con.execute('DELETE FROM sessions WHERE expires <= ?', (now,))
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        con.execute('INSERT INTO sessions VALUES (?, ?, ?)', (token_hash, user[0], now + SESSION_SECONDS))
        return token


def current_user(token):
    if not isinstance(token, str) or not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with core.connect() as con:
        setup(con)
        row = con.execute('SELECT u.id, u.username, u.school_class FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires > ?', (digest, int(time.time()))).fetchone()
    return {'id': row[0], 'username': row[1], 'school_class': row[2], 'profile': 'account:' + row[0]} if row else None


def logout(token):
    if not isinstance(token, str):
        return
    with core.connect() as con:
        setup(con)
        con.execute('DELETE FROM sessions WHERE token_hash = ?', (hashlib.sha256(token.encode()).hexdigest(),))
