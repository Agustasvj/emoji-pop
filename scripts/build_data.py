#!/usr/bin/env python3
"""
Build the bundled, compressed emoji dataset for Emoji Pop.
Compiles standard Unicode emoji sequences, categories, names, CLDR keywords,
search aliases, skin-tone modifiable sets, and kaomoji into emoji_data.json.gz.
"""

import os
import re
import glob
import json
import gzip
from pathlib import Path

ROFIMOJI_DIR = "/home/sierra/.local/share/pipx/venvs/rofimoji/lib/python3.12/site-packages/picker/data"
EMOJI_PICKER_PY = "/usr/share/emoji-picker/emoji_data.py"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "emoji_pop" / "assets" / "emoji_data.json.gz"
OUTPUT_RAW_PATH = Path(__file__).resolve().parent.parent / "emoji_pop" / "assets" / "emoji_data.json"

# Curated English aliases and intent boosters for top queries
COMMON_ALIASES = {
    # Smileys
    "😂": ["laugh", "crying laughing", "lol", "lmao", "haha", "rofl", "funny"],
    "🤣": ["laugh", "rolling on the floor", "rofl", "lmao", "lol", "haha", "hilarious"],
    "😆": ["laugh", "xd", "grin", "haha"],
    "😅": ["sweat", "nervous", "relief", "awkward"],
    "😀": ["smile", "grin", "happy"],
    "😃": ["smile", "happy", "joy"],
    "😄": ["smile", "happy", "laugh"],
    "😊": ["smile", "blush", "happy", "warm", "kind"],
    "🙂": ["smile", "slight smile", "fine", "ok"],
    "🙃": ["upside down", "sarcasm", "irony", "silly"],
    "😉": ["wink", "flirt"],
    "😍": ["love", "heart eyes", "crush", "in love", "adore"],
    "🥰": ["love", "hearts", "cute", "affection", "adore"],
    "😘": ["kiss", "love", "blow kiss"],
    "😋": ["yummy", "delicious", "food", "tasty", "nom"],
    "😎": ["cool", "sunglasses", "swag", "awesome"],
    "🥳": ["party", "celebrate", "birthday", "tada", "yay"],
    "🤔": ["thinking", "hmm", "ponder", "wonder"],
    "🤨": ["eyebrow", "suspicious", "doubt", "skeptical"],
    "😐": ["neutral", "meh", "poker face", "straight face"],
    "😑": ["expressionless", "done", "annoyed"],
    "🙄": ["eye roll", "whatever", "bored"],
    "😬": ["grimace", "awkward", "oops", "yikes"],
    "🥺": ["pleading", "puppy eyes", "begging", "please"],
    "😢": ["cry", "sad", "tear"],
    "😭": ["cry", "sob", "crying", "sad", "bawling"],
    "😱": ["scream", "shocked", "fear", "scared"],
    "🤯": ["mind blown", "exploding head", "shocked", "wow"],
    "🥵": ["hot", "sweating", "spicy"],
    "🥶": ["cold", "freezing", "ice"],
    "😴": ["sleep", "tired", "sleepy", "zzz"],
    "🤮": ["vomit", "barf", "puke", "gross", "sick"],
    "🤧": ["sneeze", "sick", "cold"],
    "💀": ["skull", "dead", "died", "skeleton"],
    "💩": ["poop", "poo", "crap"],

    # Gestures / People
    "👍": ["thumbs up", "yes", "ok", "good", "approve", "like", "+1"],
    "👎": ["thumbs down", "no", "bad", "dislike", "-1"],
    "👏": ["clap", "applause", "bravo", "praise"],
    "🙌": ["raising hands", "praise", "celebration", "hooray"],
    "🫶": ["heart hands", "love", "care"],
    "🙏": ["pray", "please", "thank you", "thanks", "gratitude", "namaste"],
    "✌️": ["peace", "v sign", "victory"],
    "🤞": ["fingers crossed", "luck", "hope"],
    "🤟": ["love you", "ily", "rock on"],
    "🤘": ["rock on", "metal", "horns"],
    "👌": ["ok", "perfect", "okay", "fine"],
    "🤌": ["chef kiss", "italian", "pinched fingers"],
    "👈": ["point left"],
    "👉": ["point right"],
    "👆": ["point up"],
    "👇": ["point down"],
    "👋": ["wave", "hello", "hi", "bye", "goodbye"],
    "🤝": ["handshake", "deal", "agree"],
    "💪": ["muscle", "flex", "strong", "power", "fitness"],

    # Objects / Symbols
    "🔥": ["fire", "lit", "hot", "flame", "burn"],
    "❤️": ["heart", "love", "red heart"],
    "💖": ["sparkle heart", "love", "cute"],
    "💕": ["two hearts", "love", "pink"],
    "💔": ["broken heart", "sad", "heartbreak"],
    "💯": ["100", "hundred", "perfect", "keep it 100"],
    "✨": ["sparkles", "shine", "magic", "stars", "clean", "glitter"],
    "⭐": ["star", "favorite", "yellow star"],
    "🌟": ["glowing star", "shine", "sparkle"],
    "🎉": ["tada", "party", "celebration", "congrats", "confetti"],
    "🚀": ["rocket", "to the moon", "launch", "fast", "ship"],
    "💡": ["bulb", "idea", "light bulb", "invention"],
    "👀": ["eyes", "look", "see", "watching"],
    "☕": ["coffee", "tea", "cafe", "morning"],
    "🍕": ["pizza", "food", "cheese"],
    "🍔": ["burger", "hamburger", "cheeseburger", "fast food"],
    "🍺": ["beer", "drink", "alcohol", "cheers"],
    "🍻": ["beers", "cheers", "clinking mugs"],
    "🍷": ["wine", "glass", "drink"],
    "🐱": ["cat", "kitty", "kitten", "meow"],
    "🐶": ["dog", "puppy", "woof", "doggo"],
    "🌈": ["rainbow", "pride", "colors"],
    "☀️": ["sun", "sunny", "weather", "summer"],
    "🌙": ["moon", "crescent", "night"],
    "Check": ["✔️", "✅"],
    "Cross": ["❌", "❎"],
}

