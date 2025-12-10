import random, datetime
from typing import Optional
from wordfreq import top_n_list
from Custom_modules.dictionary_api_v2 import (fetch_mw_english_json, fetch_mw_spanish_json, format_mw_entries)
from Custom_modules.telegram_bot import send_text
from important_info.API_loader import env

EN_LIST_SIZE = 200000
ES_LIST_SIZE = 200000
RARE_LIST_SIZE = 50000
MAX_ATTEMPT = 12
CHAT_ID = env("BOT_OWNER_ID")

def pick_random_word(langugage : str, pool_size : int, rare_list_size : int) -> str:
    words = top_n_list(langugage, n=pool_size)
    words = [w for w in words if w.isalpha() and len(w) > 2]
    words.reverse()
    rare_words = words[:rare_list_size]
    return random.choice(rare_words)

def get_random_en_word(max_tries : int) -> Optional[tuple[str:str]]:
    for _ in range(max_tries):
        w = pick_random_word(langugage="en", pool_size=EN_LIST_SIZE, rare_list_size=RARE_LIST_SIZE)
        try:
            data = fetch_mw_english_json(w)
        except Exception:
            continue
        if isinstance(data, list) and data:
            text = format_mw_entries(data, language="en")
            return w, text
    return None

def get_random_es_word(max_tries : int) -> Optional[tuple[str:str]]:
    for _ in range(max_tries):
        w = pick_random_word(langugage="es", pool_size=ES_LIST_SIZE, rare_list_size=RARE_LIST_SIZE)
        try:
            data = fetch_mw_spanish_json(w)
        except Exception:
            continue
        if isinstance(data, list) and data:
            text = format_mw_entries(data, language="es")
            return w, text
    return None

def build_message() -> str:
    today = datetime.datetime.today().strftime("%d-%m-%Y")
    lines = [f"Daily word - {today}", ""]
    
    eng_word = get_random_en_word(max_tries=MAX_ATTEMPT)
    if eng_word:
        w, text = eng_word
        lines.append(f"English: {w}")
        lines.append(text)
    else:
        lines.append(f"English: (failed to find a word today)")
        
    lines.append("\n***************************************************************************************\n")
    
    es_word = get_random_es_word(max_tries=MAX_ATTEMPT)
    if es_word:
        w, text = es_word
        lines.append(f"Spanish: {w}")
        lines.append(text)
    else:
        lines.append(f"Spanish: (failed to find a word today)")
    
    return "\n".join(lines)

def main():
    
    msg = build_message()
    # This is a standalone script, so send_text() (which uses asyncio.run) is fine:
    send_text(msg, CHAT_ID)

if __name__ == "__main__":
    main()