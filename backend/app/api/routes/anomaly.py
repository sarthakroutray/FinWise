from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_anomalies():
    """Placeholder for anomaly detection route."""
    return {"message": "Anomaly route is under construction"}
