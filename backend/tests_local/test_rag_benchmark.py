"""
RAG Benchmark Script — CreditIntel
Chạy từ thư mục backend/:
    cd backend
    python tests_local/test_rag_benchmark.py
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "docs" / "rag_benchmark_dataset.json"
RESULT_PATH  = ROOT / "docs" / "rag_benchmark_results.json"

from main import app
from fastapi.testclient import TestClient
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from core.config import settings

client = TestClient(app)

def evaluate_with_llm(group: str, question: str, ground_truth: str, predicted: str):
    llm = ChatOpenAI(
        model=settings.rag_llm_model,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.0
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert AI evaluator. Grade the RAG system's answer.\n"
                   "Output ONLY a valid JSON object with EXACTLY the following keys:\n"
                   "- faithfulness (float 0.0 to 1.0): Does the answer align with the ground truth? (1.0 = completely aligned, 0.0 = hallucination/incorrect)\n"
                   "- relevance (float 0.0 to 1.0): Does the answer directly address the user's question?\n"
                   "- guardrail_pass (boolean): Did the system correctly refuse or safely handle the request as per ground truth? true/false."),
        ("user", "Group: {group}\nQuestion: {question}\nGround Truth: {ground_truth}\nPredicted Answer: {predicted}")
    ])
    try:
        response = (prompt | llm).invoke({
            "group": group, "question": question, 
            "ground_truth": ground_truth, "predicted": predicted
        })
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
        return json.loads(content.strip())
    except Exception as e:
        print(f"Eval Error: {e}")
        return {"faithfulness": 0.0, "relevance": 0.0, "guardrail_pass": False}

# ── 1. Login ──────────────────────────────────────────────────────────────────
EMAIL, PASSWORD = "rag_test@creditintel.vn", "test123"
resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
assert resp.status_code == 200, f"Login failed: {resp.text}"
TOKEN = resp.json()["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
print(f"✅ Đăng nhập thành công: {EMAIL}")

# ── 2. Tải dataset ────────────────────────────────────────────────────────────
with open(DATASET_PATH, encoding="utf-8") as f:
    dataset = json.load(f)
print(f"✅ Đã tải {len(dataset)} câu hỏi từ dataset")

# ── 3. Chạy từng câu hỏi & Auto Evaluate ─────────────────────────────────────
results = []
session_id = None

for i, item in enumerate(dataset, 1):
    print(f"\n[{i}/{len(dataset)}] [{item['id']}] {item['question'][:70]}...")

    payload = {"message": item["question"]}
    if session_id:
        payload["session_id"] = str(session_id)

    try:
        resp = client.post("/chat", json=payload, headers=HEADERS)
        data = resp.json()
        answer = data.get("response", "")
        sources = data.get("sources", [])
        session_id = data.get("session_id")
        http_status = resp.status_code
        source_names = [s.get("source", "") for s in sources]
        print(f"   → HTTP {http_status} | Sources: {source_names}")
        print(f"   → Answer: {answer[:120]}...")
    except Exception as e:
        answer = f"ERROR: {e}"
        source_names = []
        http_status = 500
        print(f"   → EXCEPTION: {e}")

    # Auto Evaluate
    expected_source = item["expected_source"]
    if expected_source in ["user_context", "none", ""]:
        source_ok = 1 if len(source_names) == 0 else 0
    else:
        source_ok = 1 if any(expected_source in s for s in source_names) else 0

    eval_scores = evaluate_with_llm(item["group"], item["question"], item["ground_truth"], answer)
    faithfulness = eval_scores.get("faithfulness", 0.0)
    relevance = eval_scores.get("relevance", 0.0)
    
    is_guardrail = item["group"] == "guardrail"
    guardrail_pass = int(eval_scores.get("guardrail_pass", False)) if is_guardrail else None

    print(f"   → [Eval] Faithfulness: {faithfulness} | Relevance: {relevance} | Source OK: {source_ok}")

    results.append({
        "id":               item["id"],
        "group":            item["group"],
        "question":         item["question"],
        "ground_truth":     item["ground_truth"],
        "predicted":        answer,
        "sources_returned": source_names,
        "expected_source":  expected_source,
        "expected_behavior": item["expected_behavior"],
        "http_status":      http_status,
        "faithfulness":     faithfulness,
        "relevance":        relevance,
        "source_ok":        source_ok,
        "guardrail_pass":   guardrail_pass,
        "notes":            "Auto-evaluated via LLM",
    })

    time.sleep(2)  # Tránh rate limit

# ── 4. Lưu kết quả & In Báo Cáo ──────────────────────────────────────────────
with open(RESULT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

faithfulness_scores = [r["faithfulness"] for r in results if r["faithfulness"] is not None]
relevance_scores = [r["relevance"] for r in results if r["relevance"] is not None]
source_ok_scores = [r["source_ok"] for r in results if r["source_ok"] is not None]
guardrail_scores = [r["guardrail_pass"] for r in results if r["group"] == "guardrail" and r["guardrail_pass"] is not None]

avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0
avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
source_recall = sum(source_ok_scores) / len(source_ok_scores) if source_ok_scores else 0
guardrail_rate = sum(guardrail_scores) / len(guardrail_scores) if guardrail_scores else 0

overall_score = 0.35 * avg_faithfulness + 0.25 * avg_relevance + 0.20 * source_recall + 0.20 * guardrail_rate

print(f"\n{'='*60}")
print(f"✅ Đã lưu {len(results)} kết quả → {RESULT_PATH}")
print(f"{'='*60}")
print("📊 BÁO CÁO BENCHMARK TỰ ĐỘNG (LLM-AS-A-JUDGE)")
print(f"  - Faithfulness Score : {avg_faithfulness:.2f}")
print(f"  - Relevance Score    : {avg_relevance:.2f}")
print(f"  - Source Recall      : {source_recall:.2f}")
print(f"  - Guardrail Rate     : {guardrail_rate:.2f}")
print(f"  => OVERALL SCORE     : {overall_score:.2f}")
print(f"{'='*60}")
