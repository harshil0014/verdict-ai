"""HTTP account/security contracts. Actual PostgreSQL isolation is probed separately."""
import base64
import hashlib
import secrets
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import saas_app as application
import saas_auth as auth
from saas_store import CloudRepository, SESSION


@pytest.fixture
def account_client(monkeypatch):
    sessions, accounts, calls = {}, {}, []
    async def start(): pass
    async def close(): pass
    async def rpc(op,args=None,session=None):
        args=args or {}; session=SESSION.get() if session is None else session
        calls.append((op,args,session))
        if op=='health': return {'storage':'postgres'}
        if op=='rate': return {'allowed':True}
        if op=='register':
            if args['username'] in accounts: raise HTTPException(409,'That username is already in use')
            row={'id':secrets.token_hex(16),**args}; accounts[row['username']]=row; sessions[session]=row
            return {'id':row['id'],'username':row['username'],'display_name':row['display_name']}
        if op=='login_lookup': return accounts.get(args['username'])
        if op=='login_commit':
            row=accounts[args['username']]; sessions[session]=row
            return {'id':row['id']}
        if session not in sessions: raise HTTPException(401,'Sign in to continue')
        row=sessions[session]
        if op=='me': return {k:row[k] for k in ('id','username','display_name')}
        if op=='logout': del sessions[session]; return {'ok':True}
        if op=='list': return []
        if op=='file': return {'content':base64.b64encode(b'original').decode(),'mime':'text/plain','sha256':'incorrect'}
        raise HTTPException(404,'Record not found')
    monkeypatch.setattr(application.repo,'start',start)
    monkeypatch.setattr(application.repo,'close',close)
    monkeypatch.setattr(application.repo,'rpc',rpc)
    monkeypatch.setenv('VERDICT_AUTH_PEPPER','unit-test-pepper-is-not-a-real-secret')
    monkeypatch.setenv('VERDICT_SECURE_COOKIES','true')
    monkeypatch.setenv('VERDICT_PUBLIC_HOST','testserver')
    with TestClient(application.app,base_url='https://testserver') as c:
        yield c,accounts,calls


def register(c,**overrides):
    return c.post('/api/auth/register',json={'username':'unit_user','display_name':'Unit User','password':'unit-test-password-only',**overrides})


def test_signup_uses_real_password_hash_and_hashed_session(account_client):
    c,accounts,calls=account_client
    r=register(c)
    assert r.status_code==200
    assert accounts['unit_user']['password_hash'].startswith('$argon2id$')
    assert auth.passwords.verify('unit-test-password-only',accounts['unit_user']['password_hash'])
    raw=c.cookies.get(auth.COOKIE)
    assert next(item for item in calls if item[0]=='register')[2]==hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in str(calls)
    assert 'password_hash' not in r.text
    assert len(r.json()['recovery_code'])>=32
    assert accounts['unit_user']['recovery_hash']==auth.token_hash(r.json()['recovery_code'])


def test_signup_cookie_is_secure_private_and_http_only(account_client):
    c,_,_=account_client; r=register(c)
    header=r.headers['set-cookie'].lower()
    assert all(v in header for v in ('secure','httponly','samesite=lax'))
    assert 'no-store' in r.headers['cache-control']
    assert c.get('/api/me').json()['role']=='member'


@pytest.mark.parametrize('payload',[{'password':'short'},{'username':'a'},{'username':'bad@example.com'},{'display_name':'   '},{'owner_id':'forged'},{'email':'not-collected@example.invalid'}])
def test_registration_rejects_invalid_or_owner_fields(account_client,payload):
    c,_,_=account_client
    assert register(c,**payload).status_code==422


def test_no_demo_or_bootstrap_account_bypass(account_client):
    c,_,_=account_client
    assert c.post('/api/auth/demo').status_code==404
    assert c.post('/api/auth/login',json={'bootstrap':'not-an-account'}).status_code==422
    assert c.get('/api/cases').status_code==401


