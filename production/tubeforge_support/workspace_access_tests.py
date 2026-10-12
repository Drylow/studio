"""Trusted portal identity, equal capabilities and direct-worker isolation."""
import base64,json,sys
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
if Path(__file__).parent.name=='tests':
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from app import workspace_access as access
    from app.workspace_identity import current_owner,identity
else:
    from . import workspace_access as access
    from .workspace_identity import current_owner,identity

TOKEN='fixture-private-connection-token-for-tests-only'

def header(uid='member',name='Team member'):
    return {'X-Worker-Token':TOKEN,'X-TubeForge-Member':base64.urlsafe_b64encode(json.dumps({'id':uid,'name':name}).encode()).decode().rstrip('=')}

@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setenv('TUBEFORGE_PROXY_TOKEN',TOKEN)
    monkeypatch.setenv('TUBEFORGE_REQUIRE_AUTH','1')
    app=FastAPI()
    @app.get('/api/project')
    async def project():return {'owner':current_owner()}
    @app.put('/api/settings')
    async def settings():return {'ok':True}
    @app.get('/')
    async def home():return {'html':'private worker'}
    access.install(app);access.install(app)
    return TestClient(app)

def test_missing_connection_fails_closed(monkeypatch):
    monkeypatch.delenv('TUBEFORGE_PROXY_TOKEN',raising=False)
    monkeypatch.setenv('TUBEFORGE_REQUIRE_AUTH','1')
    with pytest.raises(RuntimeError):access.install(FastAPI())

def test_local_studio_remains_optional(monkeypatch):
    monkeypatch.delenv('TUBEFORGE_PROXY_TOKEN',raising=False)
    monkeypatch.delenv('TUBEFORGE_REQUIRE_AUTH',raising=False)
    app=FastAPI();access.install(app)
    assert TestClient(app).get('/api/workspace/session').json()['username']=='admin'

def test_browser_cannot_access_worker_directly(gate):
    for headers in ({},{'X-Worker-Token':'wrong'},{'Authorization':'Basic fixture'},{'X-TubeForge-Member':header()['X-TubeForge-Member']}):
        assert gate.get('/api/project',headers=headers).status_code==401
        assert gate.get('/',headers=headers).status_code==401
    assert gate.get('/healthz').json()=={'status':'ok'}

def test_portal_members_have_equal_capabilities_and_separate_identity(gate):
    for uid in ('admin','worker-a','worker-b'):
        assert gate.get('/api/project',headers=header(uid)).json()['owner']==uid
        assert gate.put('/api/settings',headers=header(uid)).status_code==200
        session=gate.get('/api/workspace/session',headers=header(uid)).json()
        assert session['username']==uid and session['capabilities']=='full' and session['auth_mode']=='portal'
    assert identity.get() is None

def test_no_duplicate_login_or_account_registry(gate):
    for path in ('login','logout','team','team/example'):
        assert gate.post('/api/workspace/'+path,headers=header()).status_code==404
    assert 'password_hash' not in gate.get('/api/workspace/session',headers=header()).text

def test_malformed_identity_is_rejected(gate):
    for user in ({'id':'../admin','name':'Bad'},{'id':'admin','name':''},{'id':'admin','name':['bad']},{'id':'x'*129,'name':'Bad'}):
        h={'X-Worker-Token':TOKEN,'X-TubeForge-Member':base64.urlsafe_b64encode(json.dumps(user).encode()).decode()}
        assert gate.get('/api/project',headers=h).status_code==401
    assert gate.get('/api/project',headers={'X-Worker-Token':TOKEN,'X-TubeForge-Member':'%%%' }).status_code==401
