from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from .database import Base

def now():
    return datetime.now(timezone.utc)
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now)
class Session(Base):
    __tablename__ = 'sessions'
    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    expires_at = Column(DateTime, nullable=False)
class Owned:
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=now)
class Document(Owned, Base):
    __tablename__ = 'clinical_documents'
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, default='General')
    source = Column(Text, default='Manual entry')
    published_at = Column(String, default='')
    updated_at = Column(DateTime, default=now, onupdate=now)
class Knowledge(Owned, Base):
    __tablename__ = 'knowledge_records'
    document_id = Column(Integer, ForeignKey('clinical_documents.id', ondelete='CASCADE'))
    content = Column(Text)
class Memory(Owned, Base):
    __tablename__ = 'agent_memories'
    content = Column(Text, nullable=False)
    kind = Column(String, nullable=False)
    source = Column(Text, default='User')
    accesses = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=now, onupdate=now)
class MemoryHistory(Owned, Base):
    __tablename__ = 'memory_history'
    memory_id = Column(Integer, ForeignKey('agent_memories.id', ondelete='SET NULL'), nullable=True)
    content = Column(Text)
    action = Column(String)
class Evidence(Owned, Base):
    __tablename__ = 'evidence_records'
    document_id = Column(Integer, ForeignKey('clinical_documents.id', ondelete='CASCADE'))
    target_id = Column(Integer, ForeignKey('clinical_documents.id', ondelete='SET NULL'), nullable=True)
    status = Column(String, default='pending')
    comparison = Column(Text)
    reviewed_at = Column(DateTime, nullable=True)
class EvidenceVersion(Owned, Base):
    __tablename__ = 'evidence_versions'
    evidence_id = Column(Integer, ForeignKey('evidence_records.id', ondelete='CASCADE'))
    old_content = Column(Text)
    new_content = Column(Text)
    decision = Column(String)
class Retrieval(Owned, Base):
    __tablename__ = 'retrieval_history'
    query = Column(Text)
    hits = Column(Integer)
    engine = Column(String)
class Activity(Owned, Base):
    __tablename__ = 'agent_activity'
    agent = Column(String)
    task = Column(Text)
    status = Column(String, default='success')
    duration_ms = Column(Float, default=0)
