from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List

from .agent_core import Agent, Plan, Step
from .config import Config
from .tool_registry import list_tools, get_tool
from .state import SessionState
from .nlg import summarize_results

# Import tools to register them
import cmpuse.tools


app = FastAPI(title="cmpuse API", version="0.1.0")


class Goal(BaseModel):
    tool: Optional[str] = None
    steps: Optional[list[dict]] = None
    args: Optional[dict] = None

class ChatRequest(BaseModel):
    message: str
    allow_shell: bool = False
    confirm: bool = False
    force: bool = False


def _auth(cfg: Config, token: Optional[str]):
    if cfg.api_auth_token and token != cfg.api_auth_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tools")
def tools():
    return {name: t.summary for name, t in list_tools().items()}


@app.post("/plan")
def plan(goal: Goal, authorization: Optional[str] = Header(None)):
    cfg = Config.from_env()
    _auth(cfg, authorization)
    agent = Agent(cfg)
    p = agent.plan(goal.model_dump(exclude_none=True))
    return {"steps": [s.__dict__ for s in p.steps]}


@app.post("/run")
def run(goal: Goal, force: bool = False, authorization: Optional[str] = Header(None)):
    cfg = Config.from_env()
    _auth(cfg, authorization)
    agent = Agent(cfg)
    p = agent.plan(goal.model_dump(exclude_none=True))
    res = agent.run(p, force=force)
    return res

@app.post("/chat")
def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    """Chat endpoint that plans and executes based on natural language message"""
    cfg = Config.from_env()
    _auth(cfg, authorization)

    agent = Agent(cfg)

    # Use the proper LLM-based planner for natural language processing
    from .planner_llm import propose_plan
    plan_items = propose_plan(request.message, max_steps=3)

    # Convert LLM plan to Step objects
    if plan_items:
        steps = [Step(tool=item["tool"], args=item.get("args", {})) for item in plan_items]
    else:
        # Fallback to basic mapping if LLM planner fails
        steps = [_map_step(request.message)]

    plan = Plan(steps=steps)

    # Execute if force is enabled, otherwise dry run
    if request.force and request.confirm:
        result = agent.run(plan, force=True)
    else:
        # Dry run - just return the plan
        result = [{"tool": step.tool, "args": step.args, "status": "dry-run"} for step in plan.steps]

    return {
        "planned": [{"tool": step.tool, "args": step.args} for step in plan.steps],
        "result": result,
        "text": summarize_results(plan_items, result) if plan_items else "Task completed."
    }


class AutoGoal(BaseModel):
    goal: str
    force: bool = False
    retries: int = 1
    timeout: float = 30.0
    backoff: float = 0.5
    backoff_factor: float = 2.0


def _map_step(text: str) -> Step:
    t = text.lower()

    # Boot repair
    if ("boot" in t) and ("repair" in t or "bcd" in t):
        return Step(tool="boot_repair", args={})

    # File operations
    if any(k in t for k in ["file", "directory", "folder", "list", "ls", "dir", "read", "write", "delete", "copy", "move", "create"]):
        return Step(tool="fs_ops", args={})

    # Web/Network operations
    if any(k in t for k in ["website", "url", "http", "download", "fetch", "web", "internet", "browse", "curl"]):
        return Step(tool="net_ops", args={})

    # Memory operations
    if any(k in t for k in ["remember", "memory", "learn", "forget", "store", "recall", "preference"]):
        return Step(tool="memory_system", args={})

    # JSON operations
    if "json" in t and "merge" in t:
        return Step(tool="json_ops", args={"operation": "merge", "a": {}, "b": {}})
    if "json" in t and any(k in t for k in ["validate", "lint", "check"]):
        return Step(tool="json_ops", args={"operation": "validate", "data": "{}"})

    # Creative/LLM tasks (use layered_planner for complex planning)
    if any(k in t for k in ["write", "poem", "story", "creative", "generate", "compose", "plan", "analyze", "explain"]):
        return Step(tool="layered_planner", args={"goal": text})

    # PowerShell/command execution
    if any(k in t for k in ["command", "execute", "run", "powershell", "cmd", "shell"]):
        return Step(tool="ps_exec", args={})

    # System information (default for many queries)
    if any(k in t for k in ["audit", "system", "info", "verify", "check", "time", "what time", "status", "hardware", "cpu", "memory", "disk"]):
        return Step(tool="sys_ops", args={})

    # Default fallback to system info
    return Step(tool="sys_ops", args={})


