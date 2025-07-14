def skill(fn):
    fn._is_skill=True
    return fn

@skill
def run_shell(command:str,timeout:int=120):
    """Execute shell command"""
    import subprocess,platform,shlex
    shell=platform.system()=="Windows"
    cmd=shlex.split(command) if not shell else command
    p=subprocess.run(cmd,shell=shell,capture_output=True,text=True,timeout=timeout)
    return{"returncode":p.returncode,"stdout":p.stdout,"stderr":p.stderr}
