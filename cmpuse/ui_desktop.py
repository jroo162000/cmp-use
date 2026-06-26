from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

from .agent_core import Agent, Plan, Step
from .intents import map_message_to_steps
from .tts import speak
from .voice import VoiceLoop
from .nlg import summarize_results


class ChatView(tk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, bg="#0b0b0b")
        self.canvas = tk.Canvas(self, bg="#0b0b0b", bd=0, highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg="#0b0b0b")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def add_message(self, role: str, text: str) -> None:
        wrap = tk.Frame(self.inner, bg="#0b0b0b")
        wrap.pack(fill=tk.X, pady=4, padx=8)
        bubble_bg = "#2563eb" if role == "you" else ("#1f2937" if role == "agent" else "#374151")
        fg = "#ffffff" if role == "you" else "#e5e7eb"
        anchor = "e" if role == "you" else "w"
        bubble = tk.Label(wrap, text=text, bg=bubble_bg, fg=fg, padx=10, pady=8, wraplength=700, justify=tk.LEFT)
        bubble.pack(anchor=anchor, padx=10)
        self.after(10, lambda: self.canvas.yview_moveto(1))


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CMPUSE – Local Agent")
        self.root.geometry("960x640")

        # Chat area
        self.chat = ChatView(root)
        self.chat.pack(fill=tk.BOTH, expand=True)

        frm = tk.Frame(root)
        frm.pack(fill=tk.X)

        self.entry = tk.Entry(frm)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)

        self.allow_shell = tk.IntVar(value=0)
        self.confirm = tk.IntVar(value=0)
        self.force = tk.IntVar(value=0)
        self.speak = tk.IntVar(value=0)
        self.use_llm = tk.IntVar(value=1)
        self.use_llm_plan = tk.IntVar(value=1)

        tk.Checkbutton(frm, text="Allow Shell", variable=self.allow_shell).pack(side=tk.LEFT)
        tk.Checkbutton(frm, text="Confirm", variable=self.confirm).pack(side=tk.LEFT)
        tk.Checkbutton(frm, text="Force", variable=self.force).pack(side=tk.LEFT)
        tk.Checkbutton(frm, text="Speak", variable=self.speak).pack(side=tk.LEFT)
        tk.Checkbutton(frm, text="Use LLM", variable=self.use_llm).pack(side=tk.LEFT)
        tk.Checkbutton(frm, text="LLM Plan", variable=self.use_llm_plan).pack(side=tk.LEFT)

        tk.Button(frm, text="Send", command=self.on_send).pack(side=tk.LEFT, padx=4)
        self.voice_btn = tk.Button(frm, text="Start Voice", command=self.toggle_voice)
        self.voice_btn.pack(side=tk.LEFT, padx=4)

        self.agent = Agent()
        self.voice: VoiceLoop | None = None

    def log(self, role: str, msg: str) -> None:
        self.chat.add_message(role, msg)

    def on_send(self) -> None:
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, tk.END)
        self.log("you", msg)

        # Environment gate for shell
        if self.allow_shell.get():
            os.environ["CMPUSE_ALLOW_SHELL"] = "1"
        else:
            if "CMPUSE_ALLOW_SHELL" in os.environ:
                os.environ.pop("CMPUSE_ALLOW_SHELL", None)

        # Decide steps: LLM plan or heuristic intents
        if self.use_llm_plan.get():
            try:
                from .planner_llm import propose_plan
                plan_items = propose_plan(msg)
                if plan_items:
                    steps = [Step(tool=i.get('tool'), args=i.get('args', {})) for i in plan_items]
                else:
                    steps = map_message_to_steps(msg)
            except Exception:
                steps = map_message_to_steps(msg)
        else:
            steps = map_message_to_steps(msg)
        # Inject confirm flag into step args if present
        for s in steps:
            if self.confirm.get():
                s.args.setdefault("confirm", True)

        plan = Plan(steps=steps)
        try:
            res = self.agent.run(plan, force=bool(self.force.get()), retries=1, timeout_sec=30)
            reply = summarize_results(res, msg)
        except Exception as e:
            reply = f"I hit an error while executing your request: {e}"
        # If using LLM, append an answer to user's message for general Q&A
        if self.use_llm.get():
            try:
                from .llm import answer, is_configured
                if is_configured():
                    llm_text = answer(msg)
                    if llm_text:
                        reply = llm_text if reply.strip() == "Done." else f"{reply}\n\n{llm_text}"
                else:
                    self.log("system", "LLM not configured. Set OPENAI_API_KEY.")
            except Exception as e:
                self.log("system", f"LLM error: {e}")
        self.log("agent", reply)

        if self.speak.get():
            # speak a short summary
            speak(reply, allow_shell=bool(self.allow_shell.get()))

    def handle_voice(self, utter: str) -> None:
        # Called from background thread; schedule on main thread
        self.root.after(0, self._handle_voice_main, utter)

    def _handle_voice_main(self, utter: str) -> None:
        self.log("voice", utter)
        # Reuse on_send logic path: map intents and run
        if self.allow_shell.get():
            os.environ["CMPUSE_ALLOW_SHELL"] = "1"
        else:
            os.environ.pop("CMPUSE_ALLOW_SHELL", None)
        if self.use_llm_plan.get():
            try:
                from .planner_llm import propose_plan
                plan_items = propose_plan(utter)
                if plan_items:
                    steps = [Step(tool=i.get('tool'), args=i.get('args', {})) for i in plan_items]
                else:
                    steps = map_message_to_steps(utter)
            except Exception:
                steps = map_message_to_steps(utter)
        else:
            steps = map_message_to_steps(utter)
        for s in steps:
            if self.confirm.get():
                s.args.setdefault("confirm", True)
        plan = Plan(steps=steps)
        try:
            res = self.agent.run(plan, force=bool(self.force.get()), retries=1, timeout_sec=30)
            reply = summarize_results(res, utter)
        except Exception as e:
            reply = f"I hit an error while executing your request: {e}"
        if self.use_llm.get():
            try:
                from .llm import answer, is_configured
                if is_configured():
                    llm_text = answer(utter)
                    if llm_text:
                        reply = llm_text if reply.strip() == "Done." else f"{reply}\n\n{llm_text}"
            except Exception as e:
                self.log("system", f"LLM error: {e}")
        self.log("agent", reply)
        if self.speak.get():
            speak(reply, allow_shell=bool(self.allow_shell.get()))

    def toggle_voice(self) -> None:
        if self.voice is None:
            # Start voice
            loop = VoiceLoop(wake_word="ava", on_utterance=self.handle_voice)
            ok = loop.start()
            if not ok:
                self.log("system", "SpeechRecognition not available. Install it: pip install SpeechRecognition pyaudio")
                return
            self.voice = loop
            self.voice_btn.configure(text="Stop Voice")
            self.log("system", "Voice listening started. Say 'AVa ...' to command.")
        else:
            self.voice.stop()
            self.voice = None
            self.voice_btn.configure(text="Start Voice")
            self.log("system", "Voice listening stopped.")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
