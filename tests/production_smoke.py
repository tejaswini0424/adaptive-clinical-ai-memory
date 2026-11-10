"""Smoke test the public deployment without Vercel credentials."""
import ssl
import uuid
import httpx

def main():
    with httpx.Client(base_url='https://clinical-ai-memory.vercel.app', verify=ssl.create_default_context(), timeout=60) as c:
        r = c.get('/')
        r.raise_for_status()
        assert 'Clinical AI Memory' in r.text
        print('PASS: public frontend without Vercel login')
        credentials = {'username':'deployment-check-'+uuid.uuid4().hex[:10], 'password':uuid.uuid4().hex}
        r = c.post('/auth/register', json=credentials)
        r.raise_for_status()
        c.headers['Authorization'] = 'Bearer '+r.json()['token']
        print('PASS: public account registration')
        c.post('/demo').raise_for_status()
        docs = c.get('/documents').json()
        assert len(docs)==3
        print('PASS: PostgreSQL document persistence')
        r = c.post('/retrieve', json={'query':'diabetes evidence'})
        r.raise_for_status()
        assert r.json()['evidence']
        print('PASS: passage retrieval and extractive summary')
        m = c.post('/memories', json={'content':'Synthetic deployment smoke memory','kind':'long-term','source':'Deployment verification'})
        m.raise_for_status()
        assert c.get('/memories?q=deployment').json()
        c.delete('/memories/'+str(m.json()['id'])).raise_for_status()
        print('PASS: memory storage, search, deletion')
        r = c.post('/documents/upload', files={'file':('smoke.txt', b'Synthetic educational upload smoke test')})
        r.raise_for_status()
        c.delete('/documents/'+str(r.json()['id'])).raise_for_status()
        print('PASS: document upload and deletion')
        e = c.post('/evidence', json={'title':'Synthetic deployment evidence','content':'Synthetic updated evidence passage for educational comparison.','published_at':'2026-01-01','target_id':docs[0]['id']})
        e.raise_for_status()
        c.post(f'/evidence/{e.json()["id"]}/review', json={'decision':'rejected'}).raise_for_status()
        assert c.get('/evidence').json()[0]['status']=='rejected'
        print('PASS: evidence review and history')
        c.get('/reports/documents').raise_for_status()
        c.get('/analytics').raise_for_status()
        print('PASS: analytics and CSV export')
        c.post('/auth/logout').raise_for_status()
        assert c.get('/documents').status_code==401
        r = c.post('/auth/login', json=credentials)
        r.raise_for_status()
        c.headers['Authorization'] = 'Bearer '+r.json()['token']
        assert len(c.get('/documents').json())>=3
        c.post('/auth/logout').raise_for_status()
        print('PASS: logout, login, retained account data')
if __name__=='__main__':
    main()
