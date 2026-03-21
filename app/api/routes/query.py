from typing import List, Optional, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.rag.pipeline import RAGPipeline

router = APIRouter()

_rag_pipeline = RAGPipeline()


class QueryRequest(BaseModel):
    question: str
    use_rlm: bool = False


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    chart: Dict[str, Any] | None = None


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Query the RAG pipeline or RLM for analysis and visualization."""
    
    if request.use_rlm:
        # Use the powerful RLM for deep analysis and charts
        result = await _rag_pipeline.query_rlm(request.question)
        
        if isinstance(result, dict) and result.get("type") == "chart":
            return QueryResponse(
                answer=f"AI generated a {result['payload'].get('type')} chart: {result['payload'].get('title')}",
                sources=["Full Statement Context"],
                chart=result["payload"]
            )
        else:
            return QueryResponse(
                answer=str(result),
                sources=["Full Statement Context"],
            )

    # Standard RAG Retrieve-and-Rank
    results = _rag_pipeline.query(request.question, top_k=3)
    
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
