"""
Auto Shorts — Utility: LLM

Wrapper for MLX-LM to run local language models natively on Apple Silicon.
No external server required — models run directly in the Python process.
"""
import json
import logging
from typing import Any

from auto_shorts.config import LLM_MODEL, MODELS_DIR

logger = logging.getLogger(__name__)

# Module-level cache to avoid reloading the model on every call
_loaded_model = None
_loaded_tokenizer = None
_loaded_model_name = None


def _get_model(model: str):
    """Load and cache the MLX-LM model. Downloads from HuggingFace on first use."""
    global _loaded_model, _loaded_tokenizer, _loaded_model_name
    
    if _loaded_model is not None and _loaded_model_name == model:
        return _loaded_model, _loaded_tokenizer
    
    from mlx_lm import load
    from huggingface_hub import snapshot_download
    
    # Extract the base model name (e.g., "Qwen2.5-14B-Instruct-4bit")
    model_name = model.split("/")[-1] if "/" in model else model
    local_model_dir = MODELS_DIR / model_name
    
    if not local_model_dir.exists() or not list(local_model_dir.glob("*.safetensors")):
        logger.info(f"Downloading MLX-LM model {model} to local models folder ({local_model_dir})...")
        snapshot_download(
            repo_id=model,
            local_dir=str(local_model_dir),
            local_dir_use_symlinks=False
        )
    else:
        logger.info(f"Found local MLX-LM model at {local_model_dir}")
        
    logger.info(f"Loading MLX-LM model into memory (this is fast)...")
    
    _loaded_model, _loaded_tokenizer = load(str(local_model_dir))
    _loaded_model_name = model
    
    logger.info(f"✅ Model loaded: {model}")
    return _loaded_model, _loaded_tokenizer


def unload_model():
    """Explicitly unload the model to free memory."""
    global _loaded_model, _loaded_tokenizer, _loaded_model_name
    _loaded_model = None
    _loaded_tokenizer = None
    _loaded_model_name = None
    logger.info("Model unloaded from memory")


def ask(prompt: str, model: str = LLM_MODEL) -> str:
    """Send a prompt to the local MLX-LM model and get a string response."""
    from mlx_lm import generate
    
    logger.debug(f"Sending prompt to {model} (length: {len(prompt)})")
    
    mlx_model, tokenizer = _get_model(model)
    
    # Format using chat template for instruction-tuned models
    messages = [{"role": "user", "content": prompt}]
    
    if hasattr(tokenizer, 'apply_chat_template'):
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False
        )
    else:
        formatted_prompt = prompt
    
    response = generate(
        mlx_model,
        tokenizer,
        prompt=formatted_prompt,
        max_tokens=4096,
        verbose=False,
    )
    
    return response


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
    
    # Handle thinking tags from Qwen models
    if "<think>" in raw:
        # Remove everything between <think> and </think>
        import re
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
        
    raw = raw.strip()
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response:\n{raw[:500]}...")
        raise ValueError("LLM did not return valid JSON") from e
