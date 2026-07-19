import json
import logging
import os
import re
from typing import Any, List, Optional

import httpx

from .api_lock import api_lock
from .http_utils import raise_for_status
from .prompts import DOCUMENT_EXTRACTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENAI_BASE_URL = os.environ.get(
    "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
)


class DocumentAgent:
    """AI agent that extracts structured diligence data from a document's text."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.model = model or os.environ.get("OPENAI_DOCUMENT_MODEL", "gpt-5")
        self.timeout = float(timeout or os.environ.get("OPENAI_TIMEOUT", "120"))
        self.max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", "8000"))

        logger.info(
            "document_agent.configured model=%s timeout=%s max_tokens=%s",
            self.model,
            self.timeout,
            self.max_tokens,
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
            "max_completion_tokens": self.max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            logger.info("document_agent.extract.request model=%s", self.model)
            with api_lock():
                response = client.post(OPENAI_BASE_URL, headers=headers, json=payload)
            raise_for_status(response)
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
            raise ValueError(f"Unexpected OpenAI response shape: {data}") from exc

        message = choice.get("message", {})
        content = message.get("content", "")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)
            content = content.strip()

        if not content:
            logger.error("document_agent.extract.empty_content")
            raise ValueError("OpenAI response contained no content")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("document_agent.extract.invalid_json content=%s", content)
            raise ValueError(f"OpenAI response was not valid JSON:\n{content}") from exc

        return {
            "profile": parsed.get("profile", {}) or {},
            "summary": parsed.get("summary", ""),
            "claims": parsed.get("claims", []) or [],
            "evidence": parsed.get("evidence", []) or [],
        }
