"""Trust the existing portal session; TubeForge has no separate user database."""
import base64
import hmac
import json
import os
import re
from fastapi.responses import JSONResponse
from .workspace_identity import identity


def install(app):
    if getattr(app.state, 'workspace_access_installed', False):
        return
    token = os.environ.get('TUBEFORGE_PROXY_TOKEN', '')
    if not token:
        if os.environ.get('TUBEFORGE_REQUIRE_AUTH') == '1':
            raise RuntimeError('Hosted TubeForge requires the trusted portal connection token')
        @app.get('/api/workspace/session')
        async def local_session():
            return {'username':'admin','display_name':'Local studio','hosted':False,'capabilities':'full'}
        return
    if len(token) < 32:
        raise RuntimeError('Use a strong private portal connection token')

    @app.middleware('http')
    async def portal_identity(request, call_next):
        if request.url.path == '/healthz' and request.method == 'GET':
            return JSONResponse({'status':'ok'})
        supplied = request.headers.get('x-worker-token', '')
        if len(supplied) > 512 or not hmac.compare_digest(supplied.encode(), token.encode()):
            return JSONResponse({'detail':'Open TubeForge from tools.kanye.studio.'},401,headers={'Cache-Control':'no-store'})
        try:
            encoded = request.headers.get('x-tubeforge-member','')
            if len(encoded) > 2048:
                raise ValueError()
            member = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
            uid, name = member['id'], member['name']
            if not isinstance(uid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',uid):
                raise ValueError()
            if not isinstance(name,str) or not 1 <= len(name) <= 100:
                raise ValueError()
        except (ValueError,TypeError,KeyError,UnicodeError):
            return JSONResponse({'detail':'A valid portal member is required.'},401)
        user = {'username':uid,'display_name':name,'hosted':True,'auth_mode':'portal','capabilities':'full'}
        request.state.workspace_user = user
        if request.url.path == '/api/workspace/session' and request.method == 'GET':
            return JSONResponse(user,headers={'Cache-Control':'no-store'})
        if request.url.path in ('/api/workspace/login','/api/workspace/logout','/api/workspace/team') or request.url.path.startswith('/api/workspace/team/'):
            return JSONResponse({'detail':'Accounts and sessions are managed by the existing portal.'},404)
        marker = identity.set(user)
        try:
            return await call_next(request)
        finally:
            identity.reset(marker)
    app.state.workspace_access_installed = True
