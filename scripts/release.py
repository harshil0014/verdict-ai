"""Package tracked source and the local frontend build, after a private secret scan."""
import argparse,hashlib,json,subprocess,zipfile,re
from pathlib import Path
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def run():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    output=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT)
    names=sorted(set(p for p in output.decode().split('\0') if p))
    names += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'frontend/dist').rglob('*') if p.is_file()]
    names=sorted(set(names))
    private=dotenv_values(ROOT/'backend/.env')
    values=[v.encode() for k,v in private.items() if v and len(v)>=12 and (k.endswith('_KEY') or k.endswith('_SECRET') or k.endswith('_ID') or k=='VERDICT_OPERATOR_PASSWORD')]
    manifest={}
    for name in names:
        parts=Path(name).parts
        if any(p in ('.git','.venv','node_modules','runtime','work','__pycache__') for p in parts) or (Path(name).name.startswith('.env') and Path(name).name!='.env.example'):raise RuntimeError('Private path entered release inventory')
        data=(ROOT/name).read_bytes()
        if any(v in data for v in values) or re.search(rb'AIza[0-9A-Za-z_-]{35}|sb_secret_[0-9A-Za-z_-]{25,}',data):raise RuntimeError('Secret-like value detected; release refused (value withheld)')
        manifest[name]=sha(data)
    print(f'Secret scan passed for {len(names)} files. Private runtime and credential paths excluded.')
    if args.check_only:return
    if not args.output:raise RuntimeError('--output is required')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():raise RuntimeError('Tracked source has uncommitted changes')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(ROOT/name,'verdict-ai/'+name)
        z.writestr('verdict-ai/RELEASE-MANIFEST.json',json.dumps({'source_commit':commit,'files':manifest,'boundaries':'No credentials, runtime state, virtualenv or node_modules. Frontend build included. Backend dependency installation still required.'},indent=2))
    print(json.dumps({'archive':str(args.output),'source_commit':commit,'files':len(names),'bytes':args.output.stat().st_size,'sha256':sha(args.output.read_bytes())},indent=2))
if __name__=='__main__':run()
