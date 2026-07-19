import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from models import Claim, EvidenceItem, EvidenceStatus, EvidenceType, Founder
from .api_lock import api_lock
from .extractor import evidence_from_llm
from .http_utils import raise_for_status

logger = logging.getLogger(__name__)

OPENAI_BASE_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
)

_ESTIMATE_SYSTEM_PROMPT = """You are a rigorous founder-diligence estimator.

Given whatever information is available about a founder (sourcing reason, research summary, social background, and extracted claims), estimate one evidence item per scoring dimension.

Scoring dimensions and what they measure:
- execution_and_shipping: shipped products, milestones, revenue/growth, operational delivery
- technical_or_domain_ability: work, research, patents, code, domain outcomes
- agency_and_initiative: self-directed work, resource acquisition, outreach
- learning_velocity: iteration history, response to feedback, skills progression
- resilience_and_persistence: continued progress after setbacks and recovery actions
- commercial_recruiting_distribution_ability: customers, partnerships, hires, community growth
- collaboration_and_integrity: references, team history, claim consistency
- prior_venture_outcomes: prior company results, users, revenue, exit, or learning

Return ONLY a valid JSON object matching this schema:

{
  "evidence": [
    {
      "dimension": "execution_and_shipping|technical_or_domain_ability|agency_and_initiative|learning_velocity|resilience_and_persistence|commercial_recruiting_distribution_ability|collaboration_and_integrity|prior_venture_outcomes",
      "observation": "A short, factual sentence explaining what the available data implies for this dimension. If nothing is known, say so.",
      "rubric_level": 0-4,
      "source_trust": 0.0-1.0,
      "task_relevance": 0.0-1.0,
      "recency_factor": 0.0-1.0,
      "polarity": "positive|negative|mixed|unknown",
      "status": "positive|negative|mixed|unknown",
      "counter_evidence": "Any contradiction or caveat; otherwise null",
      "unknowns": "Open questions or caveats; otherwise null"
    }
  ]
}

Rubric level guidance:
- 0 = strong negative signal
- 1 = weak negative / concerning
- 2 = neutral / no strong signal
- 3 = positive signal
- 4 = exceptional, verified outcome

Trust/relevance/recency guidance:
- source_trust: 0.9-1.0 official/verified, 0.6-0.8 credible pub, 0.3-0.5 self-claimed/social, 0.1-0.2 vague/no source
- task_relevance: how directly the finding maps to the dimension
- recency_factor: 1.0 <6mo, 0.5 1-2yr, 0.2 older, 0.0 unknown

Important:
- Produce exactly one evidence item per dimension.
- These are estimates, so lean conservative and avoid extreme 4s unless the data strongly supports it.
- If no data supports a dimension, use rubric_level 2, low trust/relevance, and explain the unknown.
- Do not invent facts that are not supported by the provided context.

Return ONLY the JSON object. No markdown fences, no commentary."""


class AIFounderEstimator:
    """Estimates dimension scores from whatever founder data is available."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.model = model or os.environ.get("OPENAI_ESTIMATE_MODEL", "gpt-5")
        self.timeout = float(timeout or os.environ.get("OPENAI_TIMEOUT", "60"))
        self.max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", "4000"))

    def estimate(
        self,
        founder: Founder,
        source_reason: Optional[str] = None,
        research_summary: Optional[str] = None,
        social_summary: Optional[str] = None,
        claims: Optional[List[Claim]] = None,
    ) -> List[EvidenceItem]:
        """Return inferred evidence items for each dimension based on available context."""
        context_parts = []
        if source_reason:
            context_parts.append(f"Sourcing reason: {source_reason}")
        if research_summary:
            context_parts.append(f"AI research summary: {research_summary}")
        if social_summary:
            context_parts.append(f"Social background summary: {social_summary}")
        if claims:
            for claim in claims:
                claim_text = f"- {claim.claim}"
                if claim.contradiction:
                    claim_text += f" (Contradiction: {claim.contradiction})"
                context_parts.append(claim_text)

        if not context_parts:
            logger.info("estimator.no_context founder_id=%s", founder.id)
            return []

        user_message = (
            "Estimate the founder's score across all dimensions.\n\n"
            f"Founder: {founder.name}\n"
            f"Company: {founder.current_company or 'unknown'}\n"
            f"Role: {founder.role or 'unknown'}\n\n"
            "Context:\n" + "\n".join(context_parts)
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _ESTIMATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_completion_tokens": self.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info("estimator.request.start founder_id=%s model=%s", founder.id, self.model)
        with httpx.Client(timeout=self.timeout) as client:
            with api_lock():
                response = client.post(OPENAI_BASE_URL, headers=headers, json=payload)
            raise_for_status(response)
            data = response.json()

        parsed = self._parse_response(data)
        raw_evidence = parsed.get("evidence", []) or []
        evidence_items = []
        for item in raw_evidence:
            # Ensure the estimator output is coerced into a valid EvidenceItem.
            item.setdefault("source_type", "ai_estimate")
            item.setdefault("source_id", "estimate")
            item.setdefault("source_locator", "estimate")
            item.setdefault("evidence_type", "inferred_estimate")
            item.setdefault("independence_group", "ai_estimate")
            evidence_items.append(evidence_from_llm(founder.id, item))
        logger.info(
            "estimator.request.end founder_id=%s items=%s",
            founder.id,
            len(evidence_items),
        )
        return evidence_items

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            logger.error("estimator.unexpected_response data=%s", data)
            raise ValueError(f"Unexpected OpenAI response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")
        content = content.strip()

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            logger.error("estimator.empty_content")
            raise ValueError("OpenAI response contained no content")

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("estimator.invalid_json content=%s", content)
            raise ValueError(f"OpenAI response was not valid JSON:\n{content}") from exc
