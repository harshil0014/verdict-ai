"""Audit Git object history and the publication tree without logging secret values.

Uses exact local private values plus generic credential signatures. Pair this with
an independent Gitleaks scan. Ignored local runtime is inventoried, never exported.
"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DENIED = {'.venv','venv','node_modules','runtime','work','__pycache__','.pytest_cache','.ruff_cache','.git'}
PATTERNS = {
    'google_api_key': rb'AIza[0-9A-Za-z_-]{35}',
    'github_token': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'supabase_secret': rb'sb_secret_[A-Za-z0-9_-]{25,}',
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'aws_access_key': rb'AKIA[0-9A-Z]{16}',
    'jwt': rb'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',
}

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    private=dotenv_values(ROOT/'backend/.env')
    known={k:v.encode() for k,v in private.items() if v and len(v)>=12 and any(s in k for s in ('KEY','SECRET','PASSWORD','CLIENT_ID'))}
    if private.get('SUPABASE_URL'):
        known['private_supabase_project']=urlparse(private['SUPABASE_URL']).hostname.split('.')[0].encode()
    local_url=ROOT/'runtime/local-access.url'
    if local_url.exists():known['local_bootstrap']=local_url.read_text().split('bootstrap=')[-1].strip().encode()
    hosted=ROOT/'runtime/hosted-demo-private.json'
    if hosted.exists():
        for key,value in json.loads(hosted.read_text(encoding='utf-8')).items():
            if value:known['hosted_'+key]=value.encode()
    dispute=ROOT/'runtime/private-dispute-id.json'
    for name in ('saas-deploy-private.json','saas-acceptance-private.json','saas-security-private.json','saas-ui-private.json'):
        path=ROOT/'runtime'/name
        if path.exists():
            def collect_saas(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if isinstance(item,str) and len(item)>=12 and (key in ('username','password','recovery_code','portal_token','case_id','original_id','witness_id') or key.startswith('VERDICT_')):
                            known['saas_private_'+str(len(known))]=item.encode()
                        collect_saas(item)
                elif isinstance(value,list):
                    for item in value:collect_saas(item)
            collect_saas(json.loads(path.read_text(encoding='utf-8')))
    if dispute.exists():
        known['private_dispute_id']=json.loads(dispute.read_text(encoding='utf-8'))['dispute_id'].encode()
    session=ROOT/'runtime/private-local-session.json'
    if session.exists():
        for key,value in json.loads(session.read_text(encoding='utf-8')).items():
            if value:known['local_session_'+key]=value.encode()
    checkout=ROOT/'runtime/sandbox-checkout.json'
    if checkout.exists():
        def private_fields(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in ('id','order_id','email_address','merchant_id','payer_id') and isinstance(item,str) and len(item)>=8:
                        known['private_checkout_'+str(len(known))]=item.encode()
                    private_fields(item)
            elif isinstance(value,list):
                for item in value:private_fields(item)
        private_fields(json.loads(checkout.read_text(encoding='utf-8')))
    findings=[]
    def check(label,content):
        for name,value in known.items():
            if value and value in content:findings.append({'location':label,'rule':'exact_private_'+name})
        for name,pattern in PATTERNS.items():
            if re.search(pattern,content):findings.append({'location':label,'rule':name})
    objects=[line.split() for line in git('cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype)').decode().splitlines()]
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    count=0
    for oid,kind in objects:
        if kind not in ('blob','commit','tag'):continue
        process.stdin.write((oid+'\n').encode());process.stdin.flush()
        header=process.stdout.readline().decode().split();size=int(header[2])
        content=process.stdout.read(size);process.stdout.read(1)
        check('git-object:'+oid,content);count+=1
    process.stdin.close();process.wait()
    paths=set(git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0'))-{''}
    public_paths=[]
    for path in sorted(paths):
        p=Path(path)
        if any(x in DENIED for x in p.parts) or (p.name.startswith('.env') and p.name!='.env.example'):
            findings.append({'location':path,'rule':'private_path_in_publication_tree'})
        check('worktree:'+path,(ROOT/path).read_bytes());public_paths.append(path)
    for commit in git('rev-list','--all','--reflog').decode().splitlines():
        for path in git('ls-tree','-r','--name-only','-z',commit).decode().split('\0'):
            if not path:continue
            p=Path(path)
            if any(x in DENIED for x in p.parts) or (p.name.startswith('.env') and p.name!='.env.example'):
                findings.append({'location':'history:'+commit+':'+path,'rule':'historical_private_path'})
    ignore={}
    for path in ['backend/.env','backend/.venv/example','runtime/local-access.url','work/audit-tools/gitleaks.exe','frontend/node_modules/example','frontend/dist/index.html','.ruff_cache/example','private.pem','debug.log']:
        result=subprocess.run(['git','check-ignore','-q','--no-index',path],cwd=ROOT)
        ignore[path]=result.returncode==0
        if result.returncode!=0:findings.append({'location':path,'rule':'missing_ignore_rule'})
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'git_objects_scanned_including_unreachable':count,'working_files_scanned':len(public_paths),'commits_and_reflogs_checked':len(set(git('rev-list','--all','--reflog').decode().splitlines())),'ignore_checks':ignore,'finding_count':len(findings),'findings':findings,'scope':'All local Git blob/commit/tag objects, every reachable/reflog commit path, and all nonignored publication files. Local credentials/runtime remain excluded. Findings omit values.'}
    folder=ROOT/'work/publication-audit';folder.mkdir(parents=True,exist_ok=True)
    (folder/'exact-and-generic.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if findings:raise SystemExit(1)

if __name__=='__main__':main()
