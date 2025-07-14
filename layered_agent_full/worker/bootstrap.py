#!/usr/bin/env python3
import os,sys,subprocess,venv,argparse
from pathlib import Path
# config
HOME=Path.home()
WORK=HOME/".agent"
VENV=WORK/"venv"
FULL=Path(__file__).parent.parent/"requirements.txt"
MIN=Path(__file__).parent.parent/"requirements-minimal.txt"

def py(): return str(VENV/("Scripts/python.exe" if os.name=="nt" else "bin/python"))
def ensure():
    if not Path(py()).exists(): venv.create(VENV,with_pip=True)

def install(f):
    pip=VENV/("Scripts/pip.exe" if os.name=="nt" else "bin/pip")
    try: subprocess.check_call([str(pip),"install","-r",str(f)]);return True
    except: return False

def launch(s,l,t): os.execv(py(),[py(),str(Path(__file__).with_name("worker.py")),"--server",s,"--layer",l,"--token",t])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--server",required=True)
    p.add_argument("--token",required=True)
    a=p.parse_args()
    WORK.mkdir(exist_ok=True)
    ensure()
    lay="L-3" if install(FULL) else "L-2";install(MIN) if lay=="L-2" else None
    launch(a.server,lay,a.token)

if __name__=="__main__": main()
