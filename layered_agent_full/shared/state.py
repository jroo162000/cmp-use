import secrets, json
from typing import Dict, List
from shared.protocol import make_skill_schema, ChatMessage

class CommanderState:
    def __init__(self):
        self.history=[]
        self.workers={}
        self.skills={}
        self.tasks={}
        self.pending={}
        self.bearer_token=secrets.token_hex(16)
        self.function_schema=[]

    def register_worker(self,wid,info):
        self.workers[wid]=info
        self.tasks.setdefault(wid,[])
        for s in info.get("skills",[]): self.skills[s["name"]]=s
        self.function_schema=make_skill_schema(self.skills)

    def get_worker_with_skill(self,name):
        for wid,inf in self.workers.items():
            if any(s["name"]==name for s in inf.get("skills",[])): return wid
        return None

    def enqueue(self,wid,fc):
        tid=secrets.token_hex(8)
        task={"id":tid,"function":{"name":fc.name,"arguments":fc.arguments}}
        self.tasks.setdefault(wid,[]).append(task)
        self.pending[tid]={'worker':wid,'function':fc}
        return tid

    def fetch_tasks(self,wid): return self.tasks.pop(wid,[])

    def complete(self,tid,result):
        fc=self.pending.pop(tid)['function']
        self.history.append(ChatMessage(role="function",content=json.dumps({"task_id":tid,"result":result})))
        self.history=self.history[-20:]

    def snapshot(self):
        return {"workers":list(self.workers.values()),"skills":list(self.skills),"bearer_token":self.bearer_token,"layer":"L-3"}
