"""Base agent class with LLM integration and retry logic."""

import base64
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import get_settings


class BaseAgent(ABC):
    """Base class for all agents with common LLM functionality."""

    _initialized = False  # Class-level flag to print only once

    def __init__(
        self,
        model: str | None = None,
        max_retries: int | None = None,
        request_delay: float | None = None,
    ):
        from google import genai

        settings = get_settings()
        self.max_retries = max_retries or settings.max_retries
        self.request_delay = request_delay or settings.request_delay_seconds

        # Use Gemini API
        gemini_key = settings.effective_gemini_key
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY not found in .env")

        self.model_name = model or "gemini-flash-latest"
        self._client = genai.Client(api_key=gemini_key)

        # Print only once
        if not BaseAgent._initialized:
            print(f"  [LLM] Using Gemini: {self.model_name}")
            BaseAgent._initialized = True

    @property
    def name(self) -> str:
        """Return the agent name."""
        return self.__class__.__name__.replace("Agent", "").lower()

    @abstractmethod
    def process(self, **kwargs) -> BaseModel:
        """Process input and return structured output."""
        pass

    def _encode_image(self, image_source: bytes | str | Path) -> tuple[str, str]:
        """Encode image to base64 and determine media type.

        Args:
            image_source: Image bytes, file path string, or Path object

        Returns:
            Tuple of (base64_data, media_type)
        """
        if isinstance(image_source, bytes):
            image_bytes = image_source
            media_type = "image/png"  # Default assumption
        else:
            path = Path(image_source)
            image_bytes = path.read_bytes()
            suffix = path.suffix.lower()
            media_type_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(suffix, "image/png")

        base64_data = base64.standard_b64encode(image_bytes).decode("utf-8")
        return base64_data, media_type

    def _call_vision_llm(
        self,
        image_source: bytes | str | Path,
        prompt: str,
    ) -> str:
        """Call the vision LLM with an image and prompt.

        Args:
            image_source: Image bytes, file path, or Path object
            prompt: Text prompt to send with the image

        Returns:
            The LLM's text response
        """
        from google.genai import types

        # Get image bytes and media type
        if isinstance(image_source, bytes):
            image_bytes = image_source
            media_type = "image/png"
        else:
            path = Path(image_source)
            image_bytes = path.read_bytes()
            suffix = path.suffix.lower()
            media_type_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }
            media_type = media_type_map.get(suffix, "image/png")

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                types.Part.from_text(text=prompt),
            ],
        )
        return response.text if response.text else ""

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with a text-only prompt.

        Args:
            prompt: Text prompt

        Returns:
            The LLM's text response
        """
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=[types.Part.from_text(text=prompt)],
        )
        return response.text if response.text else ""

    def _call_with_retry(
        self,
        func: callable,
        *args,
        **kwargs,
    ) -> Any:
        """Call a function with retry logic for rate limits.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: After exhausting retries
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    wait_time = self.request_delay * (2 ** (attempt - 1))
                    time.sleep(wait_time)

                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if rate limited
                if "429" in str(e) or "rate" in error_str:
                    if attempt < self.max_retries:
                        continue

                # Non-retryable error
                raise

        raise last_exception

    def _parse_json_response(self, response: str) -> dict:
        """Extract JSON from LLM response.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed JSON dict
        """
        import json
        import re

        # Try to find JSON in code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find raw JSON object
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            return json.loads(json_match.group(0))

        # Try parsing entire response
        return json.loads(response)
