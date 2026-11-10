import csv
import hashlib
import io
import time
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from .database import Base, engine, get_db
from .models import *
from .auth import current_user, hash_password, verify, login_session, security
from .retrieval import rank, passages, summarize

Base.metadata.create_all(engine)
app = FastAPI(title='Clinical AI Memory Intelligence Platform', version='1.0.0')
class Credentials(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
class DocumentInput(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    category: str = 'General'
    source: str = 'Manual entry'
    published_at: str = ''
class MemoryInput(BaseModel):
    content: str = Field(min_length=1)
    kind: str = 'long-term'
    source: str = 'User'
class Query(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
class EvidenceInput(DocumentInput):
    target_id: int | None = None
class Decision(BaseModel):
    decision: str
def rows(db, cls, uid):
    return db.scalars(select(cls).where(cls.user_id == uid).order_by(cls.id.desc())).all()
def owned(db, cls, id, uid):
    obj = db.get(cls, id)
    if not obj or obj.user_id != uid:
        raise HTTPException(404, 'Record not found')
    return obj
def serial(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name != 'user_id'}
def activity(db, uid, agent, task, elapsed=0):
    db.add(Activity(user_id=uid, agent=agent, task=task, duration_ms=elapsed))
def add_document(db, uid, data):
    if data.published_at:
        try:
            date.fromisoformat(data.published_at)
        except ValueError:
            raise HTTPException(422, 'Publication date must use YYYY-MM-DD')
    doc = Document(user_id=uid, **data.model_dump(exclude={'target_id'}))
    db.add(doc)
    db.flush()
    db.add(Knowledge(user_id=uid, document_id=doc.id, content=doc.content))
    return doc
@app.get('/health')
def health():
    return {'status': 'ok'}
@app.post('/auth/register', status_code=201)
def register(data: Credentials, db: DBSession = Depends(get_db)):
    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Username already exists')
    return login_session(db, user)
@app.post('/auth/login')
def login(data: Credentials, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not verify(data.password, user.password_hash):
        raise HTTPException(401, 'Invalid credentials')
    return login_session(db, user)
@app.post('/auth/logout')
def logout(user=Depends(current_user), credentials=Depends(security), db: DBSession = Depends(get_db)):
    db.delete(db.get(Session, hashlib.sha256(credentials.credentials.encode()).hexdigest()))
    db.commit()
    return {'status': 'logged out'}
@app.get('/documents')
def documents(q: str = '', user=Depends(current_user), db: DBSession = Depends(get_db)):
    return [serial(d) for d in rows(db, Document, user.id) if q.casefold() in (d.title+' '+d.content+' '+d.category).casefold()]
@app.post('/documents', status_code=201)
def create_document(data: DocumentInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    doc = add_document(db, user.id, data)
    db.commit()
    return serial(doc)
@app.post('/documents/upload', status_code=201)
async def upload(file: UploadFile = File(...), category: str = Form('General'), user=Depends(current_user), db: DBSession = Depends(get_db)):
    raw = await file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, 'Maximum file size is 10 MB')
    try:
        if file.filename.lower().endswith('.pdf'):
            from pypdf import PdfReader
            content = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
        elif file.filename.lower().endswith('.txt'):
            content = raw.decode('utf-8-sig')
        else:
            raise ValueError('Upload PDF or UTF-8 TXT')
        if not content.strip():
            raise ValueError('No extractable text; scanned PDFs require OCR')
    except Exception as exc:
        raise HTTPException(422, f'Unable to read document: {exc}')
    return create_document(DocumentInput(title=file.filename, content=content, category=category, source=f'Uploaded: {file.filename}'), user, db)
@app.put('/documents/{id}')
def edit_document(id: int, data: DocumentInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    doc = owned(db, Document, id, user.id)
    if data.published_at:
        try:
            date.fromisoformat(data.published_at)
        except ValueError:
            raise HTTPException(422, 'Invalid date')
    db.add(EvidenceVersion(user_id=user.id, old_content=doc.content, new_content=data.content, decision='manual edit'))
    for key, val in data.model_dump().items():
        setattr(doc, key, val)
    for item in db.scalars(select(Knowledge).where(Knowledge.document_id == id)):
        item.content = data.content
    db.commit()
    return serial(doc)
@app.delete('/documents/{id}')
def delete_document(id: int, user=Depends(current_user), db: DBSession = Depends(get_db)):
    db.delete(owned(db, Document, id, user.id))
    db.commit()
    return {'deleted': id}
@app.get('/memories')
def memories(q: str = '', user=Depends(current_user), db: DBSession = Depends(get_db)):
    items = rows(db, Memory, user.id)
    items = [m for m in items if m.kind != 'short-term' or m.updated_at > datetime.utcnow()-timedelta(hours=24)]
    if not q:
        return [serial(m) for m in items]
    hits, _ = rank(q, [dict(serial(m), passage=m.content) for m in items])
    for hit in hits:
        m = db.get(Memory, hit['id'])
        m.accesses += 1
        m.last_accessed = datetime.utcnow()
    activity(db, user.id, 'Memory Agent', 'Search memories')
    db.commit()
    return hits
@app.post('/memories', status_code=201)
def create_memory(data: MemoryInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    if data.kind not in ['short-term', 'long-term', 'semantic', 'episodic']:
        raise HTTPException(422, 'Unknown memory type')
    existing = next((m for m in rows(db, Memory, user.id) if m.content.strip().casefold() == data.content.strip().casefold() and m.kind == data.kind), None)
    if existing:
        return serial(existing)
    item = Memory(user_id=user.id, **data.model_dump())
    db.add(item)
    db.flush()
    db.add(MemoryHistory(user_id=user.id, memory_id=item.id, content=item.content, action='created'))
    activity(db, user.id, 'Memory Agent', 'Store memory')
    db.commit()
    return serial(item)
@app.put('/memories/{id}')
def edit_memory(id: int, data: MemoryInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    item = owned(db, Memory, id, user.id)
    if data.kind not in ['short-term', 'long-term', 'semantic', 'episodic']:
        raise HTTPException(422, 'Unknown memory type')
    db.add(MemoryHistory(user_id=user.id, memory_id=id, content=item.content, action='before edit'))
    for k, v in data.model_dump().items():
        setattr(item, k, v)
    db.commit()
    return serial(item)
@app.delete('/memories/{id}')
def delete_memory(id: int, user=Depends(current_user), db: DBSession = Depends(get_db)):
    item = owned(db, Memory, id, user.id)
    db.add(MemoryHistory(user_id=user.id, memory_id=id, content=item.content, action='deleted'))
    db.flush()
    db.delete(item)
    db.commit()
    return {'deleted': id}
@app.post('/retrieve')
def retrieve(data: Query, user=Depends(current_user), db: DBSession = Depends(get_db)):
    start = time.perf_counter()
    unreviewed = {e.document_id for e in rows(db, Evidence, user.id) if e.status != 'accepted'}
    corpus = [d for d in rows(db, Document, user.id) if d.id not in unreviewed]
    try:
        hits, mode = rank(data.query, passages(corpus), data.limit)
    except Exception as exc:
        raise HTTPException(503, f'Embedding engine unavailable: {exc}. Use EMBEDDING_BACKEND=tfidf for offline retrieval.')
    db.add(Retrieval(user_id=user.id, query=data.query, hits=len(hits), engine=mode))
    activity(db, user.id, 'Retrieval Agent', data.query, (time.perf_counter()-start)*1000)
    activity(db, user.id, 'Summarization Agent', 'Extractive summary')
    create_memory(MemoryInput(content=f'Query: {data.query}\nRetrieved document IDs: {[h["document_id"] for h in hits]}', kind='episodic', source='Retrieval Agent'), user, db)
    return {'evidence': hits, 'explanation': summarize(hits), 'explanation_type': 'Local extractive summary; source excerpts, not independently verified advice', 'engine': mode, 'related_memories': memories(data.query, user, db)}
@app.get('/evidence')
def evidence(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return [dict(serial(e), versions=[serial(v) for v in rows(db, EvidenceVersion, user.id) if v.evidence_id == e.id]) for e in rows(db, Evidence, user.id)]
@app.post('/evidence', status_code=201)
def add_evidence(data: EvidenceInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    target = owned(db, Document, data.target_id, user.id) if data.target_id else None
    doc = add_document(db, user.id, data)
    score = rank(data.content, passages([target]), 1)[0] if target else []
    newer = bool(target and data.published_at and target.published_at and data.published_at > target.published_at)
    import re
    negation = lambda text: bool(re.search(r'\b(no|not|never|ineffective|contraindicated)\b', text, re.I))
    conflict = bool(target and score and negation(target.content) != negation(data.content))
    comparison = f'Lexical/semantic overlap: {score[0]["score"] if score else 0}. '+('Possible conflict: differing negation language. ' if conflict else 'No negation-based conflict signal detected. ')+('New evidence is newer; existing record may be outdated. ' if newer else '')+'Potential disagreement requires human review; this heuristic cannot establish clinical contradiction.'
    item = Evidence(user_id=user.id, document_id=doc.id, target_id=data.target_id, comparison=comparison)
    db.add(item)
    db.flush()
    db.add(EvidenceVersion(user_id=user.id, evidence_id=item.id, old_content=target.content if target else '', new_content=doc.content, decision='proposed'))
    activity(db, user.id, 'Evidence Agent', 'Compare evidence')
    activity(db, user.id, 'Update Agent', 'Propose human review')
    db.commit()
    return serial(item)
@app.post('/evidence/{id}/review')
def review(id: int, data: Decision, user=Depends(current_user), db: DBSession = Depends(get_db)):
    item = owned(db, Evidence, id, user.id)
    if item.status != 'pending':
        raise HTTPException(409, 'Already reviewed')
    if data.decision not in ['accepted', 'rejected']:
        raise HTTPException(422, 'Choose accepted or rejected')
    new = owned(db, Document, item.document_id, user.id)
    target = owned(db, Document, item.target_id, user.id) if item.target_id else None
    db.add(EvidenceVersion(user_id=user.id, evidence_id=id, old_content=target.content if target else '', new_content=new.content, decision=data.decision))
    if data.decision == 'accepted' and target:
        target.content, target.published_at, target.source = new.content, new.published_at, new.source
        for k in db.scalars(select(Knowledge).where(Knowledge.document_id == target.id)):
            k.content = new.content
    item.status, item.reviewed_at = data.decision, datetime.utcnow()
    activity(db, user.id, 'Update Agent', f'Human {data.decision} evidence')
    db.commit()
    return serial(item)
REPORTS = {'documents': Document, 'memories': Memory, 'retrievals': Retrieval, 'evidence': Evidence, 'agents': Activity, 'memory_history': MemoryHistory, 'versions': EvidenceVersion}
@app.get('/analytics')
def analytics(user=Depends(current_user), db: DBSession = Depends(get_db)):
    result = {name: [serial(r) for r in rows(db, cls, user.id)] for name, cls in REPORTS.items()}
    result['knowledge_records'] = len(rows(db, Knowledge, user.id))
    return result
@app.get('/reports/{name}')
def report(name: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    if name not in REPORTS:
        raise HTTPException(404, 'Unknown report')
    cls = REPORTS[name]
    fields = [c.name for c in cls.__table__.columns if c.name != 'user_id']
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows(db, cls, user.id):
        record = serial(row)
        writer.writerow({k: ("'"+v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v) for k, v in record.items()})
    return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename={name}.csv'})
@app.post('/demo')
def demo(user=Depends(current_user), db: DBSession = Depends(get_db)):
    if rows(db, Document, user.id):
        raise HTTPException(409, 'Demo is available only in an empty repository')
    import json
    from .database import ROOT
    samples = json.loads((ROOT/'data'/'sample_evidence.json').read_text())
    for entry in samples:
        add_document(db, user.id, DocumentInput(**entry))
    db.commit()
    create_memory(MemoryInput(content='Educational evidence should retain publication dates and source provenance.', kind='semantic', source='Synthetic demo'), user, db)
    return {'documents_added': len(samples)}
