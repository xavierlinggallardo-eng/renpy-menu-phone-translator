import json, os

DEFAULT = {
    "gemini_api_key": "",
    "deepl_api_key": "",
    "libre_url": "https://libretranslate.com",
    "libre_api_key": "",
    "target_lang": "Spanish",
}

def _path():
    if os.name == "nt":
        base = os.environ.get("APPDATA", "")
        if base:
            return os.path.join(base, "RenpyMenuTranslator", "config.json")
    return os.path.join(os.path.dirname(__file__), "config.json")

def load():
    cfg = dict(DEFAULT)
    p = _path()
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                cfg.update(json.load(f))
        except: pass
    return cfg

def save(cfg):
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
