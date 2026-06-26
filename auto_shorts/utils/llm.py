"""
Auto Shorts — Utility: LLM

Wrapper for Ollama API to run local language models.
"""
import json
import logging
from typing import Any

import ollama

from auto_shorts.config import LLM_MODEL

logger = logging.getLogger(__name__)


def ask(prompt: str, model: str = LLM_MODEL) -> str:
    """Send a prompt to the local LLM and get a string response."""
    logger.debug(f"Sending prompt to {model} (length: {len(prompt)})")
    
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"]
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        logger.error("Make sure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull <model>`)")
        raise


def ask_json(prompt: str, model: str = LLM_MODEL) -> Any:
    """
    Send a prompt to the LLM and parse the response as JSON.
    Automatically handles stripping markdown fences and common LLM JSON errors.
    """
    # Append instructions to ensure JSON output
    json_prompt = (
        prompt + "\n\n"
        "IMPORTANT: You must respond ONLY with valid, minified JSON. "
        "Do not include any explanation, preamble, or markdown code fences (like ```json). "
        "The response must be strictly parseable by standard JSON parsers."
    )
    
    raw = ask(json_prompt, model)
    
    # Clean up common LLM output issues
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
        
    raw = raw.strip()
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response:\n{raw}")
        raise ValueError("LLM did not return valid JSON") from e
