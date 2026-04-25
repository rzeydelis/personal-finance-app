import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .llms import generate_json as llm_generate_json
except Exception:
    try:
        from llms import generate_json as llm_generate_json  # type: ignore
    except Exception:
        llm_generate_json = None  # type: ignore


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_VECTOR_SIZE = 512
DEFAULT_TOP_K = 8


def _tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


def _stable_hash_token(token: str) -> int:
    return int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], 16)


def _embed_text(text: str, vector_size: int) -> Dict[str, float]:
    counts: Dict[int, float] = defaultdict(float)
    for token in _tokenize(text):
        index = _stable_hash_token(token) % vector_size
        counts[index] += 1.0

    if not counts:
        return {}

    norm = math.sqrt(sum(value * value for value in counts.values()))
    if norm == 0:
        return {}

    return {
        str(index): value / norm
        for index, value in counts.items()
    }


def _cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0

    if len(a) > len(b):
        a, b = b, a

    dot = 0.0
    for key, value in a.items():
        other = b.get(key)
        if other is not None:
            dot += value * other
    return dot


def _transaction_text(transaction: Dict[str, Any]) -> str:
    date = str(transaction.get("date") or "unknown-date")
    merchant = str(
        transaction.get("merchant")
        or transaction.get("name")
        or transaction.get("description")
        or "unknown-merchant"
    ).strip()
    amount = float(transaction.get("amount") or 0.0)
    account = str(transaction.get("account_name") or transaction.get("account") or "unknown-account").strip()
    category = str(transaction.get("category") or transaction.get("subcategory") or "").strip()
    direction = "expense" if amount >= 0 else "income_or_credit"
    amount_display = f"${amount:,.2f}"
    return (
        f"Date: {date}. Merchant: {merchant}. Amount: {amount_display}. "
        f"Direction: {direction}. Account: {account}. Category: {category or 'uncategorized'}."
    )


def _transaction_doc_id(transaction: Dict[str, Any]) -> str:
    signature = "|".join(
        [
            str(transaction.get("id") or ""),
            str(transaction.get("date") or ""),
            str(transaction.get("merchant") or transaction.get("name") or ""),
            f"{float(transaction.get('amount') or 0.0):.2f}",
            str(transaction.get("account_name") or transaction.get("account") or ""),
        ]
    )
    return "tx_" + hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]


