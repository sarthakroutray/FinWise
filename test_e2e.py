"""
End-to-end test for the FinWise AI pipeline.

Run:  python -m pytest test_e2e.py -v
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "FinWise" in data["app"]


def test_analyze_csv():
    csv_path = os.path.join(os.path.dirname(__file__), "test_data.csv")
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/analyze",
            data={"user_id": "test_user"},
            files={"file": ("test_data.csv", f, "text/csv")},
        )
    assert resp.status_code == 200, f"Analyze failed: {resp.text}"
    data = resp.json()

    # health_score
    hs = data["health_score"]
    assert 0 <= hs["score"] <= 100
    assert hs["grade"] in ("A", "B", "C", "D", "F")
    assert hs["forecast_trend"] in ("improving", "declining", "stable")

    # recommendations
    assert 3 <= len(data["recommendations"]) <= 6

    # anomalies
    for a in data["anomalies"]:
        assert "date" in a and "amount" in a

    # forecast — now List[{date, predicted_amount}]
    forecast = data["forecast"]
    assert len(forecast) == 30
    for pt in forecast:
        assert "date" in pt and "predicted_amount" in pt
        assert isinstance(pt["predicted_amount"], float)

    # transactions — new field
    txs = data["transactions"]
    assert len(txs) > 0
    for tx in txs:
        assert "date" in tx and "amount" in tx and "category" in tx

    # category_summary
    assert len(data["category_summary"]) > 0

    # extraction_meta
    meta = data["extraction_meta"]
    assert meta["method"] == "csv"
    assert meta["rows_extracted"] > 0
    assert 0 < meta["confidence"] <= 1.0

    print(f"Health: {hs['score']} ({hs['grade']}), Transactions: {len(txs)}, Forecast days: {len(forecast)}")


def test_extract_csv():
    csv_path = os.path.join(os.path.dirname(__file__), "test_data.csv")
    with open(csv_path, "rb") as f:
        resp = client.post("/extract", files={"file": ("test_data.csv", f, "text/csv")})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.content.decode("utf-8")
    lines = content.strip().split("\n")
    assert len(lines) > 1  # header + at least one data row
    header = lines[0].lower()
    assert "date" in header and "amount" in header


def test_query_after_analyze():
    # First upload to populate RAG
    csv_path = os.path.join(os.path.dirname(__file__), "test_data.csv")
    with open(csv_path, "rb") as f:
        client.post(
            "/analyze",
            data={"user_id": "test_user"},
            files={"file": ("test_data.csv", f, "text/csv")},
        )
    resp = client.post("/query", json={"question": "What is my top spending category?"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) > 0
    assert "No financial data" not in data["answer"]


def test_query_without_data():
    from app.rag.pipeline import RAGPipeline
    fresh = RAGPipeline()
    results = fresh.query("expenses?")
    assert "No documents" in results[0]


if __name__ == "__main__":
    import traceback
    for fn in [test_health_endpoint, test_analyze_csv, test_extract_csv, test_query_after_analyze, test_query_without_data]:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as e:
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
