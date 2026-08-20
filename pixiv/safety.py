from __future__ import annotations

import re
import unicodedata


def normalize_safety_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s_\-‐‑‒–—―·・.]+", "", text)


def match_safety_term(value: object, terms: set[str] | frozenset[str]) -> str:
    normalized = normalize_safety_text(value)
    if not normalized:
        return ""
    return next(
        (term for term in sorted(terms, key=len, reverse=True) if term in normalized),
        "",
    )


def illustration_texts(illust: dict) -> list[str]:
    values = [
        str(illust.get("title") or ""),
        str(illust.get("caption") or illust.get("description") or ""),
    ]
    for tag in illust.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        values.extend(
            (str(tag.get("name") or ""), str(tag.get("translated_name") or ""))
        )
    return values
