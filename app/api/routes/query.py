from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from app.rag.pipeline import RAGPipeline

router = APIRouter()

_rag_pipeline = RAGPipeline()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Query the RAG pipeline with a natural language question."""
    results = _rag_pipeline.query(request.question, top_k=3)
    # Compose answer from retrieved documents
    if not results or results[0].startswith("No documents"):
        return QueryResponse(
            answer="No financial data available yet. Please upload a bank statement first.",
            sources=[],
        )
    answer_parts = [
        f"Based on your financial data, here are the most relevant findings:",
    ]
    for i, doc in enumerate(results, 1):
        answer_parts.append(f"{i}. {doc}")
    return QueryResponse(
        answer="\n".join(answer_parts),
        sources=results,
    )
