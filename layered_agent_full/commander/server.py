import os, toml, pathlib, uuid, json, sys

# When executed directly ``python commander/server.py`` the package root is not
# on ``sys.path``. Adjust the path so absolute imports under ``layered_agent_full``
# work the same as when running as a module.
if __package__ in (None, ""):
    # Add the repository root so ``layered_agent_full`` package can be imported
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from layered_agent_full.shared.state import CommanderState
from layered_agent_full.shared.protocol import ChatMessage, FunctionCall
from layered_agent_full.shared.utils import aes_decrypt
from fastapi import FastAPI, Body, HTTPException, UploadFile, File, Header, Response
from pydantic import BaseModel
import openai

app = FastAPI()
state = CommanderState()

# Load OpenAI key
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    cfg = pathlib.Path.home()/".config"/"agent"/"secrets.toml"
    data = toml.loads(cfg.read_text()) if cfg.exists() else {}
    OPENAI_KEY = data.get("openai_api_key")
if not OPENAI_KEY:
    raise RuntimeError("Missing OpenAI API key.")
openai.api_key = OPENAI_KEY

class ChatIn(BaseModel):
    message: str

@app.post("/chat")
async def chat(inp: ChatIn):
    # record
    state.history.append(ChatMessage(role="user", content=inp.message))
    # call
    call_args={
        "model": "gpt-4o-mini",
        "messages": [m.model_dump() for m in state.history]
    }
    if state.function_schema:
        call_args.update(functions=state.function_schema, function_call="auto")
    resp = openai.chat.completions.create(**call_args)
    choice = resp.choices[0].message
    if choice.function_call:
        fc = choice.function_call
        # map
        fn_name = fc.name
        args = fc.arguments or {}
        # find worker
        wid = state.get_worker_with_skill(fn_name)
        if not wid:
            raise HTTPException(404, f"No worker for {fn_name}")
        task_id = state.enqueue(wid, fc)
        reply = f"\ud83d\udd27 Queued `{fn_name}` as `{task_id}` on {wid}"
    else:
        reply = choice.content or ""
    state.history.append(ChatMessage(role="assistant", content=reply))
    state.history = state.history[-20:]
    return {"reply": reply}

@app.get("/status")
def status():
    return state.snapshot()

@app.post("/register")
def register_worker(payload: dict = Body(...)):
    if payload.get("token") != state.bearer_token:
        raise HTTPException(401, "bad token")
    wid = payload.get("worker_id", str(uuid.uuid4()))
    payload["worker_id"] = wid
    state.register_worker(wid, payload)
    return {"worker_id": wid}

@app.get("/task/{worker_id}")
def get_task(worker_id: str, authorization: str|None=Header(None)):
    if authorization!=state.bearer_token: raise HTTPException(401)
    if worker_id not in state.workers: raise HTTPException(404)
    tasks=state.fetch_tasks(worker_id)
    if not tasks: return Response(status_code=204)
    return {"tasks": tasks}

@app.post("/result/{task_id}")
def post_result(task_id:str, body:dict=Body(...), authorization:str|None=Header(None)):
    if authorization!=state.bearer_token: raise HTTPException(401)
    payload=body.get("payload")
    vault=toml.loads((pathlib.Path.home()/".config"/"agent"/"secrets.toml").read_text()).get("vault_passphrase")
    try:
        result=json.loads(aes_decrypt(payload.encode(), vault))
    except:
        result=json.loads(payload)
    state.complete(task_id, result)
    return {"status":"ok"}

@app.post("/upload")
async def upload(file: UploadFile=File(...)):
    d=os.getcwd()+"/uploads"
    pathlib.Path(d).mkdir(exist_ok=True)
    dest=f"{d}/{file.filename}"
    c=await file.read()
    open(dest,"wb").write(c)
    return {"filename":file.filename, "size":len(c)}

if __name__=="__main__":
    import uvicorn, argparse
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=8000)
    a=p.parse_args()
    print(f"Listening on {a.port}, token={state.bearer_token}")
    uvicorn.run("layered_agent_full.commander.server:app", host="0.0.0.0", port=a.port)
