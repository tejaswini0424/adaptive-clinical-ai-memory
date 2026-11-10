import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='Clinical AI Memory', page_icon='🧬', layout='wide')
st.markdown(f'<style>{(Path(__file__).parent/"frontend"/"styles.css").read_text()}</style>', unsafe_allow_html=True)
API = os.getenv('API_URL', 'http://127.0.0.1:8000')
def api(method, path, **kwargs):
    try:
        response = httpx.request(method, API+path, headers={'Authorization': f'Bearer {st.session_state.get("token", "")}'}, timeout=120, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get('detail', response.text)
            except ValueError:
                detail = response.text
            st.error(str(detail))
            if response.status_code == 401:
                st.session_state.pop('token', None)
            return None
        return response.content if path.startswith('/reports/') else response.json()
    except httpx.HTTPError:
        st.error('Backend unavailable. Start it with: python -m uvicorn backend.main:app')
        return None
def refresh(result):
    if result is not None:
        st.rerun()
def document_fields(prefix, item=None):
    item = item or {}
    title = st.text_input('Title', value=item.get('title', ''), key=prefix+'title')
    content = st.text_area('Text / evidence passage', value=item.get('content', ''), height=180, key=prefix+'content')
    category = st.text_input('Category', value=item.get('category', 'General'), key=prefix+'category')
    source = st.text_input('Source / public evidence URL', value=item.get('source', 'Manual entry'), key=prefix+'source')
    published = st.text_input('Publication date (YYYY-MM-DD, optional)', value=item.get('published_at', ''), key=prefix+'date')
    return dict(title=title, content=content, category=category, source=source, published_at=published)
st.title('🧬 Clinical AI Memory Intelligence Platform')
st.caption('Research & education • Synthetic demo data • Evidence requires human review')
if 'token' not in st.session_state:
    left, right = st.columns([1, 1])
    with left:
        st.subheader('Knowledge that remembers. Evidence that evolves.')
        st.write('Organize clinical literature, explore source passages, and keep a transparent history of knowledge updates.')
        st.info('Create your own account to begin. Your repository and memories are private to your account.')
    with right:
        login, register = st.tabs(['Sign in', 'Create account'])
        for tab, action, label in [(login, 'login', 'Sign in'), (register, 'register', 'Create account')]:
            with tab, st.form(action):
                username = st.text_input('Username', key=action+'user')
                password = st.text_input('Password', type='password', key=action+'pass')
                if st.form_submit_button(label, type='primary'):
                    result = api('POST', '/auth/'+action, json={'username': username, 'password': password})
                    if result:
                        st.session_state.update(result)
                        st.rerun()
    st.stop()
@st.fragment(run_every=1)
def clock():
    now = datetime.now(ZoneInfo('Asia/Kolkata'))
    st.caption(f'{now:%A, %d %B %Y}  •  {now:%H:%M:%S} IST  •  {st.session_state.get("username")}  •  Signed in')
clock()
with st.sidebar:
    st.header('MEMORY INTELLIGENCE')
    page = st.radio('Workspace', ['Overview', 'Knowledge Repository', 'Adaptive Memory', 'Knowledge Retrieval', 'Evidence Updates', 'AI Agents', 'Search & Chat', 'Reports & Analytics'])
    st.divider()
    st.caption('Local processing · Persistent SQLite')
    if st.button('Log out', width="stretch"):
        if api('POST', '/auth/logout') is not None:
            st.session_state.clear()
            st.rerun()
if page in ['Overview', 'AI Agents', 'Reports & Analytics']:
    data = api('GET', '/analytics')
    if data is None:
        st.stop()
    if page == 'Overview':
        st.subheader('Your knowledge, connected')
        values = [('Knowledge records', data['knowledge_records']), ('Stored memories', len(data['memories'])), ('Evidence documents', len(data['evidence'])), ('Successful retrievals', sum(r['hits'] > 0 for r in data['retrievals'])), ('Accepted updates', sum(e['status'] == 'accepted' for e in data['evidence'])), ('Agent tasks', len(data['agents']))]
        cols = st.columns(3)
        for i, (label, value) in enumerate(values):
            cols[i%3].metric(label, value)
        if not data['documents']:
            st.info('Start with clearly labeled synthetic cases or add your own public evidence.')
            if st.button('Load synthetic demo', type='primary'):
                refresh(api('POST', '/demo'))
    if page == 'AI Agents':
        st.subheader('Agent operations')
        for name in ['Memory Agent', 'Retrieval Agent', 'Evidence Agent', 'Summarization Agent', 'Update Agent']:
            tasks = [t for t in data['agents'] if t['agent'] == name]
            with st.container(border=True):
                st.markdown(f'**{name}** · Ready (synchronous)')
                st.write(f'Tasks: {len(tasks)} · Success: {sum(t["status"] == "success" for t in tasks)} · Last execution: {tasks[0]["created_at"] if tasks else "Not run"}')
        st.dataframe(data['agents'], width="stretch")
    else:
        a, b = st.columns(2)
        for container, key, title in [(a, 'documents', 'Knowledge records over time'), (b, 'retrievals', 'Retrieval outcomes'), (a, 'evidence', 'Evidence review status'), (b, 'agents', 'Agent task performance'), (a, 'memories', 'Memory utilization')]:
            frame = pd.DataFrame(data[key])
            if frame.empty:
                container.info(title+': no activity yet')
                continue
            if key == 'documents':
                frame['day'] = pd.to_datetime(frame['created_at']).dt.date.astype(str)
                counts = frame.groupby('day').size().reset_index(name='records')
                counts['records'] = counts['records'].cumsum()
                fig = px.line(counts, x='day', y='records', markers=True, title=title)
            else:
                field = {'retrievals':'hits', 'evidence':'status', 'agents':'agent', 'memories':'kind'}[key]
                counts = frame.groupby(field).size().reset_index(name='count')
                fig = px.bar(counts, x=field, y='count', title=title, color_discrete_sequence=['#079f99'])
            container.plotly_chart(fig, width="stretch")
        if page == 'Reports & Analytics':
            for name in ['documents', 'memories', 'retrievals', 'evidence', 'agents', 'memory_history', 'versions']:
                if st.button('Prepare '+name+' CSV'):
                    content = api('GET', '/reports/'+name)
                    if content is not None:
                        st.download_button('Download '+name, content, file_name=name+'.csv', mime='text/csv', key='dl'+name)
elif page == 'Knowledge Repository':
    st.subheader('Clinical knowledge repository')
    with st.expander('Add knowledge manually'):
        with st.form('add_doc'):
            fields = document_fields('new')
            if st.form_submit_button('Save record', type='primary'):
                refresh(api('POST', '/documents', json=fields))
    with st.expander('Upload PDF or TXT'):
        with st.form('upload'):
            file = st.file_uploader('Document · maximum 10 MB', type=['pdf', 'txt'])
            category = st.text_input('Upload category', 'General')
            if st.form_submit_button('Upload document') and file:
                refresh(api('POST', '/documents/upload', files={'file': (file.name, file.getvalue(), file.type)}, data={'category': category}))
    q = st.text_input('Search title, text, or category')
    docs = api('GET', '/documents', params={'q': q}) or []
    for doc in docs:
        with st.expander(f'{doc["title"]} · {doc["category"]} · #{doc["id"]}'):
            st.caption(f'Created {doc["created_at"]} · Updated {doc["updated_at"]}')
            with st.form('edit'+str(doc['id'])):
                fields = document_fields(str(doc['id']), doc)
                if st.form_submit_button('Save changes'):
                    refresh(api('PUT', f'/documents/{doc["id"]}', json=fields))
            confirm = st.checkbox('Confirm permanent deletion', key='dc'+str(doc['id']))
            if st.button('Delete record', key='dd'+str(doc['id']), disabled=not confirm):
                refresh(api('DELETE', f'/documents/{doc["id"]}'))
elif page == 'Adaptive Memory':
    st.subheader('Adaptive agent memory')
    st.caption('Short-term memories are active for 24 hours. Semantic search ranks content; usage counts and query episodes adapt as you work. Exact duplicate entries are reused.')
    with st.form('memory'):
        content = st.text_area('Memory content')
        kind = st.selectbox('Memory type', ['short-term', 'long-term', 'semantic', 'episodic'])
        source = st.text_input('Memory source', 'User')
        if st.form_submit_button('Store memory', type='primary'):
            refresh(api('POST', '/memories', json=dict(content=content, kind=kind, source=source)))
    q = st.text_input('Find related memories')
    items = api('GET', '/memories', params={'q': q}) or []
    for item in items:
        with st.expander(f'{item["kind"]} · {item["content"][:75]}'):
            st.caption(f'Source: {item["source"]} · Accesses: {item["accesses"]} · Updated: {item["updated_at"]} · Relevance: {item.get("score", "—")}')
            with st.form('m'+str(item['id'])):
                text = st.text_area('Edit content', item['content'])
                if st.form_submit_button('Update memory'):
                    refresh(api('PUT', f'/memories/{item["id"]}', json=dict(content=text, kind=item['kind'], source=item['source'])))
            if st.button('Remove memory', key='rm'+str(item['id'])):
                refresh(api('DELETE', f'/memories/{item["id"]}'))
elif page in ['Knowledge Retrieval', 'Search & Chat']:
    st.subheader('Explore your evidence')
    def show_answer(result):
        st.caption('Retrieval engine: '+result['engine'])
        st.markdown('#### Retrieved evidence · original stored passages')
        for h in result['evidence']:
            with st.expander(f'[{h["document_id"]}] {h["title"]} · score {h["score"]}', expanded=True):
                st.write(h['passage'])
                st.caption(f'Source: {h["source"]} · Published: {h["published_at"] or "Unknown"}')
        st.markdown('#### Automatically assembled explanation')
        st.caption(result['explanation_type'])
        st.write(result['explanation'])
        with st.expander('Related memories'):
            st.dataframe(result['related_memories'], width="stretch")
    if page == 'Search & Chat':
        for message in st.session_state.get('chat', []):
            with st.chat_message(message['role']):
                st.write(message['content']) if message['role'] == 'user' else show_answer(message['content'])
        q = st.chat_input('Ask about your stored evidence')
        if q:
            result = api('POST', '/retrieve', json={'query': q})
            if result:
                st.session_state.setdefault('chat', []).extend([{'role':'user', 'content':q}, {'role':'assistant', 'content':result}])
                st.rerun()
    else:
        with st.form('query'):
            q = st.text_input('Natural-language research question')
            submit = st.form_submit_button('Retrieve evidence', type='primary')
        if submit:
            result = api('POST', '/retrieve', json={'query':q})
            if result:
                show_answer(result)
elif page == 'Evidence Updates':
    st.subheader('Evidence review desk')
    st.info('Newness and text overlap are screening signals. Conflicts and evidence quality require human judgment. Acceptance explicitly replaces the selected target text; rejection preserves it.')
    docs = api('GET', '/documents') or []
    with st.expander('Submit new evidence', expanded=True):
        with st.form('evidence'):
            fields = document_fields('ev')
            target = st.selectbox('Compare with existing record', [None]+[d['id'] for d in docs], format_func=lambda v: 'No target' if v is None else next(d['title'] for d in docs if d['id']==v))
            if st.form_submit_button('Compare & propose update', type='primary'):
                refresh(api('POST', '/evidence', json=dict(fields, target_id=target)))
    for e in api('GET', '/evidence') or []:
        with st.expander(f'Review #{e["id"]} · {e["status"]}', expanded=e['status']=='pending'):
            st.write(e['comparison'])
            for version in e['versions']:
                st.caption(f'{version["decision"]} · {version["created_at"]}')
                old, new = st.columns(2)
                old.text_area('Old evidence', version['old_content'], disabled=True, key=f'o{version["id"]}')
                new.text_area('New evidence', version['new_content'], disabled=True, key=f'n{version["id"]}')
            if e['status'] == 'pending':
                decision = st.radio('Human review decision', ['rejected', 'accepted'], key='decision'+str(e['id']))
                if st.button('Record review decision', key='review'+str(e['id'])):
                    refresh(api('POST', f'/evidence/{e["id"]}/review', json={'decision':decision}))

