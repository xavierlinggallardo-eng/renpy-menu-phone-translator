"""
Motor de traducción — wrapper simple sobre las APIs.
Motor por defecto: Google Translate gratuito (sin API key).
También soporta Gemini, LibreTranslate y DeepL.
Incluye caché para no re-traducir.
"""

import json
import os
import hashlib
import time
import re
from typing import List, Optional, Dict

CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache.json")

# Preservar tokens especiales de Ren'Py
_TOKEN_RE = re.compile(r'(\{[^}]*\}|\[[^\]]*\]|%[sdifg]|\\[ntr]|<[^>]+>)')

def _protect(text):
    tokens = []
    def r(m):
        tokens.append(m.group(0))
        return f"__T{len(tokens)-1}__"
    return _TOKEN_RE.sub(r, text), tokens

def _restore(text, tokens):
    for i, t in enumerate(tokens):
        text = text.replace(f"__T{i}__", t)
    return text


class Cache:
    def __init__(self, path=CACHE_FILE):
        self.path = path
        self._data: Dict[str, str] = {}
        self._load()

    def _key(self, text, lang, engine):
        return hashlib.md5(f"{engine}|{lang}|{text}".encode()).hexdigest()

    def get(self, text, lang, engine):
        return self._data.get(self._key(text, lang, engine))

    def set(self, text, lang, engine, result):
        self._data[self._key(text, lang, engine)] = result
        self._save()

    def bulk_set(self, pairs, lang, engine):
        for text, result in pairs.items():
            self._data[self._key(text, lang, engine)] = result
        self._save()

    def size(self):
        return len(self._data)

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except: pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except: pass


class GeminiTranslator:
    BATCH = 40

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._model = None
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._model = genai.GenerativeModel(
                    "gemini-1.5-flash",
                    system_instruction=(
                        "Eres un traductor profesional de videojuegos. "
                        "Traduce SOLO el texto. Preserva {variables}, [nombres], %s, \\n exactamente. "
                        "Sin explicaciones. Solo la traducción."
                    )
                )
            except: pass

    @property
    def available(self):
        return bool(self.api_key and self._model)

    def translate_batch(self, texts: List[str], lang: str) -> List[Optional[str]]:
        if not self.available:
            return [None] * len(texts)
        results = [None] * len(texts)
        for i in range(0, len(texts), self.BATCH):
            batch = texts[i:i+self.BATCH]
            protected, tok_list = [], []
            for t in batch:
                p, toks = _protect(t)
                protected.append(p); tok_list.append(toks)
            for attempt in range(3):
                try:
                    if len(protected) == 1:
                        prompt = f"Traduce al {lang}:\n{protected[0]}"
                        r = self._model.generate_content(prompt)
                        translated = [r.text.strip() if r.text else None]
                    else:
                        lines = "\n".join(f"{j+1}. {t}" for j,t in enumerate(protected))
                        prompt = (f"Traduce cada línea al {lang}. "
                                  f"Devuelve SOLO las traducciones, una por línea, mismo orden, sin numeración.\n\n{lines}")
                        r = self._model.generate_content(prompt)
                        raw = r.text.strip() if r.text else ""
                        translated = [re.sub(r'^\d+\.\s*','',l.strip()) for l in raw.split('\n')]
                        while len(translated) < len(protected): translated.append(None)
                        translated = translated[:len(protected)]
                    for j,(t,toks) in enumerate(zip(translated, tok_list)):
                        results[i+j] = _restore(t, toks) if t else None
                    break
                except Exception as e:
                    err = str(e)
                    if '429' in err or 'quota' in err.lower():
                        time.sleep(8 * (attempt+1))
                    elif attempt < 2:
                        time.sleep(3)
        return results


class LibreTranslator:
    BATCH = 20

    def __init__(self, url: str, api_key: str = ""):
        self.url = url.rstrip("/")
        self.api_key = api_key

    @property
    def available(self):
        try:
            import requests
            r = requests.get(f"{self.url}/languages", timeout=5)
            return r.status_code == 200
        except: return False

    _LANG = {
        "Spanish":"es","French":"fr","German":"de","Italian":"it",
        "Portuguese":"pt","Russian":"ru","Japanese":"ja","Chinese":"zh",
        "Korean":"ko","Dutch":"nl","Polish":"pl","Turkish":"tr","Ukrainian":"uk",
    }

    def translate_batch(self, texts, lang):
        import requests
        tgt = self._LANG.get(lang, lang.lower()[:2])
        results = [None] * len(texts)
        for i, text in enumerate(texts):
            protected, toks = _protect(text)
            for attempt in range(3):
                try:
                    payload = {"q": protected, "source": "en", "target": tgt, "format": "text"}
                    if self.api_key: payload["api_key"] = self.api_key
                    r = requests.post(f"{self.url}/translate", json=payload, timeout=20)
                    if r.status_code == 200:
                        results[i] = _restore(r.json().get("translatedText",""), toks)
                        break
                except Exception:
                    if attempt < 2: time.sleep(2)
        return results


