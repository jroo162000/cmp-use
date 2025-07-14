#!/usr/bin/env python3
import argparse,importlib.util,inspect,sys,platform,time,traceback,base64,hashlib,json,requests,os,logging
from pathlib import Path
from layered_agent_full.plugin_manager import PluginManager
# logging
L=Path.home()/".agent"/"logs";L.mkdir(parents=True,exist_ok=True)
logging.basicConfig(filename=L/"worker.log",level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
# helpers
def discover():
    sk={}
    for f in (Path(__file__).parent/"skills").glob("*.py"):
6vfos9-codex/run-all-code-from-the-repo
=======
c6btom-codex/run-all-code-from-the-repo
=======
w55z61-codex/run-all-code-from-the-repo
main
main
        if f.stem=="__init__":continue
        spec=importlib.util.spec_from_file_location(f.stem,f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
=======
        if f.stem=="__init__":
            continue
        spec=importlib.util.spec_from_file_location(
            "layered_agent_full.worker.skills." + f.stem,
            f,
        )
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
main
        for n,fn in inspect.getmembers(m,inspect.isfunction):
            if getattr(fn,"_is_skill",False): sk[n]=fn
    return sk
def manifest(sk):
    return [{"name":n,"description":fn.__doc__ or "","parameters":{}} for n,fn in sk.items()]
def encrypt(o,p):
    r=json.dumps(o).encode()
    if not p:
        return r.decode()
    key=hashlib.sha256(p.encode()).digest()
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(key)).encrypt(r).decode()

# plugin support
PM=PluginManager()
skills={}

def refresh_skills(pm:PluginManager=PM):
    """Reload built-in and plugin skills."""
    global skills
    base=discover()
    base.update(pm.discover_plugins())
    skills=base
    return skills

# main
parser=argparse.ArgumentParser();parser.add_argument("--server",required=True);parser.add_argument("--layer",required=True,choices=["L-2","L-3"]);parser.add_argument("--token",required=True);args=parser.parse_args()
skills=refresh_skills();man=manifest(skills)
# register
try:
    r=requests.post(f"{args.server}/register",json={"token":args.token,"os":platform.system().lower(),"layer":args.layer,"skills":man},timeout=15)
    r.raise_for_status();wid=r.json().get("worker_id");print("Registered",wid)
except Exception as e:sys.exit(f"Reg failed: {e}")
# poll
while True:
    try:
        h={"Authorization":args.token}
        resp=requests.get(f"{args.server}/task/{wid}",headers=h,timeout=15)
        if resp.status_code==204: time.sleep(10);continue
        resp.raise_for_status();t=resp.json();tid=t["id"];fn=t["function"]["name"];kw=t["function"]["arguments"]
        try:res=skills[fn](**kw);st="success"
        except Exception:res={"trace":traceback.format_exc()};st="error"
        body={"payload":encrypt({"worker_id":wid,"task_id":tid,"status":st,"result":res},os.getenv("VAULT_PASSPHRASE"))}
        r2=requests.post(f"{args.server}/result/{tid}",json=body,headers=h,timeout=15);r2.raise_for_status()
    except Exception as e:logging.exception("poll err");time.sleep(15)
