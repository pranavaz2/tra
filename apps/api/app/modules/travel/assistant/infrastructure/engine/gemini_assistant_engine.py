"""Gemini Assistant Engine Implementation with Real-World Places Grounding."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from app.modules.travel.assistant.domain.enums import (
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.domain.value_objects import ChatMessage
from app.modules.travel.assistant.infrastructure.engine.base import (
    AssistantEngine,
    AssistantEngineResult,
    ProposedActionData,
)
from app.services.maps.base import PlaceDetails, PlacesProvider
from app.services.maps.route import RouteDetails, RoutingProvider
from app.shared.domain.errors import ExternalServiceError


logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_ASSISTANT_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "message": {
            "type": "STRING",
            "description": "Conversational assistant reply to the user.",
        },
        "response_type": {
            "type": "STRING",
            "enum": ["informational", "recommendation", "proposed_mutation"],
            "description": "Category of response.",
        },
        "proposed_action": {
            "type": "OBJECT",
            "properties": {
                "action_type": {
                    "type": "STRING",
                    "enum": [
                        "propose_itinerary_change",
                        "propose_adding_activity",
                        "propose_adding_place",
                        "propose_removing_activity",
                        "propose_rescheduling_activity",
                        "propose_replacing_activity",
                        "propose_reordering_activities",
                        "propose_adding_expense",
                        "propose_updating_budget_limit",
                        "propose_adjusting_budget",
                    ],
                },
                "summary": {"type": "STRING"},
                "description": {"type": "STRING"},
                "payload": {
                    "type": "OBJECT",
                    "properties": {
                        "day_id": {"type": "STRING"},
                        "day_number": {"type": "INTEGER"},
                        "item_id": {"type": "STRING"},
                        "old_item_id": {"type": "STRING"},
                        "title": {"type": "STRING"},
                        "place_name": {"type": "STRING"},
                        "item_type": {"type": "STRING"},
                        "description": {"type": "STRING"},
                        "start_time": {"type": "STRING"},
                        "end_time": {"type": "STRING"},
                        "cost": {"type": "STRING"},
                        "amount": {"type": "STRING"},
                        "limit_amount": {"type": "STRING"},
                        "category_id": {"type": "STRING"},
                        "expense_type": {"type": "STRING"},
                        "currency": {"type": "STRING"},
                        "rationale": {"type": "STRING"},
                        "travel_time_impact": {"type": "STRING"},
                        "budget_impact": {"type": "STRING"},
                    },
                },
            },
            "required": ["action_type", "summary", "description", "payload"],
        },
    },
    "required": ["message", "response_type"],
}


class GeminiAssistantEngine(AssistantEngine):
    """Gemini-powered conversational trip assistant with Google Places grounding & routing."""

    def __init__(
        self,
        api_key: str,
        places_provider: PlacesProvider,
        *,
        routing_provider: RoutingProvider | None = None,
        model: str = "gemini-2.0-flash",
        timeout_seconds: float = 45.0,
        temperature: float = 0.3,
        max_output_tokens: int = 2048,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._places_provider = places_provider
        self._routing_provider = routing_provider
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_system_instruction(self, context: dict[str, Any]) -> str:
        trip = context.get("trip", {})
        itinerary = context.get("itinerary", {})
        budget = context.get("budget", {})
        media = context.get("media", {})
        proactive_warnings = context.get("proactive_warnings", [])
        user_role = context.get("user_role", "viewer")

        context_str = json.dumps(
            {
                "trip": trip,
                "itinerary": itinerary,
                "budget": budget,
                "media_overview": media,
                "proactive_warnings": proactive_warnings,
                "user_role": user_role,
            },
            indent=2,
        )

        return (
            "You are the Travix AI trip assistant. You help travelers optimize, inspect, "
            "and modify their travel itinerary, places, and budget.\n\n"
            f"CURRENT TRIP CONTEXT:\n{context_str}\n\n"
            "CRITICAL GROUNDING AND SAFETY RULES:\n"
            "1. You NEVER directly modify databases or perform mutations autonomously.\n"
            "2. Never hallucinate places, fake coordinates, or fictitious venues. Only recommend real, authentic venues.\n"
            "3. When recommending or proposing a place, always specify the specific real-world venue name in 'place_name' and 'title'.\n"
            "4. If the user asks for a place or restaurant near Day N, use Day N's activities or destination context.\n"
            "5. If proposing a mutation (e.g. propose_adding_activity, propose_adding_place, propose_adding_expense), "
            "include a complete 'proposed_action' object and always ask for confirmation in the reply message.\n"
            "6. Match day_id and item_id accurately from the provided itinerary context.\n"
            "7. PROACTIVE WARNINGS: If there are proactive_warnings regarding schedule overlaps, travel feasibility/distance, or budget risks, explain them clearly and suggest realistic adjustments when asked."
        )

    async def _ground_place(
        self,
        place_name: str,
        destination: str,
        location_bias: tuple[float, float] | None = None,
    ) -> PlaceDetails | None:
        """Resolve a place name against the PlacesProvider."""
        if not place_name or not place_name.strip():
            return None

        clean_name = place_name.strip()
        query = f"{clean_name}, {destination}" if destination else clean_name
        try:
            candidates = await self._places_provider.text_search(query, location=location_bias)
            if not candidates:
                candidates = await self._places_provider.text_search(clean_name, location=location_bias)
            if candidates:
                return candidates[0]
        except Exception as exc:
            logger.warning("Places grounding failed for query '%s': %s", query, exc)

        return None

    async def chat(
        self,
        *,
        context: dict[str, Any],
        user_message: str,
        history: list[ChatMessage] | None = None,
    ) -> AssistantEngineResult:
        system_instruction = self._build_system_instruction(context)

        contents = []
        if history:
            for msg in history[-8:]:  # keep bounded recent turns
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        contents.append({"role": "user", "parts": [{"text": user_message}]})

        url = f"{_GEMINI_BASE_URL}/{self._model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self._api_key}

        body = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": self._temperature,
                "maxOutputTokens": self._max_output_tokens,
                "responseMimeType": "application/json",
                "responseSchema": _ASSISTANT_SCHEMA,
            },
        }

        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.post(url, params=params, headers=headers, json=body)
                if response.status_code == 429:
                    raise ExternalServiceError("Gemini rate limit reached.")
                if response.status_code != 200:
                    raise ExternalServiceError(
                        f"Gemini API returned status {response.status_code}: {response.text}"
                    )

                data = response.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)

                response_type = AssistantResponseType(parsed.get("response_type", "informational"))
                message = parsed.get("message", "")
                proposed_action_data: ProposedActionData | None = None
                tools_used: list[AssistantActionType] = [
                    AssistantActionType.READ_TRIP,
                    AssistantActionType.READ_ITINERARY,
                ]

                if response_type == AssistantResponseType.PROPOSED_MUTATION and "proposed_action" in parsed:
                    pa = parsed["proposed_action"]
                    action_type = AssistantActionType(pa["action_type"])
                    payload = dict(pa.get("payload", {}))

                    # If adding an activity / place, ground against PlacesProvider
                    if action_type in [
                        AssistantActionType.PROPOSE_ADDING_ACTIVITY,
                        AssistantActionType.PROPOSE_ADDING_PLACE,
                    ]:
                        tools_used.append(AssistantActionType.SEARCH_PLACES)
                        place_name = payload.get("place_name") or payload.get("title") or ""
                        destination = context.get("trip", {}).get("title", "")

                        verified_place = await self._ground_place(place_name, destination)
                        if verified_place:
                            payload["place_name"] = verified_place.name
                            payload["provider_place_id"] = verified_place.provider_place_id
                            payload["formatted_address"] = verified_place.formatted_address
                            payload["latitude"] = verified_place.latitude
                            payload["longitude"] = verified_place.longitude
                            payload["rating"] = verified_place.rating
                            payload["is_verified"] = True
                            if not payload.get("title"):
                                payload["title"] = verified_place.name
                            tools_used.append(AssistantActionType.PROPOSE_ADDING_PLACE)
                        else:
                            # If place cannot be verified, do not create fake place ID
                            payload["is_verified"] = False

                    proposed_action_data = ProposedActionData(
                        action_type=action_type,
                        summary=pa.get("summary", "Proposed change"),
                        description=pa.get("description", ""),
                        payload=payload,
                    )

                return AssistantEngineResult(
                    message=message,
                    response_type=response_type,
                    proposed_action=proposed_action_data,
                    tools_used=tuple(tools_used),
                )
            except Exception as exc:
                last_exc = exc
                logger.warning("Gemini Assistant attempt %d failed: %s", attempt, exc)

        raise ExternalServiceError(
            "Failed to communicate with AI Assistant service.", cause=last_exc
        )

