"""
Handlers for AI-powered project planning and code generation using DeepSeek API.
"""

import json
import logging
import os
import re
from typing import Optional

from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)

# Initialize DeepSeek client
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

if DEEPSEEK_API_KEY:
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
else:
    client = None
    logger.warning("DEEPSEEK_API_KEY not set; AI features will be unavailable.")


async def analyze_project_plan(message: str) -> dict:
    """
    Uses DeepSeek to generate a structured project plan from a user message.

    Args:
        message: The user's high-level project description.

    Returns:
        A dictionary representing the JSON project plan (e.g., with
        "project_name", "overview", "features", "files_structure", etc.).

    Raises:
        RuntimeError: If the API call fails or response is not valid JSON.
    """
    if not client:
        raise RuntimeError("DeepSeek client is not configured. Set DEEPSEEK_API_KEY.")

    system_prompt = (
        "You are an expert project planning assistant. "
        "Based on the user's request, generate a detailed project plan in valid JSON format. "
        "The JSON must include the following fields: "
        "\"project_name\" (string), \"overview\" (string), \"features\" (list of strings), "
        "\"files_structure\" (list of objects, each with \"path\" and \"description\"). "
        "Respond ONLY with the JSON object, no extra text or markdown formatting."
    )

    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
    except (APIError, APIConnectionError, RateLimitError) as e:
        logger.error(f"DeepSeek API error during analyze_project_plan: {e}")
        raise RuntimeError(f"AI planning failed: {e}") from e

    content = response.choices[0].message.content.strip()

    # Attempt to parse as JSON directly or extract from first code block
    try:
        plan = json.loads(content)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code block (e.g., ```json ... ```)
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if match:
            try:
                plan = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                raise RuntimeError(
                    "AI response did not contain valid JSON. Response preview: "
                    f"{content[:200]}"
                )
        else:
            raise RuntimeError(
                "AI response did not contain valid JSON. Response preview: "
                f"{content[:200]}"
            )

    # Validate expected fields exist (basic)
    required = ["project_name", "overview", "features", "files_structure"]
    for field in required:
        if field not in plan:
            raise RuntimeError(f"Missing required field '{field}' in AI plan.")

    return plan


async def generate_file_code(
    filename: str,
    description: str,
    context: Optional[str] = None,
) -> str:
    """
    Uses DeepSeek to generate production-ready code for a given file.

    Args:
        filename: The name/path of the file (used to infer language/file type).
        description: What the file should do.
        context: Optional additional context (e.g., surrounding project files, tech stack).

    Returns:
        The generated code as a string.

    Raises:
        RuntimeError: If the API call fails.
    """
    if not client:
        raise RuntimeError("DeepSeek client is not configured. Set DEEPSEEK_API_KEY.")

    system_prompt = (
        "You are an expert software engineer. Generate complete, production-ready code "
        "for the requested file. Follow best practices, include appropriate imports, "
        "error handling, and comments. Return ONLY the code inside a code block "
        "with the appropriate language identifier (e.g., ```python\\n...\\n```). "
        "Do not include any explanation outside the code block."
    )

    user_message = (
        f"File: {filename}\n"
        f"Description: {description}\n"
    )
    if context:
        user_message += f"Additional context:\n{context}\n"

    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
    except (APIError, APIConnectionError, RateLimitError) as e:
        logger.error(f"DeepSeek API error during generate_file_code: {e}")
        raise RuntimeError(f"Code generation failed: {e}") from e

    content = response.choices[0].message.content.strip()
    code = extract_code_from_response(content)

    if not code:
        # Fallback: return entire response if no code block found
        logger.warning(f"No code block found in AI response for file {filename}. Using raw response.")
        code = content

    return code


def extract_code_from_response(response: str) -> Optional[str]:
    """
    Extracts code from a markdown code block (triple backticks).
    Returns the first code block content if found, otherwise None.

    Args:
        response: The full text from the AI.

    Returns:
        The code inside the first code block (without backticks), or None.
    """
    # Match ```<language> (optional) followed by newline, then code, then closing ```
    pattern = r"```(?:\w+)?\s*\n?(.*?)\n?```"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None