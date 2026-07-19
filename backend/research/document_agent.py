import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

from .prompts import DOCUMENT_EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

UMANS_BASE_URL = "https://api.code.umans.ai/v1/chat/completions"


class DocumentAgent:
    """AI agent that extracts structured diligence data from a document's text."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("UMANS_API_KEY")
        if not self.api_key:
            raise RuntimeError("UMANS_API_KEY is not set")

        self.model = model or os.environ.get("UMANS_DOCUMENT_MODEL", "umans-coder")
        self.timeout = float(timeout or os.environ.get("UMANS_RESEARCH_TIMEOUT", "120"))

        logger.info(
            "document_agent.configured model=%s timeout=%s",
            self.model,
            self.timeout,
        )

    def extract(
        self,
        text: str,
        filename: Optional[str] = None,
    ) -> dict[str, Any]:
        """Extract profile, claims, and evidence from document text.

        Args:
            text: The plain text extracted from the document.
            filename: Optional filename for provenance.

        Returns:
            Parsed JSON dict with keys: profile, summary, claims, evidence.
        """
        logger.info(
            "document_agent.extract.start text_chars=%s filename=%s",
            len(text),
            filename,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        source_note = f" from {filename}" if filename else ""
        user_message = (
            f"Analyze the following founder document{source_note} and extract structured diligence data.\n\n"
            f"--- DOCUMENT TEXT ---\n{text}\n--- END DOCUMENT ---"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": DOCUMENT_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_completion_tokens": 8000,
        }

        with httpx.Client(timeout=self.timeout) as client:
            logger.info("document_agent.extract.request model=%s", self.model)
            response = client.post(UMANS_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        parsed = self._parse_response(data)
        logger.info(
            "document_agent.extract.end claims=%s evidence=%s",
            len(parsed.get("claims", []) or []),
            len(parsed.get("evidence", []) or []),
        )
        return parsed

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            logger.error("document_agent.extract.unexpected_response data=%s", data)
            raise ValueError(f"Unexpected Umans response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            logger.error("document_agent.extract.empty_content")
            raise ValueError("Umans response contained no content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("document_agent.extract.invalid_json content=%s", content)
            raise ValueError(f"Umans response was not valid JSON:\n{content}") from exc

        return {
            "profile": parsed.get("profile", {}) or {},
            "summary": parsed.get("summary", ""),
            "claims": parsed.get("claims", []) or [],
            "evidence": parsed.get("evidence", []) or [],
        }