def test_wrong_password_and_unknown_user_have_same_error(account_client):
    c,_,_=account_client; register(c)
    a=c.post('/api/auth/login',json={'username':'unit_user','password':'incorrect-password'})
    b=c.post('/api/auth/login',json={'username':'missing_user','password':'incorrect-password'})
    assert a.status_code==b.status_code==401
    assert a.json()==b.json()


def test_logout_revokes_cookie_on_server(account_client):
    c,_,_=account_client; register(c)
    raw=c.cookies.get(auth.COOKIE)
    assert c.post('/api/auth/logout').status_code==200
    assert c.get('/api/me',headers={'Cookie':auth.COOKIE+'='+raw}).status_code==401


def test_explicit_cross_origin_and_host_are_refused(account_client):
    c,_,_=account_client
    assert c.post('/api/auth/login',headers={'Origin':'https://attacker.invalid'},json={}).status_code==403
    assert c.get('/api/config',headers={'Host':'attacker.invalid'}).status_code==400


def test_original_corruption_fails_closed(account_client):
    c,_,_=account_client; register(c)
    assert c.get('/api/cases/owned/files/corrupt').status_code==503


def test_payload_limit_and_security_headers(account_client):
    c,_,_=account_client
    assert c.post('/api/auth/login',headers={'Content-Length':'99999999'},content=b'{}').status_code==413
    r=c.get('/api/config')
    assert r.headers['x-frame-options']=='DENY'
    assert r.headers['x-content-type-options']=='nosniff'
    assert "frame-ancestors 'none'" in r.headers['content-security-policy']


def test_cloud_outage_has_no_local_fallback():
    import asyncio
    repository=CloudRepository()
    with pytest.raises(HTTPException) as error:
        asyncio.run(repository.rpc('list',session='a'*64))
    assert error.value.status_code==503


def test_mutation_is_revision_bound_and_hash_chained():
    repository=CloudRepository()
    body={'id':'V-'+'a'*16,'revision':4,'timeline':[{'hash':'previous'}],'audit_valid':True}
    result=repository.mutation(body,'test_event',{'message':'test'})
    assert result['expected_revision']==4 and result['body']['revision']==5
    assert result['audit']['previous']=='previous'
    assert 'timeline' not in result['body'] and 'audit_valid' not in result['body']
    assert result['audit']['hash']==hashlib.sha256(result['canonical_record'].encode()).hexdigest()


def test_public_accounts_cannot_dispatch_paypal_actions(account_client):
    c,_,_=account_client; register(c)
    assert c.post('/api/paypal/sync').status_code==409
    assert c.post('/api/cases/any/actions/execute').status_code==409


def test_chunked_request_limit_is_enforced_without_content_length():
    import asyncio
    from web_security import BoundedBodyMiddleware
    sent=[]
    messages=iter([{'type':'http.request','body':b'12345','more_body':True},
                   {'type':'http.request','body':b'67890','more_body':False}])
    async def receive(): return next(messages)
    async def send(message): sent.append(message)
    async def forbidden_app(scope,receive,send): raise AssertionError('Oversize stream reached the parser')
    asyncio.run(BoundedBodyMiddleware(forbidden_app,limit=8)({'type':'http','method':'POST'},receive,send))
    assert sent[0]['status']==413


def test_bounded_stream_replays_exact_original_bytes():
    import asyncio
    from web_security import BoundedBodyMiddleware
    messages=iter([{'type':'http.request','body':b'original-','more_body':True},
                   {'type':'http.request','body':b'bytes','more_body':False}])
    async def receive(): return next(messages)
    async def send(message): pass
    async def app(scope,receive,send):
        body=await receive()
        assert body['body']==b'original-bytes' and body['more_body'] is False
    asyncio.run(BoundedBodyMiddleware(app,limit=20)({'type':'http','method':'POST'},receive,send))
