# graph.py

from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
import anthropic

from app.intent_classifier import classify_intent
import chromadb
from sentence_transformers import SentenceTransformer
from app.dashboard import get_at_risk_files 

from app import config

import os
client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://aibootcamp-claude.services.ai.azure.com/anthropic"
)

# --- State definition ---
class AgentState(TypedDict):
    user_message: str
    history: Optional[List[dict]]
    role: Optional[str]
    intent: Optional[str]
    reason: Optional[str]
    referenced_pr_number: Optional[int]
    retrieved_chunks: Optional[List[dict]]
    final_answer: Optional[str]


# --- Shared resources (loaded once) ---
embed_model = SentenceTransformer(config.EMBEDDING_MODEL)
chroma_client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
collection = chroma_client.get_collection(config.CHROMA_COLLECTION_NAME)


# --- Nodes ---
def dashboard_node(state: AgentState) -> dict:
    at_risk = get_at_risk_files(top_n=5)

    if not at_risk:
        return {"final_answer": "No significant knowledge-risk areas found in the current indexed history."}

    lines = ["Top at-risk files, based on currently indexed commit/PR history (not real-time):\n"]
    for i, f in enumerate(at_risk, 1):
        lines.append(
            f"{i}. `{f['filename']}` — risk={f['risk_score']:.2f} "
            f"({f['pr_count']} PRs, {f['unique_authors']} contributors, "
            f"avg {f['avg_comments_per_pr']} comments/PR)"
        )

    return {"final_answer": "\n".join(lines)}

def classify_intent_node(state: AgentState) -> dict:
    trimmed_history = trim_history(state.get("history"))
    result = classify_intent(state["user_message"], history=trimmed_history)
    return {
        "intent": result["intent"],
        "reason": result["reason"],
        "referenced_pr_number": result.get("referenced_pr_number")
    }

def rag_retrieval_node(state: AgentState) -> dict:
    pr_number = state.get("referenced_pr_number")

    if pr_number:
        raw = collection.get(
            where={"pr_number": pr_number},
            include=["documents", "metadatas"]
        )
        chunks = [
            {"text": raw["documents"][i], "metadata": raw["metadatas"][i], "score": 1.0}
            for i in range(len(raw["ids"]))
        ]
        if chunks:
            return {"retrieved_chunks": chunks}
        # fall through to semantic search if exact PR not found

    query_embedding = embed_model.encode([state["user_message"]]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=8)

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],
        })
    return {"retrieved_chunks": chunks}

def clarify_node(state: AgentState) -> dict:
    return {"final_answer": state["reason"]}

# --- New node: graceful degrade ---
def graceful_degrade_node(state: AgentState) -> dict:
    return {"final_answer": "I couldn't find relevant history in the codebase to answer that. Try rephrasing, or ask about a specific file/PR/feature."}
    
# --- New node: generate answer from retrieved chunks ---
def generate_answer_node(state: AgentState) -> dict:
    chunks = state["retrieved_chunks"]

    # build context block from top chunks, each tagged with its source for citation
    context_blocks = []
    for c in chunks:
        meta = c["metadata"]
        source_label = meta.get("title") or meta.get("sha", "unknown")
        url = meta.get("url", "")
        context_blocks.append(f"[Source: {source_label} | {url}]\n{c['text']}")

    context_text = "\n\n---\n\n".join(context_blocks)

    prompt = f"""You are answering a question about why code was built or changed, using ONLY the context below, which comes from real GitHub PRs and commits.

Context:
{context_text}

Question: {state['user_message']}

Think step by step before answering:
1. Identify which sources in the context actually address the question.
2. Note any gaps — parts the context does NOT explain.
3. Only then, write the final answer.

Example:
Question: "Why does the linter skip generated files?"
Reasoning: PR #12 excludes files matching *_generated.py from linting because CI was failing on auto-generated code with false positives.
Answer: "According to PR #12, generated files are skipped because they triggered false-positive lint failures in CI."

Now answer the actual question below.

Instructions:
- Answer using only the information in the context above.
- If the context doesn't actually answer the question, say so honestly instead of guessing.
- Cite which PR/commit your answer comes from (e.g. "according to PR #5215...").
- Keep the answer concise, 3-5 sentences.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    answer = response.content[0].text
    return {"final_answer": answer}

MAX_HISTORY_MESSAGES = 6  # sliding window

def trim_history(history):
    if not history:
        return history
    return history[-MAX_HISTORY_MESSAGES:]

# --- Conditional routing function ---
def route_after_classify(state: AgentState) -> str:
    if state["intent"] == "knowledge_query":
        return "rag_retrieval"
    elif state["intent"] == "dashboard_query":
        if state.get("role") != "manager":
            return "access_denied"
        return "dashboard"
    else:
        return "clarify"
    
def access_denied_node(state: AgentState) -> dict:
    return {"final_answer": (
        "Access denied: the knowledge-risk dashboard requires the manager role. "
        "Your authenticated role is determined by your logged-in account, not by what you state in your message — "
        "so this can't be bypassed by claiming a different role. Try asking a knowledge question instead."
    )}
    # --- New routing after retrieval ---
RELEVANCE_THRESHOLD = 0.35  # tune this based on real testing

def route_after_retrieval(state: AgentState) -> str:
    chunks = state["retrieved_chunks"]
    if not chunks or chunks[0]["score"] < RELEVANCE_THRESHOLD:
        return "degrade"
    return "generate"

# --- Build the graph ---
graph = StateGraph(AgentState)

graph.add_node("classify_intent", classify_intent_node)
graph.add_node("rag_retrieval", rag_retrieval_node)
graph.add_node("generate_answer", generate_answer_node)
graph.add_node("clarify", clarify_node)
graph.add_node("dashboard", dashboard_node)
graph.add_node("degrade", graceful_degrade_node)

graph.set_entry_point("classify_intent")

graph.add_node("access_denied", access_denied_node)

graph.add_conditional_edges(
    "classify_intent",
    route_after_classify,
    {
        "rag_retrieval": "rag_retrieval",
        "dashboard": "dashboard",
        "clarify": "clarify",
        "access_denied": "access_denied"
    }
)

graph.add_edge("access_denied", END)
graph.add_conditional_edges(
    "rag_retrieval",
    route_after_retrieval,
    {"generate": "generate_answer", "degrade": "degrade"}
)

graph.add_edge("generate_answer", END)
graph.add_edge("clarify", END)
graph.add_edge("dashboard", END)
graph.add_edge("degrade", END)

app = graph.compile()


# --- Test run ---
if __name__ == "__main__":
    test_queries = [
        "why was bracket depth tracking added to Leaf",       # rag_query
        "show me at-risk knowledge areas",                     # dashboard_query
        "why is this broken",                                  # ambiguous -> clarify
    ]

    for q in test_queries:
        print(f"\n{'='*60}\nQuery: {q}")
        result = app.invoke({"user_message": q})
        print(f"Intent: {result['intent']}")
        print(f"Final Answer: {result['final_answer']}")

