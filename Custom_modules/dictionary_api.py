import httpx, json
from pathlib import Path
from Custom_modules.telegram_bot import send_text  

def get_meaning(word: str, version: str = "v2", timeout: float = 15) -> str:
    url = f"https://api.dictionaryapi.dev/api/{version}/entries/en/{word}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
        data = response.json()
    except Exception:
        return f"'{word}' is not a valid word or the API is unavailable."

    # --- safely unpack top level ---
    if not isinstance(data, list) or not data:
        return f"No data returned for '{word}'."

    general = data[0] if isinstance(data[0], dict) else {}
    w = general.get("word", word)
    phonetic = general.get("phonetic", "—")

    meanings_list = general.get("meanings", [])
    if not meanings_list:
        return f"No meanings found for '{w}'."

    # take first meaning block
    meaning = meanings_list[0] if isinstance(meanings_list[0], dict) else {}
    part_of_speech = meaning.get("partOfSpeech", "—")

    definitions = meaning.get("definitions", [])
    if not definitions:
        return f"No definitions available for '{w}'."

    lines = []
    lines.append(f"Word: {w}")
    lines.append(f"Phonetic: {phonetic}")
    lines.append(f"Part of speech: {part_of_speech}")
    lines.append("{")

    for k, d in enumerate(definitions, start=1):
        if not isinstance(d, dict):
            continue
        defn = d.get("definition", "—")
        lines.append(f"    Definition {k}: {defn}")

        syns = d.get("synonyms", []) or []
        for i, syn in enumerate(syns, start=1):
            lines.append(f"        Synonym {i}: {syn}")

        ants = d.get("antonyms", []) or []
        for j, ant in enumerate(ants, start=1):
            lines.append(f"        Antonym {j}: {ant}")

    lines.append("}")

    # optional: top-level synonyms/antonyms under the meaning
    top_syns = meaning.get("synonyms", []) or []
    for i, syn in enumerate(top_syns, start=1):
        lines.append(f"Synonym {i}: {syn}")

    top_ants = meaning.get("antonyms", []) or []
    for j, ant in enumerate(top_ants, start=1):
        lines.append(f"Antonym {j}: {ant}")

    return "\n".join(lines)

def main():
    print(get_meaning(word="porn"))

if __name__ == "__main__":
    main()
