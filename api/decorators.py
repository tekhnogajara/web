from functools import wraps
from django.db import connection
from rest_framework.response import Response
from rest_framework import status

def check_user_active(user_id, role_id=None):
    """
    Check if user is active and (if vendor) approved.
    Raises an exception with a user-friendly message if not.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT active_status, is_approved FROM tbl_user WHERE user_id = %s", [user_id])
        row = cursor.fetchone()
        if not row:
            raise Exception("User not found.")
        active_status, is_approved = row
        if active_status != '1':
            raise Exception("Your access has been removed. Please contact admin.")
        if role_id == '3' and is_approved != 'approved':
            raise Exception("Your vendor account is not approved. Please contact admin.")

def active_user_required(view_func):
    """
    Decorator that checks if the authenticated user is active and (if vendor) approved.
    It extracts token_user and attaches it to request for later use.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        from .auth import get_user_from_token
        token_user = get_user_from_token(request)
        if not token_user:
            return Response(
                {"success": False, "error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user_id = token_user.get('user_id')
        role_id = token_user.get('role_id')
        try:
            check_user_active(user_id, role_id)
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        # Attach token_user to request so views can use it
        request.token_user = token_user
        return view_func(request, *args, **kwargs)
    return _wrapped_view