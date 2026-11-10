import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session as DBSession
from .database import get_db
from .models import User, Session

security = HTTPBearer(auto_error=False)
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'{salt}:{digest}'
def verify(password, stored):
    salt, expected = stored.split(':')
    return secrets.compare_digest(hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex(), expected)
def current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: DBSession = Depends(get_db)):
    token = hashlib.sha256(credentials.credentials.encode()).hexdigest() if credentials else ''
    session = db.get(Session, token)
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(401, 'Please log in again.')
    return db.get(User, session.user_id)
def login_session(db, user):
    token = secrets.token_urlsafe(32)
    db.add(Session(id=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=datetime.utcnow()+timedelta(hours=12)))
    db.commit()
    return {'token': token, 'username': user.username}
