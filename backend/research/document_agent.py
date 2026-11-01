from typing import Any, Optional

from .http_utils import chat_completion, parse_completion
from .openrouter_config import get_api_key, load_config
from .prompts import DOCUMENT_EXTRACTION_SYSTEM_PROMPT


class DocumentAgent:
    """AI agent that extracts structured diligence data from a document's text."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._api_key_override = api_key
        config = load_config(api_key, model, timeout, default_timeout=120, default_max_tokens=8000)
        self.api_key = config.api_key
        self.model = config.model
        self.timeout = config.timeout
        self.max_tokens = config.max_tokens

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
        self.api_key = get_api_key(self._api_key_override)

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

        data = chat_completion(payload, api_key=self.api_key, timeout=self.timeout)

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_completion(data)
        return {
            "profile": parsed.get("profile", {}) or {},
            "summary": parsed.get("summary", ""),
            "claims": parsed.get("claims", []) or [],
            "evidence": parsed.get("evidence", []) or [],
        }