@app.post("/auto")
def auto(payload: AutoGoal, authorization: Optional[str] = Header(None)):
    cfg = Config.from_env()
    _auth(cfg, authorization)
    agent = Agent(cfg)

    lp = get_tool("layered_planner")
    steps_text: List[str] = []
    if lp:
        steps_text = lp.run({"goal": payload.goal}, dry_run=False).get("steps", [])
    steps = [_map_step(s) for s in steps_text] or [Step(tool="sys_ops", args={})]
    p = Plan(steps=steps)
    res = agent.run(
        p,
        force=payload.force,
        retries=payload.retries,
        timeout_sec=payload.timeout,
        backoff_initial=payload.backoff,
        backoff_factor=payload.backoff_factor,
    )
    return {
        "planned": [{"tool": s.tool, "args": s.args} for s in steps],
        "result": res,
    }


class ChatTurn(BaseModel):
    message: str
    allow_shell: bool = False
    confirm: bool = False
    force: bool = False


@app.post("/chat")
def chat(turn: ChatTurn, authorization: Optional[str] = Header(None)):
    cfg = Config.from_env()
    _auth(cfg, authorization)
    state = SessionState.load()
    user_msg = turn.message.strip()
    state.add("user", user_msg)

    # Naive intent mapping
    lower = user_msg.lower()
    steps: List[Step] = []
    if lower.startswith("run ") or lower.startswith("exec ") or lower.startswith("powershell "):
        cmd = user_msg.split(" ", 1)[1] if " " in user_msg else ""
        steps = [Step(tool="ps_exec", args={"command": cmd, "confirm": turn.confirm})]
    elif any(k in lower for k in ["system", "info", "status"]):
        steps = [Step(tool="sys_ops", args={})]
    elif "read file" in lower and "path=" in lower:
        # pattern: "read file path=C:\..."
        try:
            path = user_msg.split("path=", 1)[1].strip()
        except Exception:
            path = ""
        steps = [Step(tool="fs_ops", args={"operation": "read", "path": path})]
    else:
        # fallback: layered planner then sys_ops
        lp = get_tool("layered_planner")
        texts = lp.run({"goal": user_msg}, dry_run=False).get("steps", []) if lp else []
        steps = [Step(tool="sys_ops", args={})] if not texts else [Step(tool="sys_ops", args={}) for _ in texts]

    plan = Plan(steps=steps)
    agent = Agent(cfg)
    if turn.allow_shell:
        # allow_shell via env gate for ps_exec
        import os as _os
        _os.environ["CMPUSE_ALLOW_SHELL"] = "1"
    res = agent.run(plan, force=bool(turn.force))
    reply_text = summarize_results(res, turn.message)
    state.add("assistant", reply_text)
    return {
        "text": reply_text,
        "planned": [{"tool": s.tool, "args": s.args} for s in steps],
        "result": res,
    }


@app.get("/history")
def history(authorization: Optional[str] = Header(None)):
    cfg = Config.from_env()
    _auth(cfg, authorization)
    st = SessionState.load()
    return {"messages": [{"role": m.role, "content": m.content} for m in st.messages][-200:]}


@app.get("/")
def root():
    return RedirectResponse(url="/ui")


