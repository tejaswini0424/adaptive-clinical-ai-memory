"""Run manually against the live API: python tests/dashboard_smoke.py."""
import uuid
from pathlib import Path
import httpx
from streamlit.testing.v1 import AppTest

def main():
    result = httpx.post('http://127.0.0.1:8000/auth/register', json={'username':'ui-check-'+uuid.uuid4().hex, 'password':'x'}).json()
    httpx.post('http://127.0.0.1:8000/demo', headers={'Authorization':'Bearer '+result['token']}).raise_for_status()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=60)
    app.run()
    assert not app.exception
    app.session_state['token'] = result['token']
    app.session_state['username'] = result['username']
    app.run()
    assert not app.exception
    for page in ['Overview', 'Knowledge Repository', 'Adaptive Memory', 'Knowledge Retrieval', 'Evidence Updates', 'AI Agents', 'Search & Chat', 'Reports & Analytics']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f'{page}: {app.exception}'
        assert not app.error, f'{page}: {app.error}'
        print('PASS:', page)
    app.sidebar.button[0].click().run()
    assert 'token' not in app.session_state
    print('PASS: logout')
if __name__ == '__main__':
    main()
