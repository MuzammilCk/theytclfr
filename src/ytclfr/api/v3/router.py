from fastapi import APIRouter

from ytclfr.api.v3.jobs import router as jobs_router
from ytclfr.api.v3.results import router as results_router

v3_router = APIRouter()
v3_router.include_router(jobs_router)
v3_router.include_router(results_router)
