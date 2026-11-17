"""Pick the AI engine from settings: real Gemini, or the offline fake."""

from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "fake":
        from app.llm.fake import FakeProvider

        return FakeProvider(dim=s.gemini_embed_dim)
    from app.llm.gemini import GeminiProvider

    return GeminiProvider(
        api_key=s.gemini_api_key,
        model=s.gemini_model,
        embed_model=s.gemini_embed_model,
        dim=s.gemini_embed_dim,
    )
