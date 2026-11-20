# middleware/language_middleware.py
from django.utils.deprecation import MiddlewareMixin
from ..redis_config import redis_client  # Use relative import to go up one level
import hashlib
import json

class LanguageMiddleware(MiddlewareMixin):
    """
    Middleware to handle language preferences and caching
    """
    SUPPORTED_LANGUAGES = ['en', 'hi', 'mr', 'gu']
    DEFAULT_LANGUAGE = 'en'
    
    def process_request(self, request):
        # Get language from various sources with priority:
        # 1. Query param
        # 2. Header
        # 3. Session
        # 4. Cookie
        # 5. Default
        
        lang = request.GET.get('lang', '')
        
        if not lang:
            lang = request.headers.get('Accept-Language', '').split(',')[0][:2]
        
        if not lang and hasattr(request, 'session'):
            lang = request.session.get('language', '')
        
        if not lang:
            lang = request.COOKIES.get('language', '')
        
        # Validate language
        if lang not in self.SUPPORTED_LANGUAGES:
            lang = self.DEFAULT_LANGUAGE
        
        request.language = lang
        
        # Create translation cache key for this request
        request.translation_cache = {}
    
    def process_response(self, request, response):
        # Set language cookie if needed
        if hasattr(request, 'language') and request.language:
            response.set_cookie('language', request.language, max_age=31536000)  # 1 year
        
        return response

def get_current_language(request):
    """Helper to get current language"""
    return getattr(request, 'language', 'en')

def cached_translate(text, target_lang, request=None):
    """
    Cached translation using Redis
    """
    if target_lang == 'en':
        return text
    
    # Generate cache key
    cache_key = hashlib.md5(f"trans:{text}:{target_lang}".encode()).hexdigest()
    
    # Check request cache first (faster)
    if request and hasattr(request, 'translation_cache'):
        if cache_key in request.translation_cache:
            return request.translation_cache[cache_key]
    
    # Check Redis cache
    cached = redis_client.get(cache_key)
    if cached:
        if request:
            request.translation_cache[cache_key] = cached
        return cached
    
    # Perform translation
    from googletrans import Translator
    translator = Translator()
    
    try:
        translated = translator.translate(text, dest=target_lang).text
        
        # Cache in Redis (24 hours)
        redis_client.set(cache_key, translated, timeout=86400)
        
        # Cache in request
        if request:
            request.translation_cache[cache_key] = translated
        
        return translated
    except:
        return text