from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.firebase_auth import AuthUser, get_current_user
from app.db.documents_store import create_document, delete_document, list_documents

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentCreateRequest(BaseModel):
    """Request payload for creating a document metadata record."""

    filename: str = Field(min_length=1, max_length=512)
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    """Serialized document metadata record."""

    id: int
    user_uid: str
    filename: str
    mime_type: str | None = None
    metadata: dict[str, Any]
    created_at: str


class DeleteResponse(BaseModel):
    """Delete operation status."""

    deleted: bool


@router.get("", response_model=list[DocumentResponse])
def get_documents(user: AuthUser = Depends(get_current_user)) -> list[DocumentResponse]:
    """List all stored document metadata rows for the current user."""
    docs = list_documents(user.uid)
    return [DocumentResponse(**d) for d in docs]


@router.post("", response_model=DocumentResponse)
def add_document(payload: DocumentCreateRequest, user: AuthUser = Depends(get_current_user)) -> DocumentResponse:
    """Store one uploaded document metadata row for the current user."""
    try:
        saved = create_document(
            user_uid=user.uid,
            filename=payload.filename,
            mime_type=payload.mime_type,
            metadata=payload.metadata,
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "configured" in msg.lower() or "initialize neon database engine" in msg.lower():
            raise HTTPException(status_code=503, detail="Document storage is not configured") from exc
        if "json" in msg.lower() or "serialize" in msg.lower():
            raise HTTPException(status_code=422, detail="Invalid document metadata payload") from exc
        raise HTTPException(status_code=500, detail=f"Failed to create document metadata: {exc}") from exc
    return DocumentResponse(**saved)


@router.delete("/{document_id}", response_model=DeleteResponse)
def remove_document(document_id: int, user: AuthUser = Depends(get_current_user)) -> DeleteResponse:
    """Delete one user-owned document metadata row."""
    try:
        deleted = delete_document(user.uid, document_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to delete document metadata: {exc}") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return DeleteResponse(deleted=True)
