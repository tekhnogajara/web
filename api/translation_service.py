# import threading
# from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
# import torch

# MODEL_NAME = "facebook/m2m100_418M"

# # Global model references (lazy loaded)
# _model = None
# _tokenizer = None
# _model_lock = threading.Lock()

# # Thread-safe in-memory cache
# _translation_cache = {}
# _cache_lock = threading.Lock()


# def _load_model():
#     global _model, _tokenizer
    
#     if _model is None:
#         with _model_lock:
#             if _model is None:  # Double check locking
#                 print("🔄 Loading translation model...")
#                 _tokenizer = M2M100Tokenizer.from_pretrained(MODEL_NAME)
#                 _model = M2M100ForConditionalGeneration.from_pretrained(MODEL_NAME)
#                 _model.eval()
#                 print("✅ Translation model loaded successfully")


# def translate_text(text: str, target_lang: str) -> str:
#     """
#     Thread-safe, cached, lazy-loaded translation
#     """
#     if not text:
#         return text

#     cache_key = f"{text}_{target_lang}"

#     # Check cache first
#     with _cache_lock:
#         if cache_key in _translation_cache:
#             return _translation_cache[cache_key]

#     # Load model if not loaded
#     _load_model()

#     # Perform translation
#     _tokenizer.src_lang = "en"
#     encoded = _tokenizer(text, return_tensors="pt")

#     with torch.no_grad():
#         generated_tokens = _model.generate(
#             **encoded,
#             forced_bos_token_id=_tokenizer.get_lang_id(target_lang)
#         )

#     result = _tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

#     # Store in cache
#     with _cache_lock:
#         _translation_cache[cache_key] = result

#     return result




import threading
from googletrans import Translator
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

# Global translator instance (thread-safe in googletrans)
_translator = None
_translator_lock = threading.Lock()

# Caches
_translation_cache = {}
_transliteration_cache = {}
_cache_lock = threading.Lock()

# Map language codes to Indic script identifiers
SCRIPT_MAP = {
    'hi': sanscript.DEVANAGARI,
    'mr': sanscript.DEVANAGARI,
    'gu': sanscript.GUJARATI,
    'pa': sanscript.GURMUKHI,
    'bn': sanscript.BENGALI,
    'ta': sanscript.TAMIL,
    'te': sanscript.TELUGU,
    'kn': sanscript.KANNADA,
    'ml': sanscript.MALAYALAM,
    'or': sanscript.ORIYA,
}

def _get_translator():
    global _translator
    if _translator is None:
        with _translator_lock:
            if _translator is None:
                _translator = Translator()
    return _translator

def translate_text(text: str, target_lang: str) -> str:
    """
    Translate text (e.g., status, payment mode, service names) using Google Translate.
    Cached, thread-safe.
    """
    if not text or target_lang == 'en':
        return text

    cache_key = f"{text}_{target_lang}"
    with _cache_lock:
        if cache_key in _translation_cache:
            return _translation_cache[cache_key]

    translator = _get_translator()
    try:
        result = translator.translate(text, dest=target_lang).text
    except Exception:
        # Fallback: return original text if translation fails
        result = text

    with _cache_lock:
        _translation_cache[cache_key] = result
    return result

def transliterate_name(name: str, target_lang: str) -> str:
    """
    Convert a name (e.g., user name, vendor name) to the target script.
    Uses indic-transliteration for accurate script conversion.
    """
    if not name or target_lang == 'en':
        return name

    cache_key = f"{name}_{target_lang}"
    with _cache_lock:
        if cache_key in _transliteration_cache:
            return _transliteration_cache[cache_key]

    script = SCRIPT_MAP.get(target_lang)
    if script:
        try:
            # Convert from Latin (ISO) to target script using ITRANS scheme
            result = transliterate(name, sanscript.ITRANS, script)
        except Exception:
            result = name
    else:
        # Fallback to regular translation for unsupported scripts
        result = translate_text(name, target_lang)

    with _cache_lock:
        _transliteration_cache[cache_key] = result
    return result