"""Recover a public decision by neutral citation, never by an invented URL.

Publisher authorities are configured; individual decisions are discovered through
the existing public search APIs. Identity matching is not legal truth checking or
proof that the inaccessible copy is byte-for-byte identical.
"""
import re
import base64
import hashlib
from urllib.parse import urljoin
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from public_web import normalize_url, RetrievalError

RECOVERY_VERSION=3
PUBLISHERS={'BCCRT':{'name':'British Columbia Civil Resolution Tribunal',
    'host':'decisions.civilresolutionbc.ca','help_url':'https://civilresolutionbc.ca/help/how-do-i-search-crt-decisions/'}}
TRACKING_KEYS={'utm_source','utm_medium','utm_campaign','utm_term','utm_content'}


def automatic_url(value):
    url=normalize_url(value)
    p=urlsplit(url)
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() not in TRACKING_KEYS]
    if any(k.lower() not in ('id','article','document','lang','language','page') for k,v in query):
        raise RetrievalError('sensitive_reference','The link has query parameters requiring review; it was not opened automatically.')
    return urlunsplit((p.scheme,p.netloc,p.path,urlencode(query),''))


def decision_identity(url):
    try:p=urlsplit(automatic_url(url))
    except RetrievalError:return None
    if p.hostname not in ('www.canlii.org','canlii.org'):return None
    m=re.fullmatch(r'/[a-z]{2}/[a-z]{2}/([a-z]{2,12})/doc/(20\d{2})/\2([a-z]{2,12})([1-9]\d{0,5})/(20\d{2}[a-z]{2,12}[1-9]\d{0,5})\.html',p.path,re.I)
    if not m or m[1].upper()!=m[3].upper():return None
    court=m[1].upper();year=m[2];number=m[4]
    if court not in PUBLISHERS:return None
    expected_slug=year+court.lower()+number
    if m[5].lower()!=expected_slug:return None
    return {'citation':f'{year} {court} {number}','court':court,'year':year,'number':number,
        'publisher':PUBLISHERS[court]['name'],'publisher_host':PUBLISHERS[court]['host']}


def recovery_query(identity):
    # Only a structured public citation and configured authority leave the case.
    return f'"{identity["citation"]}" {identity["publisher"]} official decision'


def publisher_candidates(documents,identity,blocked_url):
    result=[];seen={blocked_url}
    for doc in documents:
        try:url=automatic_url(doc.get('url',''))
        except (RetrievalError,TypeError):continue
        if url in seen or urlsplit(url).hostname!=identity['publisher_host']:continue
        seen.add(url);result.append({'url':url,'title':str(doc.get('title',''))[:200],
            'provider':str(doc.get('provider','Public search API'))[:100]})
        if len(result)==2:break
    return result


def check_decision(draft,identity):
    metadata=draft.get('metadata',{})
    result={'expected_citation':identity['citation'],'publisher_host':identity['publisher_host'],
        'status':'not_matched','basis':'Official publisher + document self-identification + exact neutral citation in the preserved header.',
        'text_sha256':metadata.get('text_sha256'),'byte_equivalence_to_blocked_copy':'not_verified'}
    if draft.get('status')!='ready':return {**result,'reason':'No readable source content was retrieved.'}
    if urlsplit(metadata.get('final_url','')).hostname!=identity['publisher_host']:
        return {**result,'reason':'The retrieved final host is not the configured original publisher.'}
    header=draft.get('text','')[:1800]
    indexed=re.search(r'Indexed\s+as\s*:\s*([^\n]{3,200}?),\s*(20\d{2})\s+([A-Z]{2,12})\s+([1-9]\d{0,5})\b',header,re.I)
    if not indexed:return {**result,'reason':'The preserved header has no explicit indexed case name and neutral citation.'}
    observed=f'{indexed[2]} {indexed[3].upper()} {indexed[4]}'
    result.update(observed_citation=observed,document_title=indexed[1].strip(),
        identity_passage=indexed.group(),passage_start=indexed.start(),passage_end=indexed.end())
    if observed!=identity['citation']:return {**result,'reason':'The retrieved decision has a different neutral citation.'}
    if not re.search(r'Civil\s+Resolution\s+Tribunal',header,re.I) or not re.search(r'REASONS\s+FOR\s+DECISION',header,re.I):
        return {**result,'reason':'The header does not identify itself as tribunal reasons for decision.'}
    if not metadata.get('publication_date'):
        return {**result,'reason':'No explicit issued date was established in the preserved decision.'}
    return {**result,'status':'matched','issued_date':metadata['publication_date'],
        'reason':'The exact neutral citation is in the original publisher’s preserved decision header.'}


def publisher_embed(draft,identity):
    """One explicit same-document publisher frame; never arbitrary page links.

    The wrapper snapshot remains staged. Only its literal iframe src, with the
    same HTTPS host/path and exactly iframe=true, may supply a document candidate.
    """
    meta=draft.get('metadata',{});url=meta.get('final_url','');p=urlsplit(url)
    if draft.get('status')!='ready' or meta.get('mime')!='text/html' or p.scheme!='https' or p.hostname!=identity['publisher_host'] or p.query:
        return None
    try:
        # PostgreSQL encode(bytea,'base64') wraps lines at 76 characters.
        raw=base64.b64decode(''.join(draft.get('content','').split()),validate=True)
        if len(raw)>5*1024*1024 or hashlib.sha256(raw).hexdigest()!=draft.get('raw_sha256'):return None
        from lxml import html
        tree=html.fromstring(raw)
        for value in tree.xpath('//iframe/@src'):
            target=normalize_url(urljoin(url,value));q=urlsplit(target)
            if (q.scheme,q.netloc,q.path)==(p.scheme,p.netloc,p.path) and q.query=='iframe=true':
                return {'url':target,'provider':'Explicit same-document publisher iframe',
                    'publisher_wrapper':{'url':url,'draft_id':draft['id'],'raw_sha256':draft['raw_sha256'],
                        'text_sha256':meta.get('text_sha256'),'retrieved_at':meta.get('retrieved_at')}}
    except (ValueError,RetrievalError):pass
    return None
