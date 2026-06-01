"""AI 模型注册表与配置。"""
from __future__ import annotations

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

deepseek = OpenAIChatModel(
    "deepseek-v4-flash",
    provider=OpenAIProvider(
        api_key="",
        base_url="",
    ),
)

# mimo = OpenAIChatModel(
#     "mimo-v2.5-pro",
#     provider=OpenAIProvider(
#         api_key="",
#         base_url="",
#     ),
# )

MODEL_OPTIONS = {
    # "Mimo": mimo,
    "DeepSeek": deepseek,
}

MODEL_REGISTRY = {
    # "openai:mimo-v2.5-pro": mimo,
    "openai:deepseek-v4-flash": deepseek,
}

DEFAULT_MODEL = deepseek
DEFAULT_SYSTEM_PROMPT = "中文回复，并称呼用户为老大"


def get_model_by_id(model_id: str | None) -> OpenAIChatModel:
    return MODEL_REGISTRY.get(model_id or "", DEFAULT_MODEL)
