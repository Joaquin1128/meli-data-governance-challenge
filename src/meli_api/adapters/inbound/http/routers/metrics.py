from fastapi import APIRouter, Response

from meli_api.observability.metrics import CONTENT_TYPE_LATEST, render_metrics

router = APIRouter(tags=["observability"])


@router.get("/metrics")
def metrics() -> Response:
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
