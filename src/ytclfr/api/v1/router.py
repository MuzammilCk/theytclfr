from fastapi import APIRouter
from ytclfr.api.v1.health import router as health_router
from ytclfr.api.v1.jobs import router as jobs_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(jobs_router)
