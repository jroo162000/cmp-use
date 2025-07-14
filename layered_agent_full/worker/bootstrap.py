#!/usr/bin/env python3
import os, sys, subprocess, venv, argparse
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

def install(f, verbose=False):
    pip=VENV/("Scripts/pip.exe" if os.name=="nt" else "bin/pip")
    cmd=[str(pip),"install","-r",str(f)]
    out=None if verbose else subprocess.DEVNULL
    res=subprocess.run(cmd, stdout=out, stderr=out)
    return res.returncode

def launch(s,l,t): os.execv(py(),[py(),str(Path(__file__).with_name("worker.py")),"--server",s,"--layer",l,"--token",t])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--server",required=True)
    p.add_argument("--token",required=True)
    p.add_argument("-v","--verbose",action="store_true",help="show pip output")
    a=p.parse_args()
    WORK.mkdir(exist_ok=True)
    ensure()
    rc_full=install(FULL,a.verbose)
    if rc_full==0:
        print("Installed full dependencies.")
        lay="L-3"
    else:
        print(f"Full install failed with code {rc_full}; installing minimal dependencies.")
        rc_min=install(MIN,a.verbose)
        print(f"Minimal install exited with code {rc_min}.")
        lay="L-2"
    launch(a.server,lay,a.token)

if __name__=="__main__": main()
