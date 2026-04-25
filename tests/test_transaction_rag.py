from src.web.transaction_rag import TransactionRAGPipeline


def _sample_transactions():
    return [
        {
            "id": 1,
            "date": "2026-01-03",
            "merchant": "Coffee Shop",
            "amount": 8.75,
            "account_name": "Credit Card",
        },
        {
            "id": 2,
            "date": "2026-01-04",
            "merchant": "Neighborhood Grocery",
            "amount": 54.12,
            "account_name": "Checking",
        },
        {
            "id": 3,
            "date": "2026-01-10",
            "merchant": "Monthly Payroll",
            "amount": -3200.00,
            "account_name": "Checking",
        },
    ]


def test_transaction_rag_builds_and_reuses_index(tmp_path):
    db_path = tmp_path / "transactions_vectors.sqlite3"
    pipeline = TransactionRAGPipeline(vector_db_path=db_path)

    first = pipeline.build_or_refresh_index(_sample_transactions(), force_rebuild=False)
    assert first["success"] is True
    assert first["indexed"] is True
    assert first["document_count"] == 3

    second = pipeline.build_or_refresh_index(_sample_transactions(), force_rebuild=False)
    assert second["success"] is True
    assert second["indexed"] is False
    assert second["document_count"] == 3


def test_transaction_rag_search_and_answer_without_llm(tmp_path):
    db_path = tmp_path / "transactions_vectors.sqlite3"
    pipeline = TransactionRAGPipeline(vector_db_path=db_path)
    pipeline.build_or_refresh_index(_sample_transactions(), force_rebuild=True)

    matches = pipeline.search("coffee spending", top_k=2)
    assert matches
    assert matches[0]["metadata"]["merchant"] == "Coffee Shop"

    answer = pipeline.ask("How much did I spend on coffee?", top_k=3, use_llm=False)
    assert answer["success"] is True
    assert answer["answer"]
    assert answer["citations"]
    assert answer["llm_used"] is False
