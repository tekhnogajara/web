# auth.py
from django.contrib.auth.hashers import make_password, check_password
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication

def hash_password(password: str) -> str:
    return make_password(password)


def verify_password(plain: str, hashed: str) -> bool:
    return check_password(plain, hashed)


def create_jwt_token(user):
    """Your original token generator"""
    refresh = RefreshToken.for_user(user)
    refresh["user_id"] = user.user_id
    refresh["role_id"] = user.role_id
    refresh["contact_number"] = user.contact_number
    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
    }


def decode_access_token(token: str):
    """Decode JWT token"""
    try:
        decoded = AccessToken(token)
        return decoded.payload
    except TokenError:
        return None


def get_user_from_token(request):
    """
    Extract user data from Authorization: Bearer <token>
    Returns None if token is missing/invalid
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    payload = decode_access_token(token)
    
    if not payload:
        return None

    return {
        "user_id": payload.get("user_id"),
        "role_id": payload.get("role_id"),
        "contact_number": payload.get("contact_number"),
        "full_payload": payload  # for debugging
    }