# Kaomoji dataset (Windows 11 style)
KAOMOJI_LIST = [
    {"text": "¯\\_(ツ)_/¯", "name": "shrug", "category": "classic"},
    {"text": "(╯°□°)╯︵ ┻━┻", "name": "table flip", "category": "rage"},
    {"text": "┬─┬ノ( º _ ºノ)", "name": "put table back", "category": "classic"},
    {"text": "( ͡° ͜ʖ ͡°)", "name": "lenny face", "category": "classic"},
    {"text": "ಠ_ಠ", "name": "look of disapproval", "category": "classic"},
    {"text": "(✿◠‿◠)", "name": "flower smile", "category": "happy"},
    {"text": "(*^▽^*)", "name": "beaming joy", "category": "happy"},
    {"text": "(｡♥‿♥｡)", "name": "heart eyes", "category": "love"},
    {"text": "(づ｡◕‿‿◕｡)づ", "name": "hug", "category": "happy"},
    {"text": "(◕‿◕✿)", "name": "sweet flower", "category": "happy"},
    {"text": "\\(^o^)/", "name": "cheering", "category": "happy"},
    {"text": "(＾▽＾)", "name": "happy grin", "category": "happy"},
    {"text": "(｡•́︿•̀｡)", "name": "pouting sad", "category": "sad"},
    {"text": "(ಥ﹏ಥ)", "name": "crying tears", "category": "sad"},
    {"text": "(╥﹏╥)", "name": "sobbing", "category": "sad"},
    {"text": "(T_T)", "name": "crying", "category": "sad"},
    {"text": "(>_<)", "name": "troubled", "category": "sad"},
    {"text": "ʕ•ᴥ•ʔ", "name": "bear", "category": "animals"},
    {"text": "(=^･ω･^=)", "name": "cat face", "category": "animals"},
    {"text": "(=\^·\^=)", "name": "cute cat", "category": "animals"},
    {"text": "(ᵔᴥᵔ)", "name": "happy bear", "category": "animals"},
    {"text": "(♥‿♥)", "name": "love", "category": "love"},
    {"text": "(♡´౪´♡)", "name": "in love", "category": "love"},
    {"text": "(ღ˘⌣˘ღ)", "name": "peaceful love", "category": "love"},
    {"text": "(⊙_⊙)", "name": "shocked eyes", "category": "surprised"},
    {"text": "(°o°)", "name": "open mouth", "category": "surprised"},
    {"text": "Σ(°ロ°)", "name": "gasped", "category": "surprised"},
    {"text": "(•_•)", "name": "calm", "category": "classic"},
    {"text": "(•_•) ( •_•)>⌐■-■ (⌐■_■)", "name": "deal with it", "category": "classic"},
]


