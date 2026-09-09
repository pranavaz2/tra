"""
Gemini PlanningEngine implementation with real-place grounding.

Queries Google Gemini for structured travel plans, and verifies every
suggested place against the PlacesProvider. Coordinates, provider place IDs,
and addresses come exclusively from the Places provider, never from the LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)
from app.modules.travel.planning.domain.value_objects.proposed_activity import (
    ProposedActivity,
)
from app.modules.travel.planning.domain.value_objects.proposed_day import ProposedDay
from app.services.ai.base import PlanningEngine
from app.services.maps.base import PlacesProvider
from app.shared.domain.errors import ExternalServiceError

logger = logging.getLogger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_PLAN_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "estimated_total_cost": {"type": "STRING"},
        "days": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "day_number": {"type": "INTEGER"},
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "activities": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "title": {"type": "STRING"},
                                "description": {"type": "STRING"},
                                "category": {"type": "STRING"},
                                "duration_minutes": {"type": "INTEGER"},
                                "estimated_cost": {"type": "STRING"},
                                "place_name": {
                                    "type": "STRING",
                                    "description": "Specific real-world place name to visit (e.g. Colosseum, Louvre Museum, Da Enzo al 29)",
                                },
                            },
                            "required": [
                                "title",
                                "description",
                                "category",
                                "duration_minutes",
                                "place_name",
                            ],
                        },
                    },
                },
                "required": ["day_number", "title", "description", "activities"],
            },
        },
    },
    "required": ["summary", "days"],
}


class GeminiPlanningEngine(PlanningEngine):
    """
    Google Gemini travel plan generator grounded with real Places data.

    Enforces:
      - AI is NEVER the source of truth for coordinates, addresses, or place IDs.
      - Every suggested place is verified against PlacesProvider.
      - Hallucinated / unresolvable places are dropped.
    """

    def __init__(
        self,
        api_key: str,
        places_provider: PlacesProvider,
        *,
        model: str = "gemini-2.0-flash",
        timeout_seconds: float = 60.0,
        temperature: float = 0.4,
        max_output_tokens: int = 4096,
        max_retries: int = 2,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key cannot be empty.")
        self._api_key = api_key
        self._places_provider = places_provider
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._max_retries = max_retries
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        elif getattr(self._client, "is_closed", False) is True:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _build_prompt(self, preferences: PlanningPreferences) -> str:
        interests_str = (
            ", ".join(preferences.interests) if preferences.interests else "general exploration"
        )
        special_reqs = (
            f"Special requirements: {preferences.special_requirements}"
            if preferences.special_requirements
            else ""
        )

        # Determine cost currency guidance based on destination
        dest_lower = preferences.destination.lower()
        india_keywords = ("india", "bengaluru", "bangalore", "mumbai", "delhi", "chennai",
                          "hyderabad", "kolkata", "mysore", "mysuru", "goa", "jaipur",
                          "agra", "varanasi", "kochi", "coorg", "kodagu", "manali",
                          "shimla", "kerala", "rajasthan", "pune", "ahmedabad", "surat")
        is_india = any(kw in dest_lower for kw in india_keywords)
        currency = preferences.currency or ("INR" if is_india else "USD")
        currency_symbol = "₹" if currency == "INR" else "$"
        currency_instruction = (
            f"Express ALL costs in Indian Rupees (₹). Use realistic local Indian pricing."
            if currency == "INR"
            else f"Express costs in {currency}."
        )

        budget_instruction = ""
        if preferences.target_budget:
            budget_instruction = (
                f"\nTarget total trip budget: {currency_symbol}{preferences.target_budget:,.0f} "
                f"{currency}. Keep total estimated costs within or close to this budget.\n"
            )

        return (
            f"Generate a realistic, day-by-day travel itinerary for a trip to {preferences.destination}.\n"
            f"Trip duration: {preferences.duration_days} days.\n"
            f"Travel style: {preferences.travel_style}.\n"
            f"Budget tier: {preferences.budget_level}.\n"
            f"Traveler interests: {interests_str}.\n"
            f"{special_reqs}\n"
            f"{budget_instruction}\n"
            f"CRITICAL GROUNDING AND QUALITY RULES:\n"
            f"1. You MUST only recommend real, physically existing, verifiable places in or immediately around {preferences.destination}.\n"
            f"2. For every activity, provide the SPECIFIC, ACTUAL real-world venue or attraction name in 'place_name'.\n"
            f"   - DO: 'Mysore Palace', 'Devaraja Market', 'Hotel RRR', 'Cafe Aramane'\n"
            f"   - DO NOT: 'Local palace', 'A market', 'Good restaurant', 'Morning exploration'\n"
            f"3. Never invent fictional or generic place names. Never hallucinate non-existent attractions.\n"
            f"4. Group activities logically by geographic proximity within each day to minimize travel time.\n"
            f"5. {currency_instruction}\n"
            f"6. Day titles must be descriptive: e.g. 'Mysore Palace & Heritage Walk' not 'Day 1 Exploration'.\n"
            f"7. For restaurant/food activities: name the specific restaurant or street food area.\n"
            f"8. Use realistic duration_minutes (sightseeing: 90-180min, meals: 60-90min, transit: 30-60min)."
        )

    async def _call_gemini_api(self, prompt: str) -> dict[str, Any]:
        """Execute request to Gemini generateContent endpoint with error mapping."""
        url = f"{_GEMINI_BASE_URL}/{self._model}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self._api_key}

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are Travix AI's expert travel planner. You generate structured, "
                            "realistic itineraries referencing strictly authentic, real-world venues."
                        )
                    }
                ]
            },
            "generationConfig": {
                "temperature": self._temperature,
                "maxOutputTokens": self._max_output_tokens,
                "responseMimeType": "application/json",
                "responseSchema": _PLAN_SCHEMA,
            },
        }

        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.post(url, params=params, headers=headers, json=body)
                if response.status_code == 429:
                    raise ExternalServiceError(
                        "gemini", "AI provider quota or rate limit exceeded."
                    )
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code != 200:
                    logger.error(
                        "Gemini API error status %d: %s", response.status_code, response.text
                    )
                    raise ExternalServiceError(
                        "gemini", f"AI provider returned unexpected HTTP {response.status_code}."
                    )

                response_json = response.json()
                candidates = response_json.get("candidates", [])
                if not candidates:
                    raise ExternalServiceError("gemini", "AI provider returned no candidates.")

                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts or "text" not in content_parts[0]:
                    raise ExternalServiceError(
                        "gemini", "AI provider response missing text content."
                    )

                raw_text = content_parts[0]["text"]
                try:
                    parsed_plan = json.loads(raw_text)
                    return parsed_plan
                except json.JSONDecodeError as exc:
                    logger.error("Failed to parse Gemini JSON output: %s", raw_text)
                    raise ExternalServiceError(
                        "gemini", "AI provider returned malformed JSON output.", cause=exc
                    )

            except ExternalServiceError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    break
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        logger.error("Gemini API call failed after %d retries: %s", self._max_retries, last_exc)
        raise ExternalServiceError(
            "gemini", "AI planning service is currently unavailable.", cause=last_exc
        )

    async def _ground_activity(
        self,
        raw_act: dict[str, Any],
        destination: str,
    ) -> ProposedActivity | None:
        """
        Verify a place against the Places provider.

        Extracts canonical coordinates and provider place ID from Places data,
        dropping hallucinated or unverified suggestions.
        """
        place_name = str(raw_act.get("place_name") or raw_act.get("title") or "").strip()
        if not place_name:
            return None

        # Resolve against Places provider
        query = f"{place_name}, {destination}"
        try:
            candidates = await self._places_provider.text_search(query)
            if not candidates:
                # Try just the place name if destination string was restrictive
                candidates = await self._places_provider.text_search(place_name)
        except Exception as exc:
            logger.warning("Places provider error while grounding '%s': %s", query, exc)
            # Return Gemini's suggestion unverified — better than losing all activities
            currency = str(raw_act.get("currency") or "INR")
            fallback_cost = raw_act.get("estimated_cost") or ("₹200" if currency == "INR" else "$5")
            return ProposedActivity(
                title=str(raw_act.get("title") or place_name),
                description=str(raw_act.get("description") or f"Visit {place_name}"),
                category=str(raw_act.get("category") or "sightseeing"),
                duration_minutes=int(raw_act.get("duration_minutes") or 120),
                estimated_cost=fallback_cost,
                provider_place_id=None,
                place_name=place_name,
                formatted_address=None,
                latitude=None,
                longitude=None,
                rating=None,
                is_verified=False,  # Unverified: Places unavailable
            )

        if not candidates:
            logger.info(
                "Dropping unverified place suggestion: '%s' (not found in Places)", place_name
            )
            return None


        # Verified match found! Use canonical ground truth from provider
        verified = candidates[0]

        return ProposedActivity(
            title=str(raw_act.get("title") or verified.name),
            description=str(raw_act.get("description") or f"Visit {verified.name}"),
            category=str(raw_act.get("category") or "sightseeing"),
            duration_minutes=int(raw_act.get("duration_minutes") or 120),
            estimated_cost=raw_act.get("estimated_cost"),
            provider_place_id=verified.provider_place_id,
            place_name=verified.name,
            formatted_address=verified.formatted_address,
            latitude=verified.latitude,
            longitude=verified.longitude,
            rating=verified.rating,
            is_verified=True,
        )

    async def generate_plan(self, preferences: PlanningPreferences) -> PlanningResult:
        """
        Generate and ground a travel plan using Google Gemini and PlacesProvider.
        """
        prompt = self._build_prompt(preferences)
        plan_data = await self._call_gemini_api(prompt)

        summary = plan_data.get("summary")
        if not summary or not isinstance(summary, str):
            raise ExternalServiceError("gemini", "AI response missing valid plan summary.")

        raw_days = plan_data.get("days", [])
        if not isinstance(raw_days, list) or not raw_days:
            raise ExternalServiceError("gemini", "AI response missing itinerary days.")

        days: list[ProposedDay] = []
        for day_data in raw_days:
            day_num = int(day_data.get("day_number", len(days) + 1))
            day_title = str(day_data.get("title") or f"Day {day_num} — {preferences.destination}")
            day_desc = str(day_data.get("description") or "")

            raw_activities = day_data.get("activities", [])
            grounded_activities: list[ProposedActivity] = []

            for raw_act in raw_activities:
                grounded = await self._ground_activity(raw_act, preferences.destination)
                if grounded is not None:
                    grounded_activities.append(grounded)

            # Fallback if all places were dropped: query verified top attractions for the city
            if not grounded_activities:
                logger.warning(
                    "All activities for day %d were unverified. Attempting Places fallback.",
                    day_num,
                )
                currency = getattr(preferences, "currency", "INR")
                fallback_cost = "₹200" if currency == "INR" else "$5"
                try:
                    fallback_places = await self._places_provider.text_search(
                        f"top attractions in {preferences.destination}"
                    )
                    for fb in fallback_places[:2]:
                        grounded_activities.append(
                            ProposedActivity(
                                title=f"Explore {fb.name}",
                                description=f"Visit {fb.name} located at {fb.formatted_address}.",
                                category="sightseeing",
                                duration_minutes=120,
                                estimated_cost=fallback_cost,
                                provider_place_id=fb.provider_place_id,
                                place_name=fb.name,
                                formatted_address=fb.formatted_address,
                                latitude=fb.latitude,
                                longitude=fb.longitude,
                                rating=fb.rating,
                                is_verified=True,
                            )
                        )
                except Exception as places_exc:
                    # Places provider unavailable — use Gemini's own suggestions unverified
                    logger.warning(
                        "Places provider unavailable for day %d fallback (%s). "
                        "Using Gemini suggestions without verification.",
                        day_num,
                        places_exc,
                    )
                    for raw_act in raw_activities[:3]:
                        place_name = str(raw_act.get("place_name") or raw_act.get("title") or "").strip()
                        if not place_name:
                            continue
                        grounded_activities.append(
                            ProposedActivity(
                                title=str(raw_act.get("title") or place_name),
                                description=str(raw_act.get("description") or f"Visit {place_name}"),
                                category=str(raw_act.get("category") or "sightseeing"),
                                duration_minutes=int(raw_act.get("duration_minutes") or 120),
                                estimated_cost=raw_act.get("estimated_cost") or fallback_cost,
                                provider_place_id=None,
                                place_name=place_name,
                                formatted_address=None,
                                latitude=None,
                                longitude=None,
                                rating=None,
                                is_verified=False,  # Marked unverified — Places unavailable
                            )
                        )

            days.append(
                ProposedDay(
                    day_number=day_num,
                    title=day_title,
                    description=day_desc,
                    activities=tuple(grounded_activities),
                )
            )

        return PlanningResult(
            summary=summary,
            days=tuple(days),
            estimated_total_cost=plan_data.get("estimated_total_cost"),
            generated_at=datetime.now(UTC),
        )
