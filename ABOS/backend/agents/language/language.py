"""
Language Detection and Translation Node — ABOS

Handles multilingual user input so non-English speakers can use ABOS
in their native language (Hindi, Marathi, Tamil, Telugu, Bengali, etc.).

Two responsibilities:
1. language_node  — runs at the START of the graph, before memory_retrieval.
   - Detects the language of the user's goal title + description.
   - If non-English: translates both to English for internal processing.
   - Stores detected_language and original text in state so outputs
     can be localised back at the end.

2. translate_output()  — called by the summarizer to convert the final
   English summary + compliance flags back into the user's language before
   delivery. This is a utility function, not a graph node.

Design decisions:
- All internal processing (planner, compliance, scheduler, agents) stays English.
  This avoids prompt complexity and keeps the core logic clean.
- The LLM does both detection and translation in a single call — cheap and accurate
  for the languages commonly spoken in India and globally.
- If detection/translation fails, we fall back gracefully to treating input as English.
- The detected language is stored as a BCP-47 language tag (e.g. "hi", "mr", "ta").
"""

import json
import logging
from typing import Any, Dict, Optional

from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.agents.state import ABOSState
from backend.core.config import settings

logger = logging.getLogger(__name__)


# ── Supported language display names (for output localisation prompts) ────────

LANGUAGE_NAMES: Dict[str, str] = {
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "en": "English",
}


# ── Prompts ───────────────────────────────────────────────────────────────────

_DETECT_TRANSLATE_SYSTEM = """\
You are a language detection and translation assistant for a business automation system.

Your job:
1. Detect the language of the provided business goal text.
2. If the language is NOT English, translate the title and description to clear, professional English.
3. If the language IS English, return it unchanged.

OUTPUT FORMAT — respond with ONLY a valid JSON object, no markdown:

{
  "detected_language": "<BCP-47 tag, e.g. hi, mr, ta, en, fr>",
  "is_english": true | false,
  "translated_title": "<English title>",
  "translated_description": "<English description>"
}

RULES:
- Keep the translated description faithful to the original intent — do not add or remove information.
- Use professional business English in translations.
- For proper nouns (city names, person names, brand names), keep them as-is or use their standard English spelling.
- If you cannot confidently detect the language, set detected_language to "en" and is_english to true.
"""

_DETECT_TRANSLATE_USER = """\
Detect the language and translate if needed:

TITLE: {title}

DESCRIPTION: {description}
"""

_LOCALISE_OUTPUT_SYSTEM = """\
You are a localisation assistant for a business automation system.

The system has completed a workflow and generated an English summary and compliance notes.
Your job is to translate this output into {language_name} so the user can read it in their language.

RULES:
- Translate naturally and professionally — not word-for-word.
- Keep business terms, numbers, percentages, company names, and technical identifiers (IDs, codes) in their original form.
- Preserve the structure: if the English has bullet points or sections, keep that structure.
- Do not add or remove information.
- Write in a register appropriate for a business owner reading in {language_name}.

OUTPUT FORMAT — respond with ONLY a valid JSON object, no markdown:

{
  "localised_summary": "<translated summary in {language_name}>",
  "localised_compliance_flags": ["<translated flag 1>", "<translated flag 2>"]
}
"""

_LOCALISE_OUTPUT_USER = """\
Translate the following business workflow output to {language_name}:

SUMMARY:
{summary}

COMPLIANCE FLAGS:
{compliance_flags}
"""


# ── LLM helpers ───────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=8), reraise=True)
async def _call_llm(system: str, user: str) -> str:
    response = await acompletion(
        model=settings.ACTIVE_LLM,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=600,
    )
    return response.choices[0].message.content


def _parse_json(raw: str, fallback: Dict) -> Dict:
    try:
        cleaned = raw.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) >= 3 else parts[-1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except Exception as e:
        logger.warning(f"[Language] JSON parse failed: {e}. Raw: {raw[:200]}")
        return fallback


# ── Node: language detection + translation ────────────────────────────────────

async def language_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Language Detection and Input Translation.

    Runs first in the graph — before memory_retrieval.

    Reads:  goal_title, goal_description, preferred_language (optional)
    Writes: detected_language, goal_title (English), goal_description (English),
            original_goal_title, original_goal_description, logs
    """
    title = state.get("goal_title", "")
    description = state.get("goal_description", "")

    # If the user explicitly set a preferred language in context, honour it
    preferred = (state.get("goal_context") or {}).get("preferred_language")

    logger.info(f"[Language] Detecting language for goal_id={state.get('goal_id')}")

    # Detect and translate
    fallback_detect = {
        "detected_language": preferred or "en",
        "is_english": True,
        "translated_title": title,
        "translated_description": description,
    }

    try:
        user_prompt = _DETECT_TRANSLATE_USER.format(
            title=title,
            description=description,
        )
        raw = await _call_llm(_DETECT_TRANSLATE_SYSTEM, user_prompt)
        result = _parse_json(raw, fallback_detect)
    except Exception as e:
        logger.error(f"[Language] Detection/translation failed: {e}. Treating as English.")
        result = fallback_detect

    detected_lang: str = result.get("detected_language", "en").lower().strip()
    is_english: bool = result.get("is_english", True)
    translated_title: str = result.get("translated_title", title)
    translated_description: str = result.get("translated_description", description)

    # If preferred_language was explicitly passed, override the detected one
    if preferred:
        detected_lang = preferred.lower().strip()
        is_english = detected_lang == "en"

    lang_name = LANGUAGE_NAMES.get(detected_lang, detected_lang.upper())
    log_lines = [
        f"Language node: detected='{detected_lang}' ({lang_name}), "
        f"is_english={is_english}, goal_id={state.get('goal_id')}."
    ]

    if not is_english:
        logger.info(
            f"[Language] Goal translated from {lang_name} to English "
            f"for goal_id={state.get('goal_id')}."
        )
        log_lines.append(
            f"Language node: translated goal from {lang_name} to English for internal processing."
        )

    return {
        # Overwrite goal_title/description with English versions for all downstream nodes
        "goal_title": translated_title,
        "goal_description": translated_description,
        # Preserve originals so we can localise the output later
        "original_goal_title": title,
        "original_goal_description": description,
        "detected_language": detected_lang,
        "logs": log_lines,
    }


# ── Utility: translate final output back to user's language ───────────────────

async def translate_output(
    summary: str,
    compliance_flags: list,
    detected_language: str,
) -> Dict[str, Any]:
    """
    Translate the final English summary and compliance flags into the
    user's detected language.

    Returns a dict with:
      - localised_summary: str
      - localised_compliance_flags: list[str]

    Falls back to English on failure.
    """
    if not detected_language or detected_language == "en":
        return {
            "localised_summary": summary,
            "localised_compliance_flags": compliance_flags,
        }

    lang_name = LANGUAGE_NAMES.get(detected_language, detected_language.upper())

    fallback = {
        "localised_summary": summary,
        "localised_compliance_flags": compliance_flags,
    }

    try:
        system = _LOCALISE_OUTPUT_SYSTEM.format(language_name=lang_name)
        user = _LOCALISE_OUTPUT_USER.format(
            language_name=lang_name,
            summary=summary,
            compliance_flags="\n".join(compliance_flags) if compliance_flags else "None",
        )
        raw = await _call_llm(system, user)
        result = _parse_json(raw, fallback)
        return {
            "localised_summary": result.get("localised_summary", summary),
            "localised_compliance_flags": result.get("localised_compliance_flags", compliance_flags),
        }
    except Exception as e:
        logger.error(f"[Language] Output translation to {lang_name} failed: {e}. Using English.")
        return fallback
