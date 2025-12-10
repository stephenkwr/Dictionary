# custom_modules/mw_dictionary.py
from __future__ import annotations
import re
import httpx
from typing import Any, Dict, List, Tuple
from important_info.API_loader import env

MW_EN_KEY = env("MERRIAM_WEBSTER_DICT_API")
MW_ES_KEY = env("MERRIAM_WEBSTER_SPANISH_DICT_API")

# -------------------- helpers: MW audio URL + tag cleaner --------------------

def _mw_audio_url(audio: str) -> str:
    """
    Build MW audio URL per their rules.
    https://dictionaryapi.com/products/json#sec-2.audio
    """
    if audio.startswith("bix"):
        sub = "bix"
    elif audio.startswith("gg"):
        sub = "gg"
    elif not audio[:1].isalpha():
        sub = "number"
    else:
        sub = audio[0]
    return f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{sub}/{audio}.mp3"

_TAG_PAT = re.compile(r"\{.*?\}")

def _clean_mw_text(s: str) -> str:
    """
    Make MW 'text' readable by removing/transforming inline tags:
      {bc}  {it}...{/it}  {wi}...{/wi}  {a_link|...}  {sx|...||}
      Spanish adds {gl} (gender labels), we keep those via extraction elsewhere.
    """
    s = s.replace("{bc}", ": ")
    s = s.replace("{wi}", "").replace("{/wi}", "")
    s = s.replace("{it}", "").replace("{/it}", "")
    # {a_link|word} -> word
    s = re.sub(r"\{a_link\|([^}|]+)\}", r"\1", s)
    # {sx|large||} -> large
    s = re.sub(r"\{sx\|([^}|]+)\|[^}]*\}", r"\1", s)
    # Remove any other {...} tags (we separately surface {gl} gender via the JSON field)
    s = _TAG_PAT.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,;:.])", r"\1", s)
    return s

# -------------------- common definition extractor (EN & ES) ------------------

def _extract_definitions_from_sseq(sseq: Any, include_examples: bool = True, include_gender: bool = True) -> List[str]:
    """
    Walk 'def' -> 'sseq' blocks and collect definition texts.
    For Spanish, 'dt' can include:
      ["text", "..."], ["gl", "masculine"], ["vis", [{"t": "...", "tr": "..."}, ...]]
    For English, it's usually ["text", "..."] and ["vis", ...].
    """
    out: List[str] = []
    if not isinstance(sseq, list):
        return out

    for block in sseq:
        if not isinstance(block, list):
            continue
        for item in block:
            if not (isinstance(item, list) and len(item) == 2 and item[0] == "sense" and isinstance(item[1], dict)):
                continue
            sense = item[1]
            dt = sense.get("dt", [])
            gender_buf: List[str] = []
            text_buf: List[str] = []
            examples_buf: List[str] = []

            for piece in dt:
                if not (isinstance(piece, list) and piece):
                    continue
                tag = piece[0]

                if tag == "text" and len(piece) > 1 and isinstance(piece[1], str):
                    text_buf.append(_clean_mw_text(piece[1]))

                elif tag == "gl" and include_gender and len(piece) > 1 and isinstance(piece[1], str):
                    gender_buf.append(piece[1])

                elif tag == "vis" and include_examples and len(piece) > 1 and isinstance(piece[1], list):
                    for ex in piece[1]:
                        t = ex.get("t")
                        tr = ex.get("tr")
                        if isinstance(t, str) and isinstance(tr, str):
                            examples_buf.append(f"e.g. { _clean_mw_text(t) } → { _clean_mw_text(tr) }")
                        elif isinstance(t, str):
                            examples_buf.append(f"e.g. { _clean_mw_text(t) }")

            # Merge this sense into a single readable line, with optional gender and examples
            line_parts: List[str] = []
            if text_buf:
                line_parts.append(" ".join(text_buf))
            if gender_buf:
                line_parts.append(f"({'; '.join(gender_buf)})")
            if examples_buf:
                line_parts.extend(examples_buf)

            line = " ".join(p for p in line_parts if p).strip()
            if line:
                out.append(line)

            # 'sdsense' (also/compare) sometimes holds extra alt texts
            sdsense = sense.get("sdsense")
            if isinstance(sdsense, dict):
                for sd_piece in sdsense.get("dt", []):
                    if isinstance(sd_piece, list) and sd_piece and sd_piece[0] == "text" and len(sd_piece) > 1:
                        out.append(_clean_mw_text(sd_piece[1]))

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for d in out:
        if d and d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq

# -------------------- fetchers (return RAW JSON) -----------------------------

def fetch_mw_english_json(word: str, timeout: float = 15) -> Any:
    url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={MW_EN_KEY}"
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()

def fetch_mw_spanish_json(word: str, timeout: float = 15) -> Any:
    url = f"https://www.dictionaryapi.com/api/v3/references/spanish/json/{word}?key={MW_ES_KEY}"
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()

# -------------------- common formatter (works for EN & ES) -------------------

def format_mw_entries(data: Any, *, language: str) -> str:
    """
    Format the first dictionary entry from MW JSON for either:
      language='en' (Collegiate) or language='es' (Spanish-English).
    If MW returns suggestions (list of strings), we show them.
    """
    if not isinstance(data, list) or not data:
        return "No data returned."

    # If MW returns suggestions rather than entry dicts
    if isinstance(data[0], str):
        suggestions = ", ".join(data[:])
        return f"No exact entry. Did you mean: {suggestions}?"

    for i in range(len(data)):
        entry = data[i] if isinstance(data[i], dict) else {}
        meta = entry.get("meta", {}) or {}
        stems = meta.get("stems", []) or []
        offensive = meta.get("offensive", False)

        hwi = entry.get("hwi", {}) or {}
        headword = hwi.get("hw", "-")
        prs = hwi.get("prs") or []
        ipa = None
        audio_url = None
        if prs and isinstance(prs[0], dict):
            ipa = prs[0].get("mw")
            snd = prs[0].get("sound", {})
            audio = snd.get("audio")
            if audio:
                audio_url = _mw_audio_url(audio)

        pos = entry.get("fl", "-")

        # Definitions: prefer def.sseq (rich), fallback to shortdef
        definitions: List[str] = []
        defs = entry.get("def") or []
        if defs and isinstance(defs[0], dict):
            sseq = defs[0].get("sseq")
            # For Spanish, include gender and bilingual examples; for English, no gender but keep examples
            definitions = _extract_definitions_from_sseq(
                sseq,
                include_examples=True,
                include_gender=(language == "es"),
            )

        if not definitions:
            shortdef = entry.get("shortdef") or []
            definitions = [str(x) for x in shortdef if isinstance(x, str)]

        # Variants (uros)
        variants_out: List[str] = []
        for u in entry.get("uros", []) or []:
            ure = u.get("ure")
            ufl = u.get("fl")
            if ure:
                variants_out.append(f"{ure}" + (f" ({ufl})" if ufl else ""))

        # Build final output
        lines: List[str] = []
        lines.append(f"Word: {meta.get('id', headword)}")
        lines.append(f"Headword: {headword}")
        if ipa:
            lines.append(f"Pronunciation: {ipa}")
        if audio_url:
            lines.append(f"Audio: {audio_url}")
        lines.append(f"Part of speech: {pos}")
        lines.append(f"Offensive: {offensive}")

        if stems:
            for i, s in enumerate(stems[:10], start=1):
                lines.append(f"Stem {i}: {s}")

        if variants_out:
            lines.append("Variants:")
            for v in variants_out:
                lines.append(f"  • {v}")

        if definitions:
            lines.append("{")
            for i, d in enumerate(definitions, start=1):
                lines.append(f"    Definition {i} {d}")
            lines.append("}")
        else:
            lines.append("No definitions found.")

        return "\n".join(lines)

def main():
    data = fetch_mw_english_json(word = "fucker")

    print(format_mw_entries(data, language="en"))

if __name__ == "__main__":
    main()