@app.get("/ui")
def ui() -> Response:
    html = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>cmpuse – Autonomous Agent</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, sans-serif; margin: 0; display: grid; grid-template-rows: auto 1fr auto; height: 100vh; }
    header { padding: 12px 16px; border-bottom: 1px solid #333; font-weight: 600; }
    main { display: grid; grid-template-columns: 280px 1fr; gap: 0; }
    aside { border-right: 1px solid #333; padding: 12px; }
    section { padding: 12px; display: grid; grid-template-rows: 1fr auto; }
    #chat { overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 10px; }
    .msg { max-width: 80%; padding: 8px 10px; border-radius: 10px; white-space: pre-wrap; }
    .user { align-self: flex-end; background: #2563eb; color: #fff; }
    .assistant { align-self: flex-start; background: #1f2937; color: #eee; }
    .system { align-self: center; opacity: 0.7; }
    .row { margin: 6px 0; }
    .muted { opacity: 0.8; font-size: 12px; }
    textarea { width: 100%; height: 6rem; }
    pre { background: #0b0b0b; color: #eee; padding: 8px; overflow: auto; border-radius: 8px; }
    input[type=text] { width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #444; }
    #composer { display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 8px; border-top: 1px solid #333; }
    button { padding: 8px 12px; border-radius: 8px; border: 1px solid #444; background: #374151; color: #fff; cursor: pointer; }
    button[disabled] { opacity: 0.6; cursor: not-allowed; }
  </style>
  <script>
    let allowShell=false, confirmAct=false, forceAct=false;
    function setToggle(id, cb){ const el=document.getElementById(id); el.addEventListener('change', ()=>cb(el.checked)); cb(el.checked); }
    function el(id){ return document.getElementById(id); }
    function addMsg(role, content){
      const wrap = el('chat');
      const div = document.createElement('div');
      div.className = 'msg ' + role;
      div.textContent = content;
      wrap.appendChild(div);
      wrap.scrollTop = wrap.scrollHeight;
    }
    async function loadHistory(){
      try{
        const resp = await fetch('/history');
        const data = await resp.json();
        el('chat').innerHTML = '';
        for (const m of data.messages){ addMsg(m.role, m.content); }
      }catch(e){ console.warn(e); }
    }
    async function runAuto() {
      const goal = document.getElementById('goal').value;
      const force = document.getElementById('force').checked;
      const retries = parseInt(document.getElementById('retries').value||'1');
      const timeout = parseFloat(document.getElementById('timeout').value||'30');
      const payload = { goal, force, retries, timeout };
      const btn = document.getElementById('runBtn');
      btn.disabled = true; btn.innerText = 'Running...';
      try {
        const resp = await fetch('/auto', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await resp.json();
        document.getElementById('out').textContent = JSON.stringify(data, null, 2);
        addMsg('assistant', 'Auto run complete.');
        loadHistory();
      } catch (e) {
        document.getElementById('out').textContent = String(e);
      } finally {
        btn.disabled = false; btn.innerText = 'Run';
      }
    }
    async function sendChat() {
      const msg = document.getElementById('chatmsg').value;
      const payload = { message: msg, allow_shell: allowShell, confirm: confirmAct, force: forceAct };
      const btn = document.getElementById('chatBtn');
      btn.disabled = true; btn.innerText = 'Sending...';
      try {
        addMsg('user', msg);
        document.getElementById('chatmsg').value='';
        const resp = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await resp.json();
        document.getElementById('chatout').textContent = JSON.stringify(data, null, 2);
        addMsg('assistant', 'Planned: ' + JSON.stringify(data.planned));
        addMsg('assistant', 'Result: ' + JSON.stringify(data.result));
        loadHistory();
      } catch (e) {
        document.getElementById('chatout').textContent = String(e);
      } finally {
        btn.disabled = false; btn.innerText = 'Send';
      }
    }
    function setupMic(){
      const btn = document.getElementById('micBtn');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition){ btn.disabled = true; btn.title = 'SpeechRecognition not supported'; return; }
      let rec=null;
      btn.addEventListener('click', ()=>{
        if (rec){ rec.stop(); rec=null; btn.textContent='🎤'; return; }
        rec = new SpeechRecognition();
        rec.lang = 'en-US';
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        rec.onresult = (e)=>{
          const text = e.results[0][0].transcript;
          document.getElementById('chatmsg').value = text;
        };
        rec.onend = ()=>{ btn.textContent='🎤'; rec=null; };
        rec.start(); btn.textContent='■';
      });
    }
    window.addEventListener('DOMContentLoaded', ()=>{
      setToggle('allowShell', v=>allowShell=v);
      setToggle('confirm', v=>confirmAct=v);
      setToggle('forceAct', v=>forceAct=v);
      setupMic();
      loadHistory();
      fetch('/tools').then(r=>r.json()).then(t=>{ document.getElementById('tools').textContent = JSON.stringify(t, null, 2); });
    });
  </script>
</head>
<body>
  <header>cmpuse — Autonomous Agent</header>
  <main>
    <aside>
      <div class=\"row\"><strong>Tools</strong></div>
      <pre id=\"tools\" class=\"muted\"></pre>
      <div class=\"row\"><strong>Auto</strong></div>
      <div class=\"row\"><textarea id=\"goal\" placeholder=\"Describe your goal...\">Audit disks. Repair boot config. Verify success.</textarea></div>
      <div class=\"row\">
        <label><input type=\"checkbox\" id=\"force\"/> Force</label>
        <label>Retries <input id=\"retries\" type=\"number\" min=\"0\" value=\"1\" style=\"width:4rem\"/></label>
        <label>Timeout(s) <input id=\"timeout\" type=\"number\" min=\"1\" value=\"30\" style=\"width:5rem\"/></label>
        <button id=\"runBtn\" onclick=\"runAuto()\">Run</button>
      </div>
      <pre id=\"out\" class=\"muted\"></pre>
    </aside>
    <section>
      <div id=\"chat\"></div>
      <div id=\"composer\"> 
        <input type=\"text\" id=\"chatmsg\" placeholder=\"Message cmpuse… Try: system info, run Get-Process, read file path=C:\\Temp\\a.txt\"/>
        <div>
          <button id=\"micBtn\" title=\"Dictate\">🎤</button>
          <label><input type=\"checkbox\" id=\"allowShell\"/> Allow Shell</label>
          <label><input type=\"checkbox\" id=\"confirm\"/> Confirm</label>
          <label><input type=\"checkbox\" id=\"forceAct\"/> Force</label>
          <button id=\"chatBtn\" onclick=\"sendChat()\">Send</button>
        </div>
      </div>
      <pre id=\"chatout\" class=\"muted\"></pre>
    </section>
  </main>
</body>
</html>
"""
    return Response(content=html, media_type="text/html")