class DeepLTranslator:
    _LANG = {
        "Spanish":"ES","French":"FR","German":"DE","Italian":"IT",
        "Portuguese":"PT-PT","Russian":"RU","Japanese":"JA","Chinese":"ZH",
        "Korean":"KO","Dutch":"NL","Polish":"PL","Ukrainian":"UK",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._t = None
        if api_key:
            try:
                import deepl
                self._t = deepl.Translator(api_key)
            except: pass

    @property
    def available(self):
        return bool(self.api_key and self._t)

    def translate_batch(self, texts, lang):
        if not self.available: return [None]*len(texts)
        tgt = self._LANG.get(lang, lang.upper())
        protected_list, tok_list = [], []
        for t in texts:
            p, toks = _protect(t)
            protected_list.append(p); tok_list.append(toks)
        try:
            translated = self._t.translate_text(protected_list, target_lang=tgt, source_lang="EN")
            return [_restore(r.text, toks) for r,toks in zip(translated, tok_list)]
        except: return [None]*len(texts)


class GoogleFreeTranslator:
    """
    Google Translate GRATUITO — sin API key, sin límites duros.
    Usa googletrans (wrapper no oficial) o deep_translator como fallback.
    """
    BATCH = 50

    def __init__(self):
        self._engine = None
        self._engine_name = ""
        self._init()

    def _init(self):
        # Intento 1: deep_translator (más estable)
        try:
            from deep_translator import GoogleTranslator
            # Test rápido
            GoogleTranslator(source='en', target='es').translate('hello')
            self._engine = 'deep_translator'
            self._engine_name = 'Google Translate (gratis)'
            return
        except Exception:
            pass
        # Intento 2: googletrans
        try:
            from googletrans import Translator as GT
            t = GT()
            t.translate('hello', dest='es')
            self._engine = 'googletrans'
            self._engine_name = 'Google Translate (gratis)'
            return
        except Exception:
            pass

    @property
    def available(self):
        return self._engine is not None

    _LANG = {
        "Spanish":"es","French":"fr","German":"de","Italian":"it",
        "Portuguese":"pt","Russian":"ru","Japanese":"ja","Chinese":"zh-cn",
        "Korean":"ko","Arabic":"ar","Dutch":"nl","Polish":"pl",
        "Turkish":"tr","Ukrainian":"uk","Czech":"cs","Swedish":"sv",
        "Romanian":"ro","Greek":"el","Hungarian":"hu","Finnish":"fi",
        "Hindi":"hi","Vietnamese":"vi","Indonesian":"id","Thai":"th",
    }

    def translate_batch(self, texts: List[str], lang: str) -> List[Optional[str]]:
        if not self.available:
            return [None] * len(texts)
        tgt = self._LANG.get(lang, lang.lower()[:2])
        results = []
        for text in texts:
            protected, toks = _protect(text)
            translated = self._translate_one(protected, tgt)
            results.append(_restore(translated, toks) if translated else None)
            time.sleep(0.05)  # pequeña pausa para no ser bloqueado
        return results

    def _translate_one(self, text: str, tgt: str) -> Optional[str]:
        for attempt in range(3):
            try:
                if self._engine == 'deep_translator':
                    from deep_translator import GoogleTranslator
                    return GoogleTranslator(source='en', target=tgt).translate(text)
                elif self._engine == 'googletrans':
                    from googletrans import Translator as GT
                    t = GT()
                    result = t.translate(text, src='en', dest=tgt)
                    return result.text
            except Exception as e:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        return None


def make_translator(config: dict):
    """
    Crea el mejor traductor disponible.
    Orden de prioridad:
      1. Google Translate gratis (sin key — predeterminado)
      2. Google Gemini (si hay API key)
      3. DeepL (si hay API key)
      4. LibreTranslate
    """
    # 1. Google Translate gratis — siempre intentar primero
    gt = GoogleFreeTranslator()
    if gt.available:
        # Si hay Gemini key, usar Gemini (mejor calidad)
        if config.get("gemini_api_key"):
            g = GeminiTranslator(config["gemini_api_key"])
            if g.available:
                return g, "Google Gemini"
        return gt, gt._engine_name

    # 2. Gemini con key
    if config.get("gemini_api_key"):
        g = GeminiTranslator(config["gemini_api_key"])
        if g.available:
            return g, "Google Gemini"

    # 3. DeepL
    if config.get("deepl_api_key"):
        t = DeepLTranslator(config["deepl_api_key"])
        if t.available:
            return t, "DeepL"

    # 4. LibreTranslate
    url = config.get("libre_url", "https://libretranslate.com")
    t = LibreTranslator(url, config.get("libre_api_key",""))
    if t.available:
        return t, "LibreTranslate"

    return None, None


def translate_all(
    segments,
    engine,
    engine_name: str,
    target_lang: str,
    cache: Cache,
    log=None,
    progress=None,
) -> Dict[int, str]:
    """Traduce todos los segmentos usando caché."""
    _log = log or (lambda m: None)
    translations: Dict[int, str] = {}

    # Deduplicar
    unique: Dict[str, List[int]] = {}
    for seg in segments:
        unique.setdefault(seg.text, []).append(seg.line)

    all_texts = list(unique.keys())
    to_translate = []
    cache_hits = 0

    for text in all_texts:
        cached = cache.get(text, target_lang, engine_name)
        if cached:
            for line_no in unique[text]:
                translations[line_no] = cached
            cache_hits += 1
        else:
            to_translate.append(text)

    _log(f"Caché: {cache_hits}/{len(all_texts)} hits. Traduciendo {len(to_translate)} nuevos...")

    BATCH = 40
    done = 0
    for i in range(0, len(to_translate), BATCH):
        batch = to_translate[i:i+BATCH]
        try:
            results = engine.translate_batch(batch, target_lang)
        except Exception as e:
            _log(f"Error de motor: {e}")
            results = [None] * len(batch)

        new_pairs = {}
        for text, result in zip(batch, results):
            if result:
                new_pairs[text] = result
                for line_no in unique[text]:
                    translations[line_no] = result
            else:
                _log(f"  Sin traducción: {text[:50]!r}")

        if new_pairs:
            cache.bulk_set(new_pairs, target_lang, engine_name)

        done += len(batch)
        if progress:
            progress(cache_hits + done, len(all_texts))

    _log(f"Traducidos: {len(translations)}/{len(segments)} segmentos.")
    return translations