def load_cldr_categories():
    categories = {}
    all_emojis = {}

    category_order = [
        "smileys_emotion",
        "people_body",
        "animals_nature",
        "food_drink",
        "travel_places",
        "activities",
        "objects",
        "symbols",
        "flags"
    ]

    for cat_key in category_order:
        csv_path = os.path.join(ROFIMOJI_DIR, f"emojis_{cat_key}.csv")
        if not os.path.exists(csv_path):
            continue
        items = []
        with open(csv_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"^(\S+)\s+(.+?)(?:\s+<small>\((.*?)\)</small>)?$", line)
                if match:
                    char, name, kw_str = match.groups()
                    keywords = [k.strip() for k in kw_str.split(",")] if kw_str else []
                    
                    # Merge curated aliases
                    if char in COMMON_ALIASES:
                        for alias in COMMON_ALIASES[char]:
                            if alias not in keywords:
                                keywords.append(alias)
                    
                    item = {
                        "char": char,
                        "name": name,
                        "keywords": keywords,
                        "category": cat_key
                    }
                    items.append(item)
                    all_emojis[char] = item
        categories[cat_key] = items

    return categories, all_emojis


def load_skin_tone_metadata():
    """Load sets of emojis that support skin tone and gender modifications."""
    skin_tone_emojis = set()
    gender_emojis = set()
    gender_swap_emojis = set()

    if os.path.exists(EMOJI_PICKER_PY):
        import sys
        sys.path.insert(0, "/usr/share/emoji-picker")
        try:
            import emoji_data
            if hasattr(emoji_data, "SKIN_TONE_EMOJIS"):
                skin_tone_emojis = set(emoji_data.SKIN_TONE_EMOJIS)
            if hasattr(emoji_data, "GENDER_EMOJIS"):
                gender_emojis = set(emoji_data.GENDER_EMOJIS)
            if hasattr(emoji_data, "GENDER_SWAP_EMOJIS"):
                gender_swap_emojis = set(emoji_data.GENDER_SWAP_EMOJIS)
        except Exception as e:
            print("Notice: could not import emoji_data directly:", e)

    return {
        "skin_tone_emojis": sorted(list(skin_tone_emojis)),
        "gender_emojis": sorted(list(gender_emojis)),
        "gender_swap_emojis": sorted(list(gender_swap_emojis)),
        "skin_tones": [
            {"code": "", "name": "Default", "sample": "🟡"},
            {"code": "\U0001F3FB", "name": "Light", "sample": "🏻"},
            {"code": "\U0001F3FC", "name": "Medium-Light", "sample": "🏼"},
            {"code": "\U0001F3FD", "name": "Medium", "sample": "🏽"},
            {"code": "\U0001F3FE", "name": "Medium-Dark", "sample": "🏾"},
            {"code": "\U0001F3FF", "name": "Dark", "sample": "🏿"},
        ]
    }


def main():
    print("Loading CLDR emoji datasets...")
    categories, all_emojis = load_cldr_categories()
    print(f"Loaded {len(all_emojis)} unique emojis across {len(categories)} categories.")

    modifier_meta = load_skin_tone_metadata()
    print(f"Loaded {len(modifier_meta['skin_tone_emojis'])} skin-tone modifiable emojis.")

    bundle = {
        "version": "1.0.0",
        "unicode_version": "15.1",
        "categories": categories,
        "modifier_meta": modifier_meta,
        "kaomoji": KAOMOJI_LIST,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Save gzipped JSON
    raw_json = json.dumps(bundle, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    with gzip.open(OUTPUT_PATH, 'wb') as fp:
        fp.write(raw_json)

    # Also save raw JSON for development/inspection
    with open(OUTPUT_RAW_PATH, 'w', encoding='utf-8') as fp:
        json.dump(bundle, fp, ensure_ascii=False, indent=2)

    print(f"Saved gzipped bundle to {OUTPUT_PATH} ({len(raw_json)/1024:.1f} KB uncompressed, {OUTPUT_PATH.stat().st_size/1024:.1f} KB compressed)")
    print("Done building emoji data.")


if __name__ == "__main__":
    main()
