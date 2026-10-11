"""AI structured output parsers.

LangChain PydanticOutputParser constrains model output to a JSON schema;
normalize/default helpers below provide fallbacks when model output is unstable.
"""

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from backend.constants import AI_RECOMMENDATION_PROVIDER_TAGS

ALLOWED_INTENTS = [
    "casual_chat",
    "provider_search",
    "review_summary",
    "unknown",
]
ALLOWED_BUDGET_PREFERENCES = ["cheap", "quality", "balanced", None]
ALLOWED_URGENCIES = ["today", "tomorrow", "this_week", "flexible", None]


class IntentClassificationResult(BaseModel):
    intent: str = Field(description="User intent")
    confidence: float = Field(default=0, description="Intent confidence from 0 to 1")
    reason: str | None = Field(default=None, description="Brief English reason")


class ServiceNeedExtractionResult(BaseModel):
    service_tags: list[str] = Field(default_factory=list, description="Service tags")
    service_province: str | None = Field(default=None, description="Service province/region")
    max_price: float | None = Field(default=None, description="User budget ceiling")
    budget_preference: str | None = Field(default=None, description="Price preference")
    quality_preference: bool = Field(default=False, description="Whether quality is prioritized")
    urgency: str | None = Field(default=None, description="Urgency level")


intent_parser = PydanticOutputParser(
    pydantic_object=IntentClassificationResult,
)
service_need_parser = PydanticOutputParser(
    pydantic_object=ServiceNeedExtractionResult,
)


def get_default_intent_result(reason: str = "Model output could not be parsed"):
    return {
        "intent": "unknown",
        "confidence": 0,
        "reason": reason,
    }


def get_default_service_need_result():
    return {
        "service_tags": [],
        "service_province": None,
        "max_price": None,
        "budget_preference": None,
        "quality_preference": False,
        "urgency": None,
    }


def normalize_intent_result(result: IntentClassificationResult):
    intent = result.intent

    if intent not in ALLOWED_INTENTS:
        intent = "unknown"

    confidence = max(0, min(result.confidence, 1))

    return {
        "intent": intent,
        "confidence": confidence,
        "reason": result.reason,
    }


def normalize_service_need_result(result: ServiceNeedExtractionResult):
    service_tags = result.service_tags or []
    service_tags = [
        tag for tag in service_tags if tag in AI_RECOMMENDATION_PROVIDER_TAGS
    ]

    budget_preference = result.budget_preference

    if budget_preference not in ALLOWED_BUDGET_PREFERENCES:
        budget_preference = None

    urgency = result.urgency

    if urgency not in ALLOWED_URGENCIES:
        urgency = None

    return {
        "service_tags": service_tags,
        "service_province": result.service_province,
        "max_price": result.max_price,
        "budget_preference": budget_preference,
        "quality_preference": result.quality_preference,
        "urgency": urgency,
    }