def _dataset_fingerprint(transactions: List[Dict[str, Any]]) -> str:
    signatures: List[str] = []
    for transaction in transactions:
        signatures.append(
            "|".join(
                [
                    str(transaction.get("date") or ""),
                    str(transaction.get("merchant") or transaction.get("name") or ""),
                    f"{float(transaction.get('amount') or 0.0):.2f}",
                    str(transaction.get("account_name") or transaction.get("account") or ""),
                ]
            )
        )
    signatures.sort()
    content = "\n".join(signatures)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class LocalVectorStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    doc_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def replace_documents(self, documents: List[Dict[str, Any]]):
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM vectors")
            rows = [
                (
                    document["doc_id"],
                    document["content"],
                    json.dumps(document["vector"]),
                    json.dumps(document["metadata"]),
                    now,
                )
                for document in documents
            ]
            conn.executemany(
                """
                INSERT INTO vectors (doc_id, content, vector_json, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def fetch_documents(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT doc_id, content, vector_json, metadata_json FROM vectors"
            ).fetchall()

        documents = []
        for row in rows:
            try:
                vector = json.loads(row["vector_json"])
                metadata = json.loads(row["metadata_json"])
            except Exception:
                continue
            documents.append(
                {
                    "doc_id": row["doc_id"],
                    "content": row["content"],
                    "vector": vector,
                    "metadata": metadata,
                }
            )
        return documents

    def count_documents(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM vectors").fetchone()
            return int(row["count"]) if row else 0

    def get_meta(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            return row["value"]

    def set_meta(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute("REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value))


class TransactionRAGPipeline:
    def __init__(self, vector_db_path: Path, vector_size: int = DEFAULT_VECTOR_SIZE):
        self.vector_size = max(128, int(vector_size))
        self.store = LocalVectorStore(vector_db_path)

    def build_or_refresh_index(
        self,
        transactions: List[Dict[str, Any]],
        force_rebuild: bool = False,
    ) -> Dict[str, Any]:
        if not transactions:
            return {
                "success": False,
                "indexed": False,
                "document_count": 0,
                "error": "No transactions to index.",
            }

        fingerprint = _dataset_fingerprint(transactions)
        existing_fingerprint = self.store.get_meta("source_fingerprint")
        existing_count = self.store.count_documents()

        if (not force_rebuild) and existing_fingerprint == fingerprint and existing_count == len(transactions):
            return {
                "success": True,
                "indexed": False,
                "document_count": existing_count,
                "error": None,
            }

        documents = []
        for transaction in transactions:
            content = _transaction_text(transaction)
            metadata = {
                "date": str(transaction.get("date") or ""),
                "merchant": str(
                    transaction.get("merchant")
                    or transaction.get("name")
                    or transaction.get("description")
                    or ""
                ),
                "amount": float(transaction.get("amount") or 0.0),
                "account": str(transaction.get("account_name") or transaction.get("account") or ""),
            }
            documents.append(
                {
                    "doc_id": _transaction_doc_id(transaction),
                    "content": content,
                    "vector": _embed_text(content, self.vector_size),
                    "metadata": metadata,
                }
            )

        self.store.replace_documents(documents)
        self.store.set_meta("source_fingerprint", fingerprint)
        self.store.set_meta("indexed_at", datetime.utcnow().isoformat())
        self.store.set_meta("document_count", str(len(documents)))

        return {
            "success": True,
            "indexed": True,
            "document_count": len(documents),
            "error": None,
        }

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []

        documents = self.store.fetch_documents()
        if not documents:
            return []

        query_vector = _embed_text(query, self.vector_size)
        if not query_vector:
            return []

        scored = []
        for document in documents:
            score = _cosine_sparse(query_vector, document.get("vector", {}))
            if score <= 0:
                continue
            scored.append(
                {
                    "doc_id": document["doc_id"],
                    "score": score,
                    "content": document["content"],
                    "metadata": document.get("metadata", {}),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(1, min(int(top_k), 20))]

    def ask(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        use_llm: bool = False,
        openai_api_key: Optional[str] = None,
        use_openai: bool = False,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        matches = self.search(query, top_k=top_k)
        if not matches:
            return {
                "success": True,
                "answer": "I could not find relevant transactions in the local index for that question.",
                "citations": [],
                "confidence": "low",
                "matches": [],
                "llm_used": False,
                "llm_error": None,
            }

        compact_matches = []
        for match in matches:
            metadata = match.get("metadata", {})
            compact_matches.append(
                {
                    "doc_id": match["doc_id"],
                    "score": round(float(match["score"]), 4),
                    "date": metadata.get("date"),
                    "merchant": metadata.get("merchant"),
                    "amount": metadata.get("amount"),
                    "account": metadata.get("account"),
                    "content": match.get("content"),
                }
            )

        fallback_answer = self._build_fallback_answer(query, compact_matches)
        citations = [match["doc_id"] for match in compact_matches[:3]]

        if use_llm and llm_generate_json:
            llm_result = self._answer_with_llm(
                query=query,
                matches=compact_matches,
                openai_api_key=openai_api_key,
                use_openai=use_openai,
                model=model,
            )
            if llm_result.get("success"):
                llm_data = llm_result.get("data", {})
                llm_citations = llm_data.get("citations") or citations
                if isinstance(llm_citations, list):
                    llm_citations = [str(item) for item in llm_citations if isinstance(item, (str, int))]
                else:
                    llm_citations = citations
                return {
                    "success": True,
                    "answer": llm_data.get("answer") or fallback_answer,
                    "citations": llm_citations,
                    "confidence": llm_data.get("confidence") or "medium",
                    "matches": compact_matches,
                    "llm_used": True,
                    "llm_error": None,
                }

            return {
                "success": True,
                "answer": fallback_answer,
                "citations": citations,
                "confidence": "medium",
                "matches": compact_matches,
                "llm_used": True,
                "llm_error": llm_result.get("error"),
            }

        return {
            "success": True,
            "answer": fallback_answer,
            "citations": citations,
            "confidence": "medium",
            "matches": compact_matches,
            "llm_used": False,
            "llm_error": None,
        }

    def _answer_with_llm(
        self,
        query: str,
        matches: List[Dict[str, Any]],
        openai_api_key: Optional[str],
        use_openai: bool,
        model: Optional[str],
    ) -> Dict[str, Any]:
        context_lines = []
        for match in matches:
            context_lines.append(
                (
                    f"[{match['doc_id']}] date={match.get('date')} merchant={match.get('merchant')} "
                    f"amount={match.get('amount')} account={match.get('account')} "
                    f"content={match.get('content')}"
                )
            )

        system_prompt = (
            "You are a personal finance assistant. Answer only with evidence from the retrieved transactions. "
            "If evidence is weak, say so."
        )
        prompt = f"""
Question:
{query}

Retrieved transactions:
{chr(10).join(context_lines)}

Return ONLY valid JSON in this shape:
{{
  "answer": "short answer using the retrieved transactions only",
  "citations": ["doc_id_1", "doc_id_2"],
  "confidence": "high|medium|low"
}}
"""
        try:
            return llm_generate_json(  # type: ignore
                prompt=prompt,
                model=model,
                system=system_prompt,
                openai_api_key=openai_api_key,
                use_openai=use_openai,
                timeout_seconds=90,
            )
        except Exception as exc:
            return {"success": False, "data": None, "raw_text": "", "error": str(exc)}

    @staticmethod
    def _build_fallback_answer(query: str, matches: List[Dict[str, Any]]) -> str:
        if not matches:
            return "I could not find relevant transactions for that question."

        amount_values = [abs(float(item.get("amount") or 0.0)) for item in matches]
        total = sum(amount_values)
        largest = max(matches, key=lambda item: abs(float(item.get("amount") or 0.0)))
        merchant_counts = Counter([str(item.get("merchant") or "Unknown") for item in matches])
        top_merchant, top_merchant_hits = merchant_counts.most_common(1)[0]

        amounts_sorted = sorted(amount_values, reverse=True)
        median_amount = amounts_sorted[len(amounts_sorted) // 2] if amounts_sorted else 0.0

        return (
            f"For '{query}', I found {len(matches)} relevant transactions. "
            f"The retrieved total is ${total:,.2f}, median amount is ${median_amount:,.2f}, "
            f"largest match is {largest.get('merchant')} on {largest.get('date')} "
            f"for ${abs(float(largest.get('amount') or 0.0)):,.2f}. "
            f"Most frequent merchant in the results is {top_merchant} ({top_merchant_hits} hits)."
        )
