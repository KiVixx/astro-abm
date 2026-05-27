from __future__ import annotations

from fastapi import APIRouter

from astro_abm_api.models.llm import LLMTestRequest, LLMTestResponse
from astro_abm_api.services.llm_client import test_llm_connection


router = APIRouter()


@router.post("/llm/test", response_model=LLMTestResponse)
def test_llm(request: LLMTestRequest) -> LLMTestResponse:
    return test_llm_connection(request)
