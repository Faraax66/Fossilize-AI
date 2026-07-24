# main.py

from fastapi import FastAPI, Request, Header
from pydantic import BaseModel
from typing import List, Optional

from app.graph import app as agent_graph
from pr_guardian.detect import get_pr_context
from pr_guardian.retrieve import retrieve_context_for_pr
from pr_guardian.judge import judge_relevance
from pr_guardian.act import confirmation_gate
from app.guardrails import input_guardrail, output_guardrail

from app import config
import json

from fastapi.responses import FileResponse
from fastapi import BackgroundTasks
from pathlib import Path

_USERS = {
    u["id"]: u for u in json.loads((config.DATA_DIR / "users.json").read_text())
}

app = FastAPI(title="Fossilize AI")

def process_pr_guardian(pr_number: int):
    pr_context = get_pr_context(pr_number)
    file_contexts = retrieve_context_for_pr(pr_context)
    verdict = judge_relevance(pr_context, file_contexts)
    outcome = confirmation_gate(pr_number, verdict)
    print(f"[PR Guardian] PR #{pr_number} -> {outcome}")


# --- Request/response models ---
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    intent: str
    answer: str

class GitHubWebhookPayload(BaseModel):
    action: Optional[str] = None
    number: Optional[int] = None
    pull_request: Optional[dict] = None
    zen: Optional[str] = None  # present only on ping events


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")

# --- Health check ---
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/users")
def get_users():
    return list(_USERS.values())

# --- Chat endpoint ---

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_user_id: str = Header(default="", alias="X-User-Id")):
    user = _USERS.get(x_user_id)
    role = user["role"] if user else "engineer"

    is_safe, reason = input_guardrail(req.message)
    if not is_safe:
        return ChatResponse(intent="blocked", answer=f"This request can't be processed: {reason}")

    history = [{"role": m.role, "content": m.content} for m in (req.history or [])]
    result = agent_graph.invoke({"user_message": req.message, "history": history, "role": role})

    is_output_safe, out_reason = output_guardrail(result["final_answer"])
    if not is_output_safe:
        return ChatResponse(
            intent=result["intent"],
            answer="I generated a response but flagged it as potentially unreliable — please rephrase your question or ask me to verify a specific PR."
        )

    return ChatResponse(intent=result["intent"], answer=result["final_answer"])


# --- GitHub webhook endpoint (manual-test-ready) ---
@app.post("/webhook/github")
def github_webhook(payload: GitHubWebhookPayload, background_tasks: BackgroundTasks):
    if payload.zen is not None:
        return {"status": "pong", "zen": payload.zen}

    action = payload.action
    pr_number = payload.number or (payload.pull_request or {}).get("number")

    if action not in ("opened", "synchronize") or not pr_number:
        return {"status": "ignored", "reason": f"action={action}, pr_number={pr_number}"}

    background_tasks.add_task(process_pr_guardian, pr_number)
    return {"status": "accepted", "pr_number": pr_number}