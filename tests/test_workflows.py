import os
import uuid
from pathlib import Path
os.environ['DATABASE_URL'] = 'sqlite:///'+str(Path('database').resolve()/f'test-{uuid.uuid4().hex}.db')
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User

client = TestClient(app)
def account(name):
    r = client.post('/auth/register', json={'username':name, 'password':'x'})
    assert r.status_code == 201
    return {'Authorization':'Bearer '+r.json()['token']}
def test_auth_isolation_logout():
    a = account('a')
    assert client.post('/auth/register', json={'username':'a','password':'x'}).status_code == 409
    assert client.post('/auth/login', json={'username':'a','password':'bad'}).status_code == 401
    assert client.post('/auth/login', json={'username':'a','password':'x'}).status_code == 200
    b = account('b')
    doc = client.post('/documents', headers=a, json={'title':'Private','content':'private passage'}).json()
    assert client.get('/documents', headers=b).json() == []
    assert client.delete(f'/documents/{doc["id"]}', headers=b).status_code == 404
    with SessionLocal() as db:
        assert db.get(User, 1).password_hash != 'x'
    assert client.post('/auth/logout', headers=a).status_code == 200
    assert client.get('/documents', headers=a).status_code == 401
def test_memory_persistence_and_history():
    h = account('memory')
    body = {'content':'diabetes evidence provenance','kind':'semantic','source':'test'}
    m = client.post('/memories', headers=h, json=body).json()
    assert client.post('/memories', headers=h, json=body).json()['id'] == m['id']
    assert client.get('/memories?q=diabetes', headers=h).json()[0]['score'] > 0
    assert TestClient(app).get('/memories', headers=h).json()[0]['id'] == m['id']
    assert client.put(f'/memories/{m["id"]}', headers=h, json=dict(body,content='updated')).status_code == 200
    assert client.delete(f'/memories/{m["id"]}', headers=h).status_code == 200
    assert len(client.get('/analytics', headers=h).json()['memory_history']) == 3
def test_upload_retrieval_reports():
    h = account('retrieval')
    assert client.post('/documents/upload', headers=h, files={'file':('case.txt', b'Diabetes research requires evidence provenance and publication dates.')}).status_code == 201
    assert client.post('/documents/upload', headers=h, files={'file':('bad.pdf', b'not pdf')}).status_code == 422
    result = client.post('/retrieve', headers=h, json={'query':'diabetes evidence'}).json()
    assert 'Diabetes research' in result['evidence'][0]['passage']
    assert 'extractive' in result['explanation_type']
    assert client.post('/retrieve', headers=h, json={'query':'zzyyxx'}).json()['evidence'] == []
    assert 'query' in client.get('/reports/retrievals', headers=h).text
def test_evidence_review_versions():
    h = account('evidence')
    old = client.post('/documents', headers=h, json={'title':'Old','content':'Original evidence passage','published_at':'2020-01-01'}).json()
    new = client.post('/evidence', headers=h, json={'title':'New','content':'New evidence passage','published_at':'2025-01-01','target_id':old['id']}).json()
    assert new['status'] == 'pending'
    assert next(d for d in client.get('/documents', headers=h).json() if d['id']==old['id'])['content'] == 'Original evidence passage'
    assert client.post(f'/evidence/{new["id"]}/review', headers=h, json={'decision':'accepted'}).status_code == 200
    assert client.post(f'/evidence/{new["id"]}/review', headers=h, json={'decision':'accepted'}).status_code == 409
    versions = client.get('/evidence', headers=h).json()[0]['versions']
    assert len(versions)==2
    assert any(v['old_content']=='Original evidence passage' for v in versions)
    assert next(d for d in client.get('/documents', headers=h).json() if d['id']==old['id'])['content'] == 'New evidence passage'
def test_demo_and_dates():
    h = account('demo')
    assert client.post('/demo', headers=h).json()['documents_added'] == 3
    assert client.post('/demo', headers=h).status_code == 409
    assert client.post('/documents', headers=h, json={'title':'bad date','content':'text','published_at':'yesterday'}).status_code == 422
    assert client.get('/analytics', headers=h).json()['knowledge_records'] == 3
