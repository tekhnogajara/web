from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import UserInfo
from .serializers import UserInfoSerializer
from django.db import connection
from Gajara.azure_storage import AzureStorageService
from django.conf import settings
import traceback
# from googletrans import Translator
# translator = Translator()
from rest_framework.permissions import AllowAny
from .services.otp_service import otp_service
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from datetime import datetime
import traceback
import random
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .vendor_services import VendorService
from django.utils import timezone
from asgiref.sync import async_to_sync 
from .translation_service import translate_text
from .translation_service import transliterate_name
from .decorators import check_user_active
from functools import wraps
from .decorators import active_user_required
import logging
logger = logging.getLogger(__name__)
# from .utils import utc_to_ist

# # storage
storage_service = AzureStorageService()
# # lat-long/address
GEOAPIFY_KEY = "bc2d5167c65e43449465f53b79f3c735"

def get_lat_long_from_address(text):
    url = f"https://api.geoapify.com/v1/geocode/search?text={text}&apiKey={GEOAPIFY_KEY}"
    resp = requests.get(url)
    data = resp.json()

    if not data.get("features"):
        return None, None

    props = data["features"][0]["properties"]
    return props.get("lat"), props.get("lon")


 
@csrf_exempt
def get_address_from_lat_lon(request):
    if request.method == "POST":
        # Read from form-data
        lat = request.POST.get("lat")
        lon = request.POST.get("lon")
 
        if not lat or not lon:
            return JsonResponse({"error": "lat and lon are required"}, status=400)
 
        url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={GEOAPIFY_KEY}"
        r = requests.get(url)
        data = r.json()
 
        if "features" in data and len(data["features"]) > 0:
            address = data["features"][0]["properties"]["formatted"]
            return JsonResponse({"address": address})
        else:
            return JsonResponse({"error": "Address not found"}, status=404)


def generate_jwt_token(user):
    refresh = RefreshToken.for_user(user)

    # Custom claims - use user_id as the primary key field name
    refresh["user_id"] = user.user_id  # This matches your model's primary key
    refresh["role_id"] = user.role_id
    refresh["contact_number"] = user.contact_number

    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
    }

def format_number(number):
    """Ensure number is in correct format (just basic strip here, no +91)"""
    return number.strip()


def get_logged_in_role_id(request):
    """
    Helper function to extract logged-in user's role_id from request
    Priority order:
    1. Authenticated user's role_id (if using Django auth)
    2. Session-based role_id
    3. Header-based role_id (X-Role-ID)
    4. Fallback to '4' (User role) for self-registration
    """
    if hasattr(request, 'user') and request.user.is_authenticated:
        if hasattr(request.user, 'role_id'):
            return str(request.user.role_id)

    if hasattr(request, 'session') and request.session.get('role_id'):
        return str(request.session.get('role_id'))

    if request.headers.get('X-Role-ID'):
        return str(request.headers.get('X-Role-ID'))

    return '4'  # Default to User role


@api_view(['GET'])
def init_azure_containers(request):
    """Initialize Azure containers - run once"""
    try:
        azure_service = AzureStorageService()
        azure_service.create_containers()
        return Response({
            "success": True,
            "message": "Azure containers initialized successfully"
        })
    except Exception as e:
        return Response({
            "success": False,
            "error": str(e)
        }, status=500)
        
        
        
        
from django.db import connection

def get_role_name(role_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM tbl_role WHERE id = %s", [role_id])
        row = cursor.fetchone()
        return row[0] if row else None




# @api_view(['POST'])
# @permission_classes([AllowAny])
# def register_or_login_user(request):
#     """
#     Unified API for User Registration and Login
#     - If user doesn't exist: Register -> Send OTP -> Verify OTP -> Create user -> Auto-login (with vendor approval check)
#     - If user exists: Login flow (OTP or Password) with vendor approval and active status check
#     """
#     azure_service = AzureStorageService()
#     data = request.data

#     contact_number = data.get('contact_number')
#     otp = data.get('otp')
#     password = data.get('password')
#     login_type = data.get('login_type', 'otp')  # 'otp' or 'password'
    
#     # Registration fields (optional, only needed for new users)
#     name = data.get('name')
#     role_id = data.get('role_id')
#     aadhar_number = data.get('aadhar_number')
#     address_text = data.get('address_text')
#     user_lat = data.get('user_lat')
#     user_long = data.get('user_long')

#     if not contact_number:
#         return Response(
#             {
#                 "success": False,
#                 "login_status": "failed",
#                 "error": "contact_number is required"
#             }, 
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Get logged-in user's role_id (for tracking who created)
#     logged_in_role_id = get_logged_in_role_id(request)

#     try:
#         # Check if user exists
#         existing_user = UserInfo.objects.filter(contact_number=contact_number).first()
        
#         # ========== CASE 1: USER EXISTS - LOGIN FLOW ==========
#         if existing_user:
#             # Check if this is registration attempt for existing user
#             if name or role_id or aadhar_number or request.FILES.get('aadhar_img'):
#                 return Response(
#                     {
#                         "success": False,
#                         "login_status": "failed",
#                         "error": "User already registered. Please login instead."
#                     },
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             # ========== CHECK ACTIVE STATUS ==========
#             if existing_user.active_status == '0':
#                 return Response(
#                     {
#                         "success": False,
#                         "login_status": "inactive",
#                         "message": "Your account is inactive. Please contact admin.",
#                         "error": "Account is inactive",
#                         "user_id": existing_user.user_id,
#                         "name": existing_user.name,
#                         "role_id": existing_user.role_id
#                     },
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             # ========== CHECK VENDOR APPROVAL STATUS ==========
#             if str(existing_user.role_id) == '3':  # Vendor role
#                 if existing_user.is_approved == 'pending':
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "pending_approval",
#                             "message": "Your account is pending approval. Please wait or contact admin.",
#                             "error": "Vendor account pending approval",
#                             "approval_status": "pending",
#                             "user_id": existing_user.user_id,
#                             "name": existing_user.name,
#                             "role_id": existing_user.role_id
#                         },
#                         status=status.HTTP_403_FORBIDDEN
#                     )
#                 elif existing_user.is_approved == 'declined':
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "declined",
#                             "message": "Your account has been declined. Please contact admin.",
#                             "error": "Vendor account declined",
#                             "approval_status": "declined",
#                             "user_id": existing_user.user_id,
#                             "name": existing_user.name,
#                             "role_id": existing_user.role_id
#                         },
#                         status=status.HTTP_403_FORBIDDEN
#                     )
#                 # If approved, continue with login

#             # ========== PASSWORD-BASED LOGIN ==========
#             if login_type == 'password' or password:
#                 from .auth import verify_password
                
#                 if not password:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": "Password is required for password login"
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
                
#                 if not existing_user.password:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": "Password not set for this account. Please use OTP login."
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
                
#                 if not verify_password(password, existing_user.password):
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": "Invalid password"
#                         },
#                         status=status.HTTP_401_UNAUTHORIZED
#                     )
                
#                 # Password verified - login successful
#                 existing_user.active_status = '1'
#                 existing_user.save()
                
#                 tokens = generate_jwt_token(existing_user)
                
#                 return Response(
#                     {
#                         "success": True,
#                         "login_status": "success",
#                         "message": "Login successful",
#                         "is_new_user": False,
#                         "data": {
#                             "refresh_token": tokens["refresh_token"],
#                             "access_token": tokens["access_token"],
#                             "user_id": existing_user.user_id,
#                             "name": existing_user.name,
#                             "contact_number": existing_user.contact_number,
#                             "role_id": existing_user.role_id,
#                             "is_approved": existing_user.is_approved if str(existing_user.role_id) == '3' else None
#                         }
#                     },
#                     status=status.HTTP_200_OK
#                 )

#             # ========== OTP-BASED LOGIN ==========
#             # Send OTP if not provided
#             if not otp:
#                 try:
#                     otp_service.sendOtp(contact_number)
#                     return Response(
#                         {
#                             "success": True,
#                             "login_status": "otp_sent",
#                             "message": "OTP sent successfully",
#                             "is_new_user": False,
#                             "data": {"contact_number": contact_number}
#                         },
#                         status=status.HTTP_200_OK
#                     )
#                 except Exception as e:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": f"Failed to send OTP: {str(e)}"
#                         },
#                         status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                     )

#             # Verify OTP
#             otp_result = otp_service.verifyOtp(contact_number, otp)
#             if not otp_result['success']:
#                 return Response(
#                     {
#                         "success": False,
#                         "login_status": "failed",
#                         "error": otp_result['message']
#                     },
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # OTP verified - login successful
#             existing_user.active_status = '1'
#             existing_user.save()
            
#             tokens = generate_jwt_token(existing_user)
            
#             return Response(
#                 {
#                     "success": True,
#                     "login_status": "success",
#                     "message": "Login successful",
#                     "is_new_user": False,
#                     "data": {
#                         "refresh_token": tokens["refresh_token"],
#                         "access_token": tokens["access_token"],
#                         "user_id": existing_user.user_id,
#                         "name": existing_user.name,
#                         "contact_number": existing_user.contact_number,
#                         "role_id": existing_user.role_id,
#                         "is_approved": existing_user.is_approved if str(existing_user.role_id) == '3' else None
#                     }
#                 },
#                 status=status.HTTP_200_OK
#             )

#         # ========== CASE 2: NEW USER - REGISTRATION FLOW ==========
#         else:
#             # Step 1: Send OTP (no data saved yet)
#             if not otp:
#                 # Validate required fields for registration
#                 required_fields = ['name', 'role_id', 'contact_number']
#                 missing_fields = [field for field in required_fields if not data.get(field)]
#                 if missing_fields:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             # "error": f"Missing required fields: {', '.join(missing_fields)}"
#                             "error": "User Not found"  
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 # Upload images to Azure if provided
#                 aadhar_url = None
#                 stamp_url = None
                
#                 if request.FILES.get('aadhar_img'):
#                     aadhar_file = request.FILES['aadhar_img']
#                     aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                
#                 if request.FILES.get('stamp_img'):
#                     stamp_file = request.FILES['stamp_img']
#                     stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)

#                 # Send OTP
#                 try:
#                     otp_service.sendOtp(contact_number)
                    
#                     response_data = {
#                         "success": True,
#                         "login_status": "otp_sent",
#                         "message": "OTP sent successfully. Please verify to complete registration.",
#                         "is_new_user": True,
#                         "next_step": "verify_otp",
#                         "data": {
#                             "contact_number": contact_number,
#                             "name": name,
#                             "role_id": role_id
#                         }
#                     }
                    
#                     # Add optional fields to response
#                     if aadhar_url:
#                         response_data["data"]["aadhar_url"] = aadhar_url
#                     if stamp_url:
#                         response_data["data"]["stamp_url"] = stamp_url
#                     if address_text:
#                         response_data["data"]["address_text"] = address_text
                    
#                     return Response(response_data, status=status.HTTP_200_OK)
                    
#                 except Exception as e:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": f"Failed to send OTP: {str(e)}"
#                         },
#                         status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                     )

#             # Step 2: Verify OTP and create user
#             else:
#                 # Verify OTP
#                 otp_result = otp_service.verifyOtp(contact_number, otp)
#                 if not otp_result['success']:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": otp_result['message']
                            
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 # Get role_id from request data
#                 role_id = data.get('role_id')
#                 role_name = get_role_name(role_id)

#                 # ========== DUPLICATE CHECK FOR AADHAR ==========
#                 if aadhar_number:
#                     if UserInfo.objects.filter(
#                         aadhar_number=aadhar_number,
#                         active_status='1'
#                     ).exists():
#                         return Response(
#                             {
#                                 "success": False,
#                                 "login_status": "failed",
#                                 "error": "Aadhar number already registered with another account"
#                             },
#                             status=status.HTTP_400_BAD_REQUEST
#                         )

#                 # Handle image uploads
#                 aadhar_url = data.get('aadhar_img')
#                 stamp_url = data.get('stamp_img')
                
#                 if request.FILES.get('aadhar_img'):
#                     aadhar_file = request.FILES['aadhar_img']
#                     aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                
#                 if request.FILES.get('stamp_img'):
#                     stamp_file = request.FILES['stamp_img']
#                     stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)

#                 # Hash password if provided
#                 hashed_password = None
#                 if data.get('password'):
#                     from .auth import hash_password
#                     hashed_password = hash_password(data.get('password'))

#                 # ========== HANDLE LOCATION DATA ==========
#                 final_lat = user_lat
#                 final_long = user_long
                
#                 if address_text and not (user_lat and user_long):
#                     try:
#                         lat, lon = get_lat_long_from_address(address_text)
#                         if lat and lon:
#                             final_lat = str(lat)
#                             final_long = str(lon)
#                     except Exception as e:
#                         return Response(
#                             {
#                                 "success": False,
#                                 "login_status": "failed",
#                                 "error": f"Error converting address to coordinates: {str(e)}"
#                             },
#                             status=status.HTTP_400_BAD_REQUEST
#                         )

#                 # Prepare user data
#                 user_data = {
#                     'name': name,
#                     'contact_number': contact_number,
#                     'role_id': role_id,
#                     'aadhar_number': aadhar_number,
#                     'aadhar_img': aadhar_url,
#                     'stamp_img': stamp_url,
#                     'created_by': logged_in_role_id,
#                     'active_status': '1',  # New users are active by default
#                     'user_lat': final_lat,
#                     'user_long': final_long,
#                     'password': hashed_password
#                 }

#                 # Set is_approved for vendors
#                 vendor_message = None
#                 login_status = "success"
                
#                 if str(role_id) == '3':  # Vendor role
#                     user_data['is_approved'] = 'pending'
#                     vendor_message = "Your registration is pending admin approval. You will be able to login once approved."
#                     login_status = "pending_approval"
#                 else:
#                     login_status = "success"

#                 # Remove None values
#                 user_data = {k: v for k, v in user_data.items() if v is not None}

#                 # Create user
#                 serializer = UserInfoSerializer(data=user_data)
                
#                 if serializer.is_valid():
#                     user = serializer.save()
                    
#                     # Generate JWT token (user is logged in automatically)
#                     tokens = generate_jwt_token(user)
                    
#                     response_data = {
#                         "success": True,
#                         "login_status": login_status,
#                         "message": "Registration successful!" if login_status == "success" else vendor_message,
#                         "is_new_user": True,
#                         "data": {
#                             "refresh_token": tokens["refresh_token"],
#                             "access_token": tokens["access_token"],
#                             "user_id": user.user_id,
#                             "name": user.name,
#                             "contact_number": user.contact_number,
#                             "role_id": user.role_id,
#                             "active_status": user.active_status,
#                             "aadhar_url": aadhar_url,
#                             "stamp_url": stamp_url
#                         }
#                     }
                    
#                     # Add vendor approval info if applicable
#                     if str(role_id) == '3':
#                         response_data["data"]["is_approved"] = "pending"
                    
#                     return Response(response_data, status=status.HTTP_201_CREATED)
#                 else:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "errors": serializer.errors
#                             # "errors" : "user not found"
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#     except Exception as e:
#         return Response({
#             "success": False,
#             "login_status": "failed",
#             "error": "Operation failed",
#             "details": str(e),
#             # "trace": traceback.format_exc()
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 



# # # certificate added 

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def register_or_login_user(request):
#     """
#     Unified API for User Registration and Login
#     - If user doesn't exist: Register -> Send OTP -> Verify OTP -> Create user -> Auto-login (with vendor approval check)
#     - If user exists: Login flow (OTP or Password) with vendor approval and active status check
#     """
#     azure_service = AzureStorageService()
#     data = request.data

#     contact_number = data.get('contact_number')
#     otp = data.get('otp')
#     password = data.get('password')
#     login_type = data.get('login_type', 'otp')  # 'otp' or 'password'
    
#     # Registration fields (optional, only needed for new users)
#     name = data.get('name')
#     role_id = data.get('role_id')
#     aadhar_number = data.get('aadhar_number')
#     address_text = data.get('address_text')
#     user_lat = data.get('user_lat')
#     user_long = data.get('user_long')

#     if not contact_number:
#         return Response(
#             {
#                 "success": False,
#                 "login_status": "failed",
#                 "error": "contact_number is required"
#             }, 
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # Get logged-in user's role_id (for tracking who created)
#     logged_in_role_id = get_logged_in_role_id(request)

#     try:
#         # Check if user exists
#         existing_user = UserInfo.objects.filter(contact_number=contact_number).first()
        
#         # ========== CASE 1: USER EXISTS - LOGIN FLOW ==========
#         if existing_user:
#             # Check if this is registration attempt for existing user
#             if name or role_id or aadhar_number or request.FILES.get('aadhar_img') or request.FILES.get('certificate'):
#                 return Response(
#                     {
#                         "success": False,
#                         "login_status": "failed",
#                         "error": "User already registered. Please login instead."
#                     },
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             # ========== CHECK ACTIVE STATUS ==========
#             if existing_user.active_status == '0':
#                 return Response(
#                     {
#                         "success": False,
#                         "login_status": "inactive",
#                         "message": "Your account is inactive. Please contact admin.",
#                         "error": "Account is inactive",
#                         "user_id": existing_user.user_id,
#                         "name": existing_user.name,
#                         "role_id": existing_user.role_id
#                     },
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             # ========== CHECK VENDOR APPROVAL STATUS ==========
#             if str(existing_user.role_id) == '3':  # Vendor role
#                 if existing_user.is_approved == 'pending':
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "pending_approval",
#                             "message": "Your account is pending approval. Please wait or contact admin.",
#                             "error": "Vendor account pending approval",
#                             "approval_status": "pending",
#                             "user_id": existing_user.user_id,
#                             "name": existing_user.name,
#                             "role_id": existing_user.role_id
#                         },
#                         status=status.HTTP_403_FORBIDDEN
#                     )
#                 elif existing_user.is_approved == 'declined':
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "declined",
#                             "message": "Your account has been declined. Please contact admin.",
#                             "error": "Vendor account declined",
#                             "approval_status": "declined",
#                             "user_id": existing_user.user_id,
#                             "name": existing_user.name,
#                             "role_id": existing_user.role_id
#                         },
#                         status=status.HTTP_403_FORBIDDEN
#                     )
#                 # If approved, continue with login

#             # ========== PASSWORD-BASED LOGIN ==========
#             if login_type == 'password' or password:
#                 from .auth import verify_password
                
#                 if not password:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": "Password is required for password login"
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
                
#                 if not existing_user.password:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": "Password not set for this account. Please use OTP login."
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
                
#                 if not verify_password(password, existing_user.password):
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": "Invalid password"
#                         },
#                         status=status.HTTP_401_UNAUTHORIZED
#                     )
                
#                 # Password verified - login successful
#                 existing_user.active_status = '1'
#                 existing_user.save()
                
#                 tokens = generate_jwt_token(existing_user)
                
#                 return Response(
#                     {
#                         "success": True,
#                         "login_status": "success",
#                         "message": "Login successful",
#                         "is_new_user": False,
#                         "data": {
#                             "refresh_token": tokens["refresh_token"],
#                             "access_token": tokens["access_token"],
#                             "user_id": existing_user.user_id,
#                             "name": existing_user.name,
#                             "contact_number": existing_user.contact_number,
#                             "role_id": existing_user.role_id,
#                             "is_approved": existing_user.is_approved if str(existing_user.role_id) == '3' else None
#                         }
#                     },
#                     status=status.HTTP_200_OK
#                 )

#             # ========== OTP-BASED LOGIN ==========
#             # Send OTP if not provided
#             if not otp:
#                 try:
#                     otp_service.sendOtp(contact_number)
#                     return Response(
#                         {
#                             "success": True,
#                             "login_status": "otp_sent",
#                             "message": "OTP sent successfully",
#                             "is_new_user": False,
#                             "data": {"contact_number": contact_number}
#                         },
#                         status=status.HTTP_200_OK
#                     )
#                 except Exception as e:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": f"Failed to send OTP: {str(e)}"
#                         },
#                         status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                     )

#             # Verify OTP
#             otp_result = otp_service.verifyOtp(contact_number, otp)
#             if not otp_result['success']:
#                 return Response(
#                     {
#                         "success": False,
#                         "login_status": "failed",
#                         "error": otp_result['message']
#                     },
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # OTP verified - login successful
#             existing_user.active_status = '1'
#             existing_user.save()
            
#             tokens = generate_jwt_token(existing_user)
            
#             return Response(
#                 {
#                     "success": True,
#                     "login_status": "success",
#                     "message": "Login successful",
#                     "is_new_user": False,
#                     "data": {
#                         "refresh_token": tokens["refresh_token"],
#                         "access_token": tokens["access_token"],
#                         "user_id": existing_user.user_id,
#                         "name": existing_user.name,
#                         "contact_number": existing_user.contact_number,
#                         "role_id": existing_user.role_id,
#                         "is_approved": existing_user.is_approved if str(existing_user.role_id) == '3' else None
#                     }
#                 },
#                 status=status.HTTP_200_OK
#             )

#         # ========== CASE 2: NEW USER - REGISTRATION FLOW ==========
#         else:
#             # Step 1: Send OTP (no data saved yet)
#             if not otp:
#                 # Validate required fields for registration
#                 required_fields = ['name', 'role_id', 'contact_number']
#                 missing_fields = [field for field in required_fields if not data.get(field)]
#                 if missing_fields:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             # "error": f"Missing required fields: {', '.join(missing_fields)}"
#                             "error": "User Not found"  
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 # Upload images to Azure if provided
#                 aadhar_url = None
#                 stamp_url = None
#                 certificate_url = None
                
#                 if request.FILES.get('aadhar_img'):
#                     aadhar_file = request.FILES['aadhar_img']
#                     aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                
#                 if request.FILES.get('stamp_img'):
#                     stamp_file = request.FILES['stamp_img']
#                     stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)
                
#                 # NEW: Upload certificate for vendors only
#                 if str(role_id) == '3' and request.FILES.get('certificate'):
#                     cert_file = request.FILES['certificate']
#                     certificate_url = azure_service.upload_image('CERTIFICATE', cert_file, cert_file.name)

#                 # Send OTP
#                 try:
#                     otp_service.sendOtp(contact_number)
                    
#                     response_data = {
#                         "success": True,
#                         "login_status": "otp_sent",
#                         "message": "OTP sent successfully. Please verify to complete registration.",
#                         "is_new_user": True,
#                         "next_step": "verify_otp",
#                         "data": {
#                             "contact_number": contact_number,
#                             "name": name,
#                             "role_id": role_id
#                         }
#                     }
                    
#                     # Add optional fields to response
#                     if aadhar_url:
#                         response_data["data"]["aadhar_url"] = aadhar_url
#                     if stamp_url:
#                         response_data["data"]["stamp_url"] = stamp_url
#                     if certificate_url:
#                         response_data["data"]["certificate_url"] = certificate_url
#                     if address_text:
#                         response_data["data"]["address_text"] = address_text
                    
#                     return Response(response_data, status=status.HTTP_200_OK)
                    
#                 except Exception as e:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": f"Failed to send OTP: {str(e)}"
#                         },
#                         status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                     )

#             # Step 2: Verify OTP and create user
#             else:
#                 # Verify OTP
#                 otp_result = otp_service.verifyOtp(contact_number, otp)
#                 if not otp_result['success']:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "error": otp_result['message']
                            
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 # Get role_id from request data
#                 role_id = data.get('role_id')
#                 role_name = get_role_name(role_id)

#                 # ========== DUPLICATE CHECK FOR AADHAR ==========
#                 if aadhar_number:
#                     if UserInfo.objects.filter(
#                         aadhar_number=aadhar_number,
#                         active_status='1'
#                     ).exists():
#                         return Response(
#                             {
#                                 "success": False,
#                                 "login_status": "failed",
#                                 "error": "Aadhar number already registered with another account"
#                             },
#                             status=status.HTTP_400_BAD_REQUEST
#                         )

#                 # Handle image uploads
#                 aadhar_url = data.get('aadhar_img')
#                 stamp_url = data.get('stamp_img')
#                 certificate_url = data.get('certificate')
                
#                 if request.FILES.get('aadhar_img'):
#                     aadhar_file = request.FILES['aadhar_img']
#                     aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                
#                 if request.FILES.get('stamp_img'):
#                     stamp_file = request.FILES['stamp_img']
#                     stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)
                
#                 # NEW: Upload certificate for vendors only
#                 if str(role_id) == '3' and request.FILES.get('certificate'):
#                     cert_file = request.FILES['certificate']
#                     certificate_url = azure_service.upload_image('CERTIFICATE', cert_file, cert_file.name)

#                 # Hash password if provided
#                 hashed_password = None
#                 if data.get('password'):
#                     from .auth import hash_password
#                     hashed_password = hash_password(data.get('password'))

#                 # ========== HANDLE LOCATION DATA ==========
#                 final_lat = user_lat
#                 final_long = user_long
                
#                 if address_text and not (user_lat and user_long):
#                     try:
#                         lat, lon = get_lat_long_from_address(address_text)
#                         if lat and lon:
#                             final_lat = str(lat)
#                             final_long = str(lon)
#                     except Exception as e:
#                         return Response(
#                             {
#                                 "success": False,
#                                 "login_status": "failed",
#                                 "error": f"Error converting address to coordinates: {str(e)}"
#                             },
#                             status=status.HTTP_400_BAD_REQUEST
#                         )

#                 # Prepare user data
#                 user_data = {
#                     'name': name,
#                     'contact_number': contact_number,
#                     'role_id': role_id,
#                     'aadhar_number': aadhar_number,
#                     'aadhar_img': aadhar_url,
#                     'stamp_img': stamp_url,
#                     'certificate': certificate_url,  # NEW: Add certificate field
#                     'created_by': logged_in_role_id,
#                     'active_status': '1',  # New users are active by default
#                     'user_lat': final_lat,
#                     'user_long': final_long,
#                     'password': hashed_password
#                 }

#                 # Set is_approved for vendors
#                 vendor_message = None
#                 login_status = "success"
                
#                 if str(role_id) == '3':  # Vendor role
#                     user_data['is_approved'] = 'pending'
#                     vendor_message = "Your registration is pending admin approval. You will be able to login once approved."
#                     login_status = "pending_approval"
#                 else:
#                     login_status = "success"

#                 # Remove None values
#                 user_data = {k: v for k, v in user_data.items() if v is not None}

#                 # Create user
#                 serializer = UserInfoSerializer(data=user_data)
                
#                 if serializer.is_valid():
#                     user = serializer.save()
                    
#                     # Generate JWT token (user is logged in automatically)
#                     tokens = generate_jwt_token(user)
                    
#                     response_data = {
#                         "success": True,
#                         "login_status": login_status,
#                         "message": "Registration successful!" if login_status == "success" else vendor_message,
#                         "is_new_user": True,
#                         "data": {
#                             "refresh_token": tokens["refresh_token"],
#                             "access_token": tokens["access_token"],
#                             "user_id": user.user_id,
#                             "name": user.name,
#                             "contact_number": user.contact_number,
#                             "role_id": user.role_id,
#                             "active_status": user.active_status,
#                             "aadhar_url": aadhar_url,
#                             "stamp_url": stamp_url
#                         }
#                     }
                    
#                     # Add certificate URL to response for vendors
#                     if str(role_id) == '3' and certificate_url:
#                         response_data["data"]["certificate_url"] = certificate_url
                    
#                     # Add vendor approval info if applicable
#                     if str(role_id) == '3':
#                         response_data["data"]["is_approved"] = "pending"
                    
#                     return Response(response_data, status=status.HTTP_201_CREATED)
#                 else:
#                     return Response(
#                         {
#                             "success": False,
#                             "login_status": "failed",
#                             "errors": serializer.errors
#                             # "errors" : "user not found"
#                         },
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#     except Exception as e:
#         return Response({
#             "success": False,
#             "login_status": "failed",
#             "error": "Operation failed",
#             "details": str(e),
#             # "trace": traceback.format_exc()
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)







# code for declined user with reason and able to re register

@api_view(['POST'])
@permission_classes([AllowAny])
def register_or_login_user(request):
    """
    Unified API for User Registration and Login
    - If user doesn't exist: Register -> Send OTP -> Verify OTP -> Create user -> Auto-login (with vendor approval check)
    - If user exists: Login flow (OTP or Password) with vendor approval and active status check
    - For declined vendors: Allows re-registration with new documents (keeps decline_reason until admin approval)
    """
    azure_service = AzureStorageService()
    data = request.data

    contact_number = data.get('contact_number')
    otp = data.get('otp')
    password = data.get('password')
    login_type = data.get('login_type', 'otp')  # 'otp' or 'password'
    
    # Registration fields (optional, only needed for new users)
    name = data.get('name')
    role_id = data.get('role_id')
    aadhar_number = data.get('aadhar_number')
    address_text = data.get('address_text')
    user_lat = data.get('user_lat')
    user_long = data.get('user_long')

    if not contact_number:
        return Response(
            {
                "success": False,
                "login_status": "failed",
                "error": "contact_number is required"
            }, 
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get logged-in user's role_id (for tracking who created)
    logged_in_role_id = get_logged_in_role_id(request)

    try:
        # Check if user exists
        existing_user = UserInfo.objects.filter(contact_number=contact_number).first()
        
        # ========== CASE 1: USER EXISTS - LOGIN FLOW ==========
        if existing_user:
            # Check if this is registration attempt for existing user
            if name or role_id or aadhar_number or request.FILES.get('aadhar_img') or request.FILES.get('stamp_img') or request.FILES.get('certificate'):
                # Special case: Vendor re-registration after being declined
                if str(existing_user.role_id) == '3' and existing_user.is_approved == 'declined':
                    # Allow re-registration - update existing record instead of creating new
                    # Step 1: Send OTP first
                    if not otp:
                        # Validate required fields for re-registration
                        required_fields = ['name', 'role_id', 'contact_number']
                        missing_fields = [field for field in required_fields if not data.get(field)]
                        if missing_fields:
                            return Response(
                                {
                                    "success": False,
                                    "login_status": "failed",
                                    "error": "User Not found"  
                                },
                                status=status.HTTP_400_BAD_REQUEST
                            )

                        # Upload new images to Azure if provided
                        aadhar_url = existing_user.aadhar_img
                        stamp_url = existing_user.stamp_img
                        certificate_url = existing_user.certificate if hasattr(existing_user, 'certificate') else None
                        
                        if request.FILES.get('aadhar_img'):
                            aadhar_file = request.FILES['aadhar_img']
                            # Delete old image if exists
                            if existing_user.aadhar_img:
                                try:
                                    old_blob_name = existing_user.aadhar_img.split('/')[-1].split('?')[0]
                                    azure_service.delete_image('AADHAR', old_blob_name)
                                except:
                                    pass
                            aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                        
                        if request.FILES.get('stamp_img'):
                            stamp_file = request.FILES['stamp_img']
                            if existing_user.stamp_img:
                                try:
                                    old_blob_name = existing_user.stamp_img.split('/')[-1].split('?')[0]
                                    azure_service.delete_image('STAMP', old_blob_name)
                                except:
                                    pass
                            stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)
                        
                        if str(role_id) == '3' and request.FILES.get('certificate'):
                            cert_file = request.FILES['certificate']
                            if hasattr(existing_user, 'certificate') and existing_user.certificate:
                                try:
                                    old_blob_name = existing_user.certificate.split('/')[-1].split('?')[0]
                                    azure_service.delete_image('CERTIFICATE', old_blob_name)
                                except:
                                    pass
                            certificate_url = azure_service.upload_image('CERTIFICATE', cert_file, cert_file.name)

                        # Send OTP
                        try:
                            otp_service.sendOtp(contact_number)
                            
                            response_data = {
                                "success": True,
                                "login_status": "otp_sent",
                                "message": "OTP sent successfully. Please verify to complete re-registration.",
                                "is_new_user": False,
                                "is_re_registration": True,
                                "next_step": "verify_otp",
                                "data": {
                                    "contact_number": contact_number,
                                    "name": name,
                                    "role_id": role_id,
                                    "aadhar_url": aadhar_url,
                                    "stamp_url": stamp_url,
                                    "certificate_url": certificate_url,
                                    "decline_reason": existing_user.decline_reason if hasattr(existing_user, 'decline_reason') else None
                                }
                            }
                            
                            if address_text:
                                response_data["data"]["address_text"] = address_text
                            
                            return Response(response_data, status=status.HTTP_200_OK)
                            
                        except Exception as e:
                            return Response(
                                {
                                    "success": False,
                                    "login_status": "failed",
                                    "error": f"Failed to send OTP: {str(e)}"
                                },
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                            )
                    else:
                        # Verify OTP and update existing vendor record
                        otp_result = otp_service.verifyOtp(contact_number, otp)
                        if not otp_result['success']:
                            return Response(
                                {
                                    "success": False,
                                    "login_status": "failed",
                                    "error": otp_result['message']
                                },
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        
                        # Update existing vendor record (DO NOT clear decline_reason here)
                        update_data = {
                            'name': data.get('name', existing_user.name),
                            'role_id': data.get('role_id', existing_user.role_id),
                            'aadhar_number': data.get('aadhar_number', existing_user.aadhar_number),
                            'active_status': '1',
                            'is_approved': 'pending',  # Reset to pending for re-approval
                            # decline_reason is NOT cleared here - it persists until admin approves
                        }
                        
                        # Handle image URLs from request data
                        aadhar_url = data.get('aadhar_url')
                        stamp_url = data.get('stamp_url')
                        certificate_url = data.get('certificate_url')
                        
                        if aadhar_url:
                            update_data['aadhar_img'] = aadhar_url
                        if stamp_url:
                            update_data['stamp_img'] = stamp_url
                        if certificate_url:
                            update_data['certificate'] = certificate_url
                        
                        # Handle location data
                        final_lat = data.get('user_lat')
                        final_long = data.get('user_long')
                        address_text = data.get('address_text')
                        
                        if address_text and not (final_lat and final_long):
                            try:
                                lat, lon = get_lat_long_from_address(address_text)
                                if lat and lon:
                                    final_lat = str(lat)
                                    final_long = str(lon)
                            except Exception as e:
                                return Response(
                                    {
                                        "success": False,
                                        "login_status": "failed",
                                        "error": f"Error converting address to coordinates: {str(e)}"
                                    },
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        
                        if final_lat:
                            update_data['user_lat'] = final_lat
                        if final_long:
                            update_data['user_long'] = final_long
                        
                        # Hash password if provided
                        if data.get('password'):
                            from .auth import hash_password
                            update_data['password'] = hash_password(data.get('password'))
                        
                        # Update the user
                        for key, value in update_data.items():
                            setattr(existing_user, key, value)
                        existing_user.save()
                        
                        tokens = generate_jwt_token(existing_user)
                        
                        response_data = {
                            "success": True,
                            "login_status": "pending_approval",
                            "message": "Your re-registration is pending admin approval. You will be able to login once approved.",
                            "is_new_user": False,
                            "is_re_registration": True,
                            "data": {
                                "refresh_token": tokens["refresh_token"],
                                "access_token": tokens["access_token"],
                                "user_id": existing_user.user_id,
                                "name": existing_user.name,
                                "contact_number": existing_user.contact_number,
                                "role_id": existing_user.role_id,
                                "active_status": existing_user.active_status,
                                "aadhar_url": existing_user.aadhar_img,
                                "stamp_url": existing_user.stamp_img,
                                "is_approved": "pending",
                                "decline_reason": existing_user.decline_reason if hasattr(existing_user, 'decline_reason') else None
                            }
                        }
                        
                        if hasattr(existing_user, 'certificate') and existing_user.certificate:
                            response_data["data"]["certificate_url"] = existing_user.certificate
                        
                        return Response(response_data, status=status.HTTP_200_OK)
                
                # Normal user - already registered (non-vendor or not declined)
                return Response(
                    {
                        "success": False,
                        "login_status": "failed",
                        "error": "User already registered. Please login instead."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ========== CHECK ACTIVE STATUS ==========
            if existing_user.active_status == '0':
                return Response(
                    {
                        "success": False,
                        "login_status": "inactive",
                        "message": "Your account is inactive. Please contact admin.",
                        "error": "Account is inactive",
                        "user_id": existing_user.user_id,
                        "name": existing_user.name,
                        "role_id": existing_user.role_id
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # ========== CHECK VENDOR APPROVAL STATUS ==========
            if str(existing_user.role_id) == '3':  # Vendor role
                if existing_user.is_approved == 'pending':
                    return Response(
                        {
                            "success": False,
                            "login_status": "pending_approval",
                            "message": "Your account is pending approval. Please wait or contact admin.",
                            "error": "Vendor account pending approval",
                            "approval_status": "pending",
                            "user_id": existing_user.user_id,
                            "name": existing_user.name,
                            "role_id": existing_user.role_id,
                            "decline_reason": existing_user.decline_reason if hasattr(existing_user, 'decline_reason') else None
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
                elif existing_user.is_approved == 'declined':
                    return Response(
                        {
                            "success": False,
                            "login_status": "declined",
                            "message": "Your account has been declined. Please contact admin or re-register with correct documents.",
                            "error": "Vendor account declined",
                            "approval_status": "declined",
                            "user_id": existing_user.user_id,
                            "name": existing_user.name,
                            "role_id": existing_user.role_id,
                            "decline_reason": existing_user.decline_reason if hasattr(existing_user, 'decline_reason') else None
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )
                # If approved, continue with login

            # ========== PASSWORD-BASED LOGIN ==========
            if login_type == 'password' or password:
                from .auth import verify_password
                
                if not password:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": "Password is required for password login"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if not existing_user.password:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": "Password not set for this account. Please use OTP login."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if not verify_password(password, existing_user.password):
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": "Invalid password"
                        },
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                
                # Password verified - login successful
                existing_user.active_status = '1'
                existing_user.save()
                
                tokens = generate_jwt_token(existing_user)
                
                return Response(
                    {
                        "success": True,
                        "login_status": "success",
                        "message": "Login successful",
                        "is_new_user": False,
                        "data": {
                            "refresh_token": tokens["refresh_token"],
                            "access_token": tokens["access_token"],
                            "user_id": existing_user.user_id,
                            "name": existing_user.name,
                            "contact_number": existing_user.contact_number,
                            "role_id": existing_user.role_id,
                            "is_approved": existing_user.is_approved if str(existing_user.role_id) == '3' else None
                        }
                    },
                    status=status.HTTP_200_OK
                )

            # ========== OTP-BASED LOGIN ==========
            # Send OTP if not provided
            if not otp:
                try:
                    otp_service.sendOtp(contact_number)
                    return Response(
                        {
                            "success": True,
                            "login_status": "otp_sent",
                            "message": "OTP sent successfully",
                            "is_new_user": False,
                            "data": {"contact_number": contact_number}
                        },
                        status=status.HTTP_200_OK
                    )
                except Exception as e:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": f"Failed to send OTP: {str(e)}"
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            # Verify OTP
            otp_result = otp_service.verifyOtp(contact_number, otp)
            if not otp_result['success']:
                return Response(
                    {
                        "success": False,
                        "login_status": "failed",
                        "error": otp_result['message']
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # OTP verified - login successful
            existing_user.active_status = '1'
            existing_user.save()
            
            tokens = generate_jwt_token(existing_user)
            
            return Response(
                {
                    "success": True,
                    "login_status": "success",
                    "message": "Login successful",
                    "is_new_user": False,
                    "data": {
                        "refresh_token": tokens["refresh_token"],
                        "access_token": tokens["access_token"],
                        "user_id": existing_user.user_id,
                        "name": existing_user.name,
                        "contact_number": existing_user.contact_number,
                        "role_id": existing_user.role_id,
                        "is_approved": existing_user.is_approved if str(existing_user.role_id) == '3' else None
                    }
                },
                status=status.HTTP_200_OK
            )

        # ========== CASE 2: NEW USER - REGISTRATION FLOW ==========
        else:
            # Step 1: Send OTP (no data saved yet)
            if not otp:
                # Validate required fields for registration
                required_fields = ['name', 'role_id', 'contact_number']
                missing_fields = [field for field in required_fields if not data.get(field)]
                if missing_fields:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": "User Not found"  
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Upload images to Azure if provided
                aadhar_url = None
                stamp_url = None
                certificate_url = None
                
                if request.FILES.get('aadhar_img'):
                    aadhar_file = request.FILES['aadhar_img']
                    aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                
                if request.FILES.get('stamp_img'):
                    stamp_file = request.FILES['stamp_img']
                    stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)
                
                if str(role_id) == '3' and request.FILES.get('certificate'):
                    cert_file = request.FILES['certificate']
                    certificate_url = azure_service.upload_image('CERTIFICATE', cert_file, cert_file.name)

                # Send OTP
                try:
                    otp_service.sendOtp(contact_number)
                    
                    response_data = {
                        "success": True,
                        "login_status": "otp_sent",
                        "message": "OTP sent successfully. Please verify to complete registration.",
                        "is_new_user": True,
                        "next_step": "verify_otp",
                        "data": {
                            "contact_number": contact_number,
                            "name": name,
                            "role_id": role_id
                        }
                    }
                    
                    # Add optional fields to response
                    if aadhar_url:
                        response_data["data"]["aadhar_url"] = aadhar_url
                    if stamp_url:
                        response_data["data"]["stamp_url"] = stamp_url
                    if certificate_url:
                        response_data["data"]["certificate_url"] = certificate_url
                    if address_text:
                        response_data["data"]["address_text"] = address_text
                    
                    return Response(response_data, status=status.HTTP_200_OK)
                    
                except Exception as e:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": f"Failed to send OTP: {str(e)}"
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            # Step 2: Verify OTP and create user
            else:
                # Verify OTP
                otp_result = otp_service.verifyOtp(contact_number, otp)
                if not otp_result['success']:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "error": otp_result['message']
                            
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Get role_id from request data
                role_id = data.get('role_id')
                role_name = get_role_name(role_id)

                # ========== DUPLICATE CHECK FOR AADHAR ==========
                if aadhar_number:
                    if UserInfo.objects.filter(
                        aadhar_number=aadhar_number,
                        active_status='1'
                    ).exists():
                        return Response(
                            {
                                "success": False,
                                "login_status": "failed",
                                "error": "Aadhar number already registered with another account"
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # Handle image uploads
                aadhar_url = data.get('aadhar_img')
                stamp_url = data.get('stamp_img')
                certificate_url = data.get('certificate')
                
                if request.FILES.get('aadhar_img'):
                    aadhar_file = request.FILES['aadhar_img']
                    aadhar_url = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
                
                if request.FILES.get('stamp_img'):
                    stamp_file = request.FILES['stamp_img']
                    stamp_url = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)
                
                if str(role_id) == '3' and request.FILES.get('certificate'):
                    cert_file = request.FILES['certificate']
                    certificate_url = azure_service.upload_image('CERTIFICATE', cert_file, cert_file.name)

                # Hash password if provided
                hashed_password = None
                if data.get('password'):
                    from .auth import hash_password
                    hashed_password = hash_password(data.get('password'))

                # ========== HANDLE LOCATION DATA ==========
                final_lat = user_lat
                final_long = user_long
                
                if address_text and not (user_lat and user_long):
                    try:
                        lat, lon = get_lat_long_from_address(address_text)
                        if lat and lon:
                            final_lat = str(lat)
                            final_long = str(lon)
                    except Exception as e:
                        return Response(
                            {
                                "success": False,
                                "login_status": "failed",
                                "error": f"Error converting address to coordinates: {str(e)}"
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )

                # Prepare user data
                user_data = {
                    'name': name,
                    'contact_number': contact_number,
                    'role_id': role_id,
                    'aadhar_number': aadhar_number,
                    'aadhar_img': aadhar_url,
                    'stamp_img': stamp_url,
                    'created_by': logged_in_role_id,
                    'active_status': '1',  # New users are active by default
                    'user_lat': final_lat,
                    'user_long': final_long,
                    'password': hashed_password
                }

                # Add certificate for vendors
                if str(role_id) == '3' and certificate_url:
                    user_data['certificate'] = certificate_url

                # Set is_approved for vendors
                vendor_message = None
                login_status = "success"
                
                if str(role_id) == '3':  # Vendor role
                    user_data['is_approved'] = 'pending'
                    vendor_message = "Your registration is pending admin approval. You will be able to login once approved."
                    login_status = "pending_approval"
                else:
                    login_status = "success"

                # Remove None values
                user_data = {k: v for k, v in user_data.items() if v is not None}

                # Create user
                serializer = UserInfoSerializer(data=user_data)
                
                if serializer.is_valid():
                    user = serializer.save()
                    
                    # Generate JWT token (user is logged in automatically)
                    tokens = generate_jwt_token(user)
                    
                    response_data = {
                        "success": True,
                        "login_status": login_status,
                        "message": "Registration successful!" if login_status == "success" else vendor_message,
                        "is_new_user": True,
                        "data": {
                            "refresh_token": tokens["refresh_token"],
                            "access_token": tokens["access_token"],
                            "user_id": user.user_id,
                            "name": user.name,
                            "contact_number": user.contact_number,
                            "role_id": user.role_id,
                            "active_status": user.active_status,
                            "aadhar_url": aadhar_url,
                            "stamp_url": stamp_url
                        }
                    }
                    
                    # Add certificate URL for vendors
                    if str(role_id) == '3' and certificate_url:
                        response_data["data"]["certificate_url"] = certificate_url
                    
                    # Add vendor approval info if applicable
                    if str(role_id) == '3':
                        response_data["data"]["is_approved"] = "pending"
                    
                    return Response(response_data, status=status.HTTP_201_CREATED)
                else:
                    return Response(
                        {
                            "success": False,
                            "login_status": "failed",
                            "errors": serializer.errors
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

    except Exception as e:
        return Response({
            "success": False,
            "login_status": "failed",
            "error": "Operation failed",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@api_view(['GET', 'PUT', 'DELETE'])
@active_user_required
def manage_user(request):
    """
    Unified API for User Management (Retrieve/Update/Delete)
    - GET: Retrieve user details (only from tbl_user)
    - PUT: Update user details (including active_status and is_approved)
    - DELETE: Permanently delete user account from database

    Authentication Required:
    - Regular users: Can only manage their own account (user_id from token)
    - Admin users (role_id=1 or 2): Can manage any account by passing target_user_id
    """
    azure_service = AzureStorageService()

    # ========== TOKEN AUTHENTICATION ==========
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)

    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Get logged-in user info from token
    logged_in_user_id = token_user.get('user_id')
    logged_in_role_id = token_user.get('role_id')

    try:
        # Get logged-in user from database
        logged_in_user = UserInfo.objects.get(user_id=logged_in_user_id)
    except UserInfo.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Authenticated user not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if user is admin (role_id 1 or 2)
    is_admin = str(logged_in_role_id) in ['1', '2']

    # Determine target user ID
    # If admin and target_user_id provided, use that; otherwise use logged_in_user_id
    target_user_id = request.data.get('target_user_id') or request.query_params.get('target_user_id')

    if is_admin and target_user_id:
        # Admin managing another user's account
        try:
            target_user = UserInfo.objects.get(user_id=target_user_id)
        except UserInfo.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": f"Target user with user_id {target_user_id} not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        # Regular user managing their own account
        target_user = logged_in_user
        target_user_id = logged_in_user_id

    # ========== GET METHOD - RETRIEVE USER ==========      # # woring code - only for english langauge
    # if request.method == 'GET':
    #     serializer = UserInfoSerializer(target_user)
    #     return Response(
    #         {
    #             "success": True,
    #             "message": "User details fetched successfully",
    #             "data": serializer.data
    #         },
    #         status=status.HTTP_200_OK
    #     )
    if request.method == 'GET':                             # # woring code - added for all langauge
        serializer = UserInfoSerializer(target_user)
        data = serializer.data
        lang = request.query_params.get('lang', 'en')
        if lang != 'en' and 'name' in data:
            data['name'] = transliterate_name(data['name'], lang)
        return Response(
            {
                "success": True,
                "message": "User details fetched successfully",
                "data": data
            },
            status=status.HTTP_200_OK
        )
    # # ========== PUT METHOD - UPDATE USER ==========
    # elif request.method == 'PUT':
    #     # ... (existing PUT code, unchanged) ...
    #     # (I'll include the full PUT block from your original code below for completeness)
    #     # Start with an empty update_data dictionary
    #     update_data = {}

    #     # Only add fields that are actually provided in the request
    #     # Basic fields
    #     if 'name' in request.data:
    #         update_data['name'] = request.data.get('name')

    #     if 'contact_number' in request.data:
    #         contact_number = request.data.get('contact_number')
    #         # Check if new contact number is already taken by another user
    #         if contact_number != target_user.contact_number:
    #             existing_user = UserInfo.objects.filter(contact_number=contact_number).first()
    #             if existing_user and existing_user.user_id != target_user.user_id:
    #                 return Response(
    #                     {
    #                         "success": False,
    #                         "error": "Contact number already registered with another account"
    #                     },
    #                     status=status.HTTP_400_BAD_REQUEST
    #                 )
    #         update_data['contact_number'] = contact_number

    #     # Only allow role_id change if admin
    #     if is_admin and 'role_id' in request.data:
    #         update_data['role_id'] = request.data.get('role_id')

    #     # Aadhar fields - ONLY update aadhar_number if provided
    #     if 'aadhar_number' in request.data:
    #         update_data['aadhar_number'] = request.data.get('aadhar_number')
    #         # Note: We're NOT including aadhar_img here unless specifically uploaded

    #     # ========== ACTIVE STATUS UPDATE ==========
    #     # Allow admin to update active_status
    #     if is_admin and 'active_status' in request.data:
    #         active_status = request.data.get('active_status')
    #         # Validate active_status value
    #         if active_status in ['0', '1']:
    #             update_data['active_status'] = active_status
    #         else:
    #             return Response(
    #                 {
    #                     "success": False,
    #                     "error": "active_status must be '0' (inactive) or '1' (active)"
    #                 },
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #     # ========== IS_APPROVED UPDATE ==========
    #     # Only admin can update is_approved for vendors
    #     if is_admin and 'is_approved' in request.data:
    #         is_approved = request.data.get('is_approved')
    #         # Validate is_approved value
    #         if is_approved in ['pending', 'approved', 'declined']:
    #             update_data['is_approved'] = is_approved
    #         else:
    #             return Response(
    #                 {
    #                     "success": False,
    #                     "error": "is_approved must be 'pending', 'approved', or 'declined'"
    #                 },
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #     # Handle image uploads - ONLY update if new files are provided
    #     # This preserves existing documents if no new files are uploaded
    #     try:
    #         if request.FILES.get('aadhar_img'):
    #             aadhar_file = request.FILES['aadhar_img']
    #             update_data['aadhar_img'] = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)
    #         # If aadhar_img is NOT in FILES, we don't include it in update_data
    #         # This preserves the existing aadhar_img value

    #         if request.FILES.get('stamp_img'):
    #             stamp_file = request.FILES['stamp_img']
    #             update_data['stamp_img'] = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)
    #         # If stamp_img is NOT in FILES, we don't include it in update_data
    #         # This preserves the existing stamp_img value

    #     except Exception as e:
    #         return Response(
    #             {
    #                 "success": False,
    #                 "error": f"Failed to upload images: {str(e)}"
    #             },
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )

    #     # ========== HANDLE LOCATION DATA ==========
    #     address_text = request.data.get('address_text')
    #     user_lat = request.data.get('user_lat')
    #     user_long = request.data.get('user_long')

    #     # If address_text is provided and lat/long are not provided, convert address to coordinates
    #     if address_text and not (user_lat and user_long):
    #         try:
    #             lat, lon = get_lat_long_from_address(address_text)
    #             if lat and lon:
    #                 update_data['user_lat'] = str(lat)
    #                 update_data['user_long'] = str(lon)
    #             else:
    #                 return Response(
    #                     {
    #                         "success": False,
    #                         "error": "Could not convert address to coordinates. Please provide valid address or send lat/long directly."
    #                     },
    #                     status=status.HTTP_400_BAD_REQUEST
    #                 )
    #         except Exception as e:
    #             return Response(
    #                 {
    #                     "success": False,
    #                     "error": f"Error converting address to coordinates: {str(e)}"
    #                 },
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
    #     else:
    #         # If lat/long are provided directly, add them
    #         if user_lat:
    #             update_data['user_lat'] = user_lat
    #         if user_long:
    #             update_data['user_long'] = user_long

    #     # Always set updated_by (this is a system field, not user-provided)
    #     update_data['updated_by'] = str(logged_in_user_id)

    #     # Handle password update if provided
    #     if 'password' in request.data and request.data.get('password'):
    #         from .auth import hash_password
    #         update_data['password'] = hash_password(request.data.get('password'))

    #     # Check if there's anything to update
    #     if not update_data:
    #         return Response(
    #             {
    #                 "success": False,
    #                 "error": "No valid fields provided for update"
    #             },
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     try:
    #         # ========== FIX FOR PRESERVING EXISTING DOCUMENTS ==========
    #         # Get current user data to preserve existing values
    #         # This ensures we don't accidentally nullify fields not in update_data
    #         current_user_data = UserInfoSerializer(target_user).data

    #         # Only update fields that are in update_data
    #         # This keeps all other fields with their existing values
    #         for field in update_data:
    #             current_user_data[field] = update_data[field]

    #         # Update user with merged data (using partial=False since we have complete data)
    #         serializer = UserInfoSerializer(target_user, data=current_user_data, partial=False)

    #         if serializer.is_valid():
    #             serializer.save()

    #             response_data = {
    #                 "success": True,
    #                 "message": "User updated successfully",
    #                 "updated_by": {
    #                     "user_id": logged_in_user_id,
    #                     "role_id": logged_in_role_id,
    #                     "is_admin": is_admin
    #                 },
    #                 "data": serializer.data,
    #                 "updated_fields": list(update_data.keys())  # Show which fields were updated
    #             }

    #             # Add image URLs to response if they were updated
    #             if update_data.get('aadhar_img'):
    #                 response_data["aadhar_url"] = update_data.get('aadhar_img')
    #             if update_data.get('stamp_img'):
    #                 response_data["stamp_url"] = update_data.get('stamp_img')

    #             return Response(response_data, status=status.HTTP_200_OK)
    #         else:
    #             return Response(
    #                 {
    #                     "success": False,
    #                     "errors": serializer.errors
    #                 },
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )

    #     except Exception as e:
    #         return Response({
    #             "success": False,
    #             "error": "Update failed",
    #             "details": str(e),
    #             # "trace": traceback.format_exc()
    #         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ========== PUT METHOD - UPDATE USER ==========
    elif request.method == 'PUT':
        # Start with an empty update_data dictionary
        update_data = {}

        # Only add fields that are actually provided in the request
        # Basic fields
        if 'name' in request.data:
            update_data['name'] = request.data.get('name')

        if 'contact_number' in request.data:
            contact_number = request.data.get('contact_number')
            # Check if new contact number is already taken by another user
            if contact_number != target_user.contact_number:
                existing_user = UserInfo.objects.filter(contact_number=contact_number).first()
                if existing_user and existing_user.user_id != target_user.user_id:
                    return Response(
                        {
                            "success": False,
                            "error": "Contact number already registered with another account"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            update_data['contact_number'] = contact_number

        # Only allow role_id change if admin
        if is_admin and 'role_id' in request.data:
            update_data['role_id'] = request.data.get('role_id')

        # Aadhar fields - ONLY update aadhar_number if provided
        if 'aadhar_number' in request.data:
            update_data['aadhar_number'] = request.data.get('aadhar_number')
            # Note: We're NOT including aadhar_img here unless specifically uploaded

        # ========== ACTIVE STATUS UPDATE ==========
        # Allow admin to update active_status
        if is_admin and 'active_status' in request.data:
            active_status = request.data.get('active_status')
            # Validate active_status value
            if active_status in ['0', '1']:
                update_data['active_status'] = active_status
            else:
                return Response(
                    {
                        "success": False,
                        "error": "active_status must be '0' (inactive) or '1' (active)"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ========== IS_APPROVED UPDATE ==========
        # Only admin can update is_approved for vendors
        if is_admin and 'is_approved' in request.data:
            is_approved = request.data.get('is_approved')
            # Validate is_approved value
            if is_approved in ['pending', 'approved', 'declined']:
                update_data['is_approved'] = is_approved
                
                # ========== SEND DECLINE NOTIFICATION ==========
                # If declining, send SMS notification with decline_reason
                if is_approved == 'declined' and str(target_user.role_id) == '3':
                    decline_reason = request.data.get('decline_reason')
                    if decline_reason:
                        update_data['decline_reason'] = decline_reason
                        # Send SMS notification
                        try:
                            from .services.otp_service import otp_service
                            otp_service.sendDeclineNotification(target_user.contact_number, decline_reason)
                        except Exception as e:
                            logger.error(f"Failed to send decline notification: {str(e)}")
                    else:
                        return Response(
                            {
                                "success": False,
                                "error": "decline_reason is required when declining a vendor"
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
            else:
                return Response(
                    {
                        "success": False,
                        "error": "is_approved must be 'pending', 'approved', or 'declined'"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # ========== UPDATE DECLINE REASON (if provided separately) ==========
        if is_admin and 'decline_reason' in request.data and 'is_approved' not in request.data:
            update_data['decline_reason'] = request.data.get('decline_reason')

        # Handle image uploads - ONLY update if new files are provided
        try:
            if request.FILES.get('aadhar_img'):
                aadhar_file = request.FILES['aadhar_img']
                # Delete old image if exists
                if target_user.aadhar_img:
                    try:
                        old_blob_name = target_user.aadhar_img.split('/')[-1].split('?')[0]
                        azure_service.delete_image('AADHAR', old_blob_name)
                    except:
                        pass
                update_data['aadhar_img'] = azure_service.upload_image('AADHAR', aadhar_file, aadhar_file.name)

            if request.FILES.get('stamp_img'):
                stamp_file = request.FILES['stamp_img']
                if target_user.stamp_img:
                    try:
                        old_blob_name = target_user.stamp_img.split('/')[-1].split('?')[0]
                        azure_service.delete_image('STAMP', old_blob_name)
                    except:
                        pass
                update_data['stamp_img'] = azure_service.upload_image('STAMP', stamp_file, stamp_file.name)

            # Handle certificate upload for vendors
            if request.FILES.get('certificate') and str(target_user.role_id) == '3':
                cert_file = request.FILES['certificate']
                if hasattr(target_user, 'certificate') and target_user.certificate:
                    try:
                        old_blob_name = target_user.certificate.split('/')[-1].split('?')[0]
                        azure_service.delete_image('CERTIFICATE', old_blob_name)
                    except:
                        pass
                update_data['certificate'] = azure_service.upload_image('CERTIFICATE', cert_file, cert_file.name)

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "error": f"Failed to upload images: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ========== HANDLE LOCATION DATA ==========
        address_text = request.data.get('address_text')
        user_lat = request.data.get('user_lat')
        user_long = request.data.get('user_long')

        # If address_text is provided and lat/long are not provided, convert address to coordinates
        if address_text and not (user_lat and user_long):
            try:
                lat, lon = get_lat_long_from_address(address_text)
                if lat and lon:
                    update_data['user_lat'] = str(lat)
                    update_data['user_long'] = str(lon)
                else:
                    return Response(
                        {
                            "success": False,
                            "error": "Could not convert address to coordinates. Please provide valid address or send lat/long directly."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Exception as e:
                return Response(
                    {
                        "success": False,
                        "error": f"Error converting address to coordinates: {str(e)}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # If lat/long are provided directly, add them
            if user_lat:
                update_data['user_lat'] = user_lat
            if user_long:
                update_data['user_long'] = user_long

        # Always set updated_by (this is a system field, not user-provided)
        update_data['updated_by'] = str(logged_in_user_id)

        # Handle password update if provided
        if 'password' in request.data and request.data.get('password'):
            from .auth import hash_password
            update_data['password'] = hash_password(request.data.get('password'))

        # Check if there's anything to update
        if not update_data:
            return Response(
                {
                    "success": False,
                    "error": "No valid fields provided for update"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # ========== FIX FOR PRESERVING EXISTING DOCUMENTS ==========
            # Get current user data to preserve existing values
            current_user_data = UserInfoSerializer(target_user).data

            # Only update fields that are in update_data
            for field in update_data:
                current_user_data[field] = update_data[field]

            # Update user with merged data
            serializer = UserInfoSerializer(target_user, data=current_user_data, partial=False)

            if serializer.is_valid():
                serializer.save()

                response_data = {
                    "success": True,
                    "message": "User updated successfully",
                    "updated_by": {
                        "user_id": logged_in_user_id,
                        "role_id": logged_in_role_id,
                        "is_admin": is_admin
                    },
                    "data": serializer.data,
                    "updated_fields": list(update_data.keys())
                }

                # Add image URLs to response if they were updated
                if update_data.get('aadhar_img'):
                    response_data["aadhar_url"] = update_data.get('aadhar_img')
                if update_data.get('stamp_img'):
                    response_data["stamp_url"] = update_data.get('stamp_img')
                if update_data.get('certificate'):
                    response_data["certificate_url"] = update_data.get('certificate')

                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {
                        "success": False,
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            return Response({
                "success": False,
                "error": "Update failed",
                "details": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ========== DELETE METHOD - PERMANENT DELETE ==========
    elif request.method == 'DELETE':
        try:
            # Store user info for response before deletion
            deleted_user_info = {
                "user_id": target_user.user_id,
                "name": target_user.name,
                "contact_number": target_user.contact_number,
                "role_id": target_user.role_id,
                "active_status": target_user.active_status
            }

            # Permanent delete from database
            target_user.delete()

            # If admin deleted someone else's account, include that info
            if is_admin and str(target_user_id) != str(logged_in_user_id):
                message = f"User account (ID: {target_user_id}) permanently deleted successfully by admin"
            else:
                message = "Your account has been permanently deleted successfully"

            return Response(
                {
                    "success": True,
                    "message": message,
                    "deleted_by": {
                        "user_id": logged_in_user_id,
                        "role_id": logged_in_role_id,
                        "is_admin": is_admin
                    },
                    "data": deleted_user_info
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response({
                "success": False,
                "error": "Delete failed",
                "details": str(e),
                # "trace": traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
def user_logout(request):
    """
    Logout API - Logs out the currently authenticated user
    - Takes user_id from token
    - Blacklists the refresh token
    """
    # ========== TOKEN AUTHENTICATION ==========
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    
    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        # Get the refresh token from request if provided
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        return Response(
            {
                "success": True,
                "message": "Logged out successfully"
            },
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {
                "success": False,
                "error": f"Logout failed: {str(e)}"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


# # Servise role 

# @api_view(['GET', 'POST', 'PUT', 'DELETE'])
# @active_user_required
# def combined_service_api(request):
#     """
#     Unified CRUD API for main_service, sub_service, and service mappings
#     GET: Fetch all main services with their subservices combined
#          Optionally filter by main_service_id or service_id (query params)
#     POST: Create main_service / sub_service / service mapping
#           body: type="main_service" / "sub_service" / "service"
#     PUT: Update main_service / sub_service / service mapping
#           body: type + relevant IDs + fields
#     DELETE: Delete main_service / sub_service / service
#           query param: type + id
    
#     Authentication Required: Valid JWT token
#     """
#     # ========== TOKEN AUTHENTICATION ==========
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
    
#     if not token_user:
#         return Response(
#             {
#                 "success": False,
#                 "error": "Authentication required. Please provide valid token."
#             },
#             status=status.HTTP_401_UNAUTHORIZED
#         )
    
#     # Get logged-in user info from token (optional - you can use this for logging if needed)
#     logged_in_user_id = token_user.get('user_id')
#     logged_in_role_id = token_user.get('role_id')
    
#     try:
#         # ------------------- GET -------------------------
#         if request.method == 'GET':
#             service_id = request.query_params.get('service_id')
#             main_service_id = request.query_params.get('main_service_id')
#             lang = request.query_params.get('lang', 'en')  # en, hi, mr, gu

#             with connection.cursor() as cursor:
#                 # Call the stored procedure
#                 cursor.execute("CALL GetMainServicesWithSubservices(%s, %s)", 
#                             [main_service_id, service_id])
#                 rows = cursor.fetchall()

#             # Group data by main_service_id
#             main_services_dict = {}
#             for row in rows:
#                 main_id, main_name, main_img, serv_id, sub_id, sub_name, price, sub_img = row

#                 if main_id not in main_services_dict:
#                     # Translate main service name if needed
#                     if lang != "en":
#                         translated_main = translate_text(main_name, lang)
#                     else:
#                         translated_main = main_name

#                     main_services_dict[main_id] = {
#                         "category_id": main_id,
#                         "category_name": translated_main,
#                         "category_image": main_img,
#                         "services": []
#                     }

#                 # If there is a service (serv_id not NULL), add it
#                 if serv_id is not None:
#                     # Translate subservice name if needed
#                     if lang != "en":
#                         translated_sub = translate_text(sub_name, lang)
#                     else:
#                         translated_sub = sub_name

#                     main_services_dict[main_id]["services"].append({
#                         "service_id": serv_id,
#                         "subservice_id": sub_id,
#                         "service_name": translated_sub,
#                         "price": float(price),
#                         "image": sub_img
#                     })

#             # Convert dictionary to list (preserve order by main_id, which is already ordered)
#             result = list(main_services_dict.values())

#             return Response({
#                 "success": True,
#                 "message": "Services fetched successfully",
#                 "data": result
#             }, status=status.HTTP_200_OK)

#         # ------------------- POST -------------------
#         elif request.method == 'POST':
#             obj_type = request.data.get('type')

#             if obj_type == 'main_service':
#                 # Create main service
#                 name = request.data.get('main_service_name')
#                 img_file = request.FILES.get('main_service_img')
#                 if not name:
#                     return Response({"error": "main_service_name required"}, status=status.HTTP_400_BAD_REQUEST)

#                 img_url = storage_service.upload_image('MAIN_SERVICE', img_file, img_file.name) if img_file else None
#                 with connection.cursor() as cursor:
#                     cursor.execute("INSERT INTO tbl_main_service (main_service_name, main_service_img) VALUES (%s,%s)", [name, img_url])
#                     cursor.execute("SELECT LAST_INSERT_ID()")
#                     new_id = cursor.fetchone()[0]

#                 return Response({"message": "Main service created", "main_service_id": new_id, "main_service_name": name, "main_service_img": img_url}, status=status.HTTP_201_CREATED)

#             elif obj_type == 'sub_service':
#                 # Create subservice
#                 name = request.data.get('subservice_name')
#                 price = request.data.get('price')
#                 main_id = request.data.get('main_service_id')
#                 img_file = request.FILES.get('sub_service_img')
#                 if not name or price is None or not main_id:
#                     return Response({"error": "subservice_name, price and main_service_id required"}, status=status.HTTP_400_BAD_REQUEST)

#                 img_url = storage_service.upload_image('SUBSERVICE', img_file, img_file.name) if img_file else None
#                 with connection.cursor() as cursor:
#                     cursor.execute("SELECT main_service_id FROM tbl_main_service WHERE main_service_id=%s", [main_id])
#                     if not cursor.fetchone():
#                         return Response({"error": "main_service_id does not exist"}, status=status.HTTP_400_BAD_REQUEST)
                    
#                     cursor.execute("INSERT INTO tbl_subservice (subservice_name, price, sub_service_img) VALUES (%s,%s,%s)", [name, price, img_url])
#                     cursor.execute("SELECT LAST_INSERT_ID()")
#                     new_subservice_id = cursor.fetchone()[0]
                    
#                     cursor.execute("INSERT INTO tbl_service (main_service_id, subservice_id) VALUES (%s,%s)", [main_id, new_subservice_id])

#                 return Response({"message": "Subservice created", "subservice_id": new_subservice_id, "subservice_name": name, "price": price, "main_service_id": main_id, "sub_service_img": img_url}, status=status.HTTP_201_CREATED)

#             elif obj_type == 'service':
#                 # Create service mapping
#                 main_id = request.data.get('main_service_id')
#                 sub_id = request.data.get('subservice_id')
#                 if not main_id or not sub_id:
#                     return Response({"error": "main_service_id and subservice_id required"}, status=status.HTTP_400_BAD_REQUEST)

#                 with connection.cursor() as cursor:
#                     # Check main service
#                     cursor.execute("SELECT main_service_name FROM tbl_main_service WHERE main_service_id=%s", [main_id])
#                     main = cursor.fetchone()
#                     if not main:
#                         return Response({"error": "main_service_id does not exist"}, status=status.HTTP_400_BAD_REQUEST)
#                     # Check subservice
#                     cursor.execute("SELECT subservice_name, price FROM tbl_subservice WHERE subservice_id=%s", [sub_id])
#                     sub = cursor.fetchone()
#                     if not sub:
#                         return Response({"error": "subservice_id does not exist"}, status=status.HTTP_400_BAD_REQUEST)
#                     # Check duplicate
#                     cursor.execute("SELECT service_id FROM tbl_service WHERE main_service_id=%s AND subservice_id=%s", [main_id, sub_id])
#                     if cursor.fetchone():
#                         return Response({"error": "Service mapping exists"}, status=status.HTTP_400_BAD_REQUEST)

#                     # Insert mapping
#                     cursor.execute("INSERT INTO tbl_service (main_service_id, subservice_id) VALUES (%s,%s)", [main_id, sub_id])
#                     cursor.execute("SELECT LAST_INSERT_ID()")
#                     new_id = cursor.fetchone()[0]

#                 return Response({"message": "Service created", "service_id": new_id, "main_service_id": main_id, "main_service_name": main[0], "subservice_id": sub_id, "subservice_name": sub[0], "price": sub[1]}, status=status.HTTP_201_CREATED)

#             else:
#                 return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)

#         # ------------------- PUT -------------------
#         elif request.method == 'PUT':
#             obj_type = request.data.get('type')

#             if obj_type == 'main_service':
#                 service_id = request.data.get('main_service_id')
#                 name = request.data.get('main_service_name')
#                 img_file = request.FILES.get('main_service_img')
#                 if not service_id or not name:
#                     return Response({"error": "main_service_id and main_service_name required"}, status=status.HTTP_400_BAD_REQUEST)
#                 img_url = storage_service.upload_image('MAIN_SERVICE', img_file, img_file.name) if img_file else None
#                 with connection.cursor() as cursor:
#                     if img_url:
#                         cursor.execute("UPDATE tbl_main_service SET main_service_name=%s, main_service_img=%s WHERE main_service_id=%s", [name, img_url, service_id])
#                     else:
#                         cursor.execute("UPDATE tbl_main_service SET main_service_name=%s WHERE main_service_id=%s", [name, service_id])
#                     if cursor.rowcount == 0:
#                         return Response({"error": "Main service not found"}, status=status.HTTP_404_NOT_FOUND)
#                 return Response({"message": "Main service updated", "main_service_id": service_id, "main_service_name": name, "main_service_img": img_url}, status=status.HTTP_200_OK)

#             elif obj_type == 'sub_service':
#                 sub_id = request.data.get('subservice_id')
#                 name = request.data.get('subservice_name')
#                 price = request.data.get('price')
#                 img_file = request.FILES.get('sub_service_img')
#                 if not sub_id or not name or price is None:
#                     return Response({"error": "subservice_id, subservice_name, price required"}, status=status.HTTP_400_BAD_REQUEST)
#                 img_url = storage_service.upload_image('SUBSERVICE', img_file, img_file.name) if img_file else None
#                 with connection.cursor() as cursor:
#                     if img_url:
#                         cursor.execute("UPDATE tbl_subservice SET subservice_name=%s, price=%s, sub_service_img=%s WHERE subservice_id=%s", [name, price, img_url, sub_id])
#                     else:
#                         cursor.execute("UPDATE tbl_subservice SET subservice_name=%s, price=%s WHERE subservice_id=%s", [name, price, sub_id])
#                     if cursor.rowcount == 0:
#                         return Response({"error": "Subservice not found"}, status=status.HTTP_404_NOT_FOUND)
#                 return Response({"message": "Subservice updated", "subservice_id": sub_id, "subservice_name": name, "price": price, "sub_service_img": img_url}, status=status.HTTP_200_OK)

#             elif obj_type == 'service':
#                 service_id = request.data.get('service_id')
#                 main_id = request.data.get('main_service_id')
#                 sub_id = request.data.get('subservice_id')
#                 if not service_id or not main_id or not sub_id:
#                     return Response({"error": "service_id, main_service_id, subservice_id required"}, status=status.HTTP_400_BAD_REQUEST)
#                 with connection.cursor() as cursor:
#                     # Check existence
#                     cursor.execute("SELECT service_id FROM tbl_service WHERE service_id=%s", [service_id])
#                     if not cursor.fetchone():
#                         return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)
#                     # Update mapping
#                     cursor.execute("UPDATE tbl_service SET main_service_id=%s, subservice_id=%s WHERE service_id=%s", [main_id, sub_id, service_id])
#                 return Response({"message": "Service updated", "service_id": service_id, "main_service_id": main_id, "subservice_id": sub_id}, status=status.HTTP_200_OK)

#             else:
#                 return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)

    
#         elif request.method == 'DELETE':
#             obj_type = request.data.get('type') or request.query_params.get('type')
#             if not obj_type:
#                 return Response(
#                     {"error": "type is required (send as JSON/form-data or query param)"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             with connection.cursor() as cursor:
#                 if obj_type == 'main_service':
#                     main_id = (request.data.get('main_service_id') or 
#                                request.query_params.get('main_service_id') or
#                                request.data.get('id') or 
#                                request.query_params.get('id'))
#                     if not main_id:
#                         return Response(
#                             {"error": "main_service_id is required for main_service deletion"},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#                     # Delete image
#                     cursor.execute("SELECT main_service_img FROM tbl_main_service WHERE main_service_id = %s", [main_id])
#                     row = cursor.fetchone()
#                     if row and row[0]:
#                         blob_name = row[0].split('/')[-1].split('?')[0]
#                         storage_service.delete_image('MAIN_SERVICE', blob_name)

#                     # Delete all service mappings for this main service
#                     cursor.execute("DELETE FROM tbl_service WHERE main_service_id = %s", [main_id])
#                     # Delete main service
#                     cursor.execute("DELETE FROM tbl_main_service WHERE main_service_id = %s", [main_id])
#                     if cursor.rowcount == 0:
#                         return Response({"error": "Main service not found"}, status=status.HTTP_404_NOT_FOUND)
#                     return Response({"message": "Main service deleted", "main_service_id": main_id}, status=status.HTTP_200_OK)

#                 elif obj_type == 'sub_service':
#                     sub_id = (request.data.get('subservice_id') or 
#                               request.query_params.get('subservice_id') or
#                               request.data.get('id') or 
#                               request.query_params.get('id'))
#                     if not sub_id:
#                         return Response(
#                             {"error": "subservice_id is required for sub_service deletion"},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#                     # Delete image
#                     cursor.execute("SELECT sub_service_img FROM tbl_subservice WHERE subservice_id = %s", [sub_id])
#                     row = cursor.fetchone()
#                     if row and row[0]:
#                         blob_name = row[0].split('/')[-1].split('?')[0]
#                         storage_service.delete_image('SUBSERVICE', blob_name)

#                     # Delete all service mappings for this subservice
#                     cursor.execute("DELETE FROM tbl_service WHERE subservice_id = %s", [sub_id])
#                     # Delete subservice
#                     cursor.execute("DELETE FROM tbl_subservice WHERE subservice_id = %s", [sub_id])
#                     if cursor.rowcount == 0:
#                         return Response({"error": "Subservice not found"}, status=status.HTTP_404_NOT_FOUND)
#                     return Response({"message": "Subservice deleted", "subservice_id": sub_id}, status=status.HTTP_200_OK)

#                 elif obj_type == 'service':
#                     # Option 1: by service_id
#                     service_id = (request.data.get('service_id') or 
#                                   request.query_params.get('service_id') or
#                                   request.data.get('id') or 
#                                   request.query_params.get('id'))
#                     if service_id:
#                         cursor.execute("DELETE FROM tbl_service WHERE service_id = %s", [service_id])
#                         if cursor.rowcount == 0:
#                             return Response({"error": "Service mapping not found"}, status=status.HTTP_404_NOT_FOUND)
#                         return Response({"message": "Service mapping deleted", "service_id": service_id}, status=status.HTTP_200_OK)

#                     # Option 2: by main_service_id + subservice_id
#                     main_id = request.data.get('main_service_id') or request.query_params.get('main_service_id')
#                     sub_id = request.data.get('subservice_id') or request.query_params.get('subservice_id')
#                     if main_id and sub_id:
#                         cursor.execute(
#                             "DELETE FROM tbl_service WHERE main_service_id = %s AND subservice_id = %s",
#                             [main_id, sub_id]
#                         )
#                         if cursor.rowcount == 0:
#                             return Response({"error": "Service mapping not found"}, status=status.HTTP_404_NOT_FOUND)
#                         return Response({"message": "Service mapping deleted", "main_service_id": main_id, "subservice_id": sub_id}, status=status.HTTP_200_OK)

#                     return Response(
#                         {"error": "For service deletion, provide either 'service_id' or both 'main_service_id' and 'subservice_id'"},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 else:
#                     return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)
#     except Exception as e:
#         return Response({"error": "Operation failed", "details": str(e)
#                         #  "trace": traceback.format_exc()
#                          }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@active_user_required
def combined_service_api(request):
    """
    Unified CRUD API for main_service, sub_service, and service mappings
    GET: Fetch all main services with their subservices combined
         Optionally filter by main_service_id or service_id or type_id (query params)
    POST: Create main_service / sub_service / service mapping
          body: type="main_service" / "sub_service" / "service"
    PUT: Update main_service / sub_service / service mapping
          body: type + relevant IDs + fields
    DELETE: Delete main_service / sub_service / service
          query param: type + id
    
    Authentication Required: Valid JWT token
    """
    # ========== TOKEN AUTHENTICATION ==========
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    
    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Get logged-in user info from token (optional - you can use this for logging if needed)
    logged_in_user_id = token_user.get('user_id')
    logged_in_role_id = token_user.get('role_id')
    
    try:
        # ------------------- GET -------------------------
        if request.method == 'GET':
            service_id = request.query_params.get('service_id')
            main_service_id = request.query_params.get('main_service_id')
            type_id = request.query_params.get('type_id')
            lang = request.query_params.get('lang', 'en')  # en, hi, mr, gu

            with connection.cursor() as cursor:
                # Call the stored procedure
                cursor.execute("CALL GetMainServicesWithSubservices(%s, %s, %s)", 
                            [main_service_id, service_id, type_id])
                rows = cursor.fetchall()

            # Group data by main_service_id
            main_services_dict = {}
            for row in rows:
                # row indices: 
                # 0: main_id, 1: main_name, 2: main_img, 3: type_id, 4: type_name, 
                # 5: serv_id, 6: sub_id, 7: sub_name, 8: price, 9: sub_img
                main_id = row[0]
                main_name = row[1]
                main_img = row[2]
                main_type_id = row[3]
                type_name = row[4]
                serv_id = row[5]
                sub_id = row[6]
                sub_name = row[7]
                price = row[8]
                sub_img = row[9]

                if main_id not in main_services_dict:
                    # Translate main service name if needed
                    if lang != "en":
                        translated_main = translate_text(main_name, lang)
                        if type_name:
                            translated_type_name = translate_text(type_name, lang)
                        else:
                            translated_type_name = type_name
                    else:
                        translated_main = main_name
                        translated_type_name = type_name

                    main_services_dict[main_id] = {
                        "category_id": main_id,
                        "category_name": translated_main,
                        "category_image": main_img,
                        "type_id": main_type_id,
                        "type_name": translated_type_name,
                        "services": []
                    }

                # If there is a service (serv_id not NULL), add it
                if serv_id is not None:
                    # Translate subservice name if needed
                    if lang != "en":
                        translated_sub = translate_text(sub_name, lang)
                    else:
                        translated_sub = sub_name

                    main_services_dict[main_id]["services"].append({
                        "service_id": serv_id,
                        "subservice_id": sub_id,
                        "service_name": translated_sub,
                        "price": float(price),
                        "image": sub_img
                    })

            # Convert dictionary to list (preserve order by main_id, which is already ordered)
            result = list(main_services_dict.values())

            return Response({
                "success": True,
                "message": "Services fetched successfully",
                "data": result
            }, status=status.HTTP_200_OK)

        # ------------------- POST -------------------
        elif request.method == 'POST':
            obj_type = request.data.get('type')

            if obj_type == 'main_service':
                # Create main service
                name = request.data.get('main_service_name')
                type_id = request.data.get('type_id')
                img_file = request.FILES.get('main_service_img')
                
                if not name:
                    return Response({"error": "main_service_name required"}, status=status.HTTP_400_BAD_REQUEST)
                
                if not type_id:
                    return Response({"error": "type_id is required"}, status=status.HTTP_400_BAD_REQUEST)

                img_url = storage_service.upload_image('MAIN_SERVICE', img_file, img_file.name) if img_file else None
                
                with connection.cursor() as cursor:
                    # Verify type_id exists
                    cursor.execute("SELECT type_id, type_name FROM tbl_service_type WHERE type_id = %s", [type_id])
                    type_result = cursor.fetchone()
                    if not type_result:
                        return Response({"error": "Invalid type_id"}, status=status.HTTP_400_BAD_REQUEST)
                    type_name = type_result[1]
                    
                    cursor.execute("INSERT INTO tbl_main_service (main_service_name, main_service_img, type_id) VALUES (%s,%s,%s)", 
                                  [name, img_url, type_id])
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    new_id = cursor.fetchone()[0]

                return Response({
                    "message": "Main service created", 
                    "main_service_id": new_id, 
                    "main_service_name": name, 
                    "main_service_img": img_url,
                    "type_id": type_id,
                    "type_name": type_name
                }, status=status.HTTP_201_CREATED)

            elif obj_type == 'sub_service':
                # Create subservice
                name = request.data.get('subservice_name')
                price = request.data.get('price')
                main_id = request.data.get('main_service_id')
                img_file = request.FILES.get('sub_service_img')
                if not name or price is None or not main_id:
                    return Response({"error": "subservice_name, price and main_service_id required"}, status=status.HTTP_400_BAD_REQUEST)

                img_url = storage_service.upload_image('SUBSERVICE', img_file, img_file.name) if img_file else None
                with connection.cursor() as cursor:
                    cursor.execute("SELECT main_service_id FROM tbl_main_service WHERE main_service_id=%s", [main_id])
                    if not cursor.fetchone():
                        return Response({"error": "main_service_id does not exist"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    cursor.execute("INSERT INTO tbl_subservice (subservice_name, price, sub_service_img) VALUES (%s,%s,%s)", [name, price, img_url])
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    new_subservice_id = cursor.fetchone()[0]
                    
                    cursor.execute("INSERT INTO tbl_service (main_service_id, subservice_id) VALUES (%s,%s)", [main_id, new_subservice_id])

                return Response({
                    "message": "Subservice created", 
                    "subservice_id": new_subservice_id, 
                    "subservice_name": name, 
                    "price": price, 
                    "main_service_id": main_id, 
                    "sub_service_img": img_url
                }, status=status.HTTP_201_CREATED)

            elif obj_type == 'service':
                # Create service mapping
                main_id = request.data.get('main_service_id')
                sub_id = request.data.get('subservice_id')
                if not main_id or not sub_id:
                    return Response({"error": "main_service_id and subservice_id required"}, status=status.HTTP_400_BAD_REQUEST)

                with connection.cursor() as cursor:
                    # Check main service
                    cursor.execute("SELECT main_service_name FROM tbl_main_service WHERE main_service_id=%s", [main_id])
                    main = cursor.fetchone()
                    if not main:
                        return Response({"error": "main_service_id does not exist"}, status=status.HTTP_400_BAD_REQUEST)
                    # Check subservice
                    cursor.execute("SELECT subservice_name, price FROM tbl_subservice WHERE subservice_id=%s", [sub_id])
                    sub = cursor.fetchone()
                    if not sub:
                        return Response({"error": "subservice_id does not exist"}, status=status.HTTP_400_BAD_REQUEST)
                    # Check duplicate
                    cursor.execute("SELECT service_id FROM tbl_service WHERE main_service_id=%s AND subservice_id=%s", [main_id, sub_id])
                    if cursor.fetchone():
                        return Response({"error": "Service mapping exists"}, status=status.HTTP_400_BAD_REQUEST)

                    # Insert mapping
                    cursor.execute("INSERT INTO tbl_service (main_service_id, subservice_id) VALUES (%s,%s)", [main_id, sub_id])
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    new_id = cursor.fetchone()[0]

                return Response({
                    "message": "Service created", 
                    "service_id": new_id, 
                    "main_service_id": main_id, 
                    "main_service_name": main[0], 
                    "subservice_id": sub_id, 
                    "subservice_name": sub[0], 
                    "price": sub[1]
                }, status=status.HTTP_201_CREATED)

            else:
                return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)

        # ------------------- PUT -------------------
        elif request.method == 'PUT':
            obj_type = request.data.get('type')

            if obj_type == 'main_service':
                service_id = request.data.get('main_service_id')
                name = request.data.get('main_service_name')
                type_id = request.data.get('type_id')
                img_file = request.FILES.get('main_service_img')
                
                if not service_id or not name:
                    return Response({"error": "main_service_id and main_service_name required"}, status=status.HTTP_400_BAD_REQUEST)
                
                img_url = storage_service.upload_image('MAIN_SERVICE', img_file, img_file.name) if img_file else None
                
                with connection.cursor() as cursor:
                    # Verify type_id exists if provided
                    if type_id:
                        cursor.execute("SELECT type_id, type_name FROM tbl_service_type WHERE type_id = %s", [type_id])
                        type_result = cursor.fetchone()
                        if not type_result:
                            return Response({"error": "Invalid type_id"}, status=status.HTTP_400_BAD_REQUEST)
                        type_name = type_result[1]
                    
                    # Build update query dynamically
                    update_fields = []
                    params = []
                    
                    update_fields.append("main_service_name = %s")
                    params.append(name)
                    
                    if type_id:
                        update_fields.append("type_id = %s")
                        params.append(type_id)
                    
                    if img_url:
                        update_fields.append("main_service_img = %s")
                        params.append(img_url)
                    
                    params.append(service_id)
                    
                    query = f"UPDATE tbl_main_service SET {', '.join(update_fields)} WHERE main_service_id = %s"
                    cursor.execute(query, params)
                    
                    if cursor.rowcount == 0:
                        return Response({"error": "Main service not found"}, status=status.HTTP_404_NOT_FOUND)
                    
                    # Fetch updated type_name for response
                    updated_type_name = None
                    if type_id:
                        updated_type_name = type_name
                    else:
                        # Get existing type_id
                        cursor.execute("SELECT type_id FROM tbl_main_service WHERE main_service_id = %s", [service_id])
                        existing_type_id = cursor.fetchone()
                        if existing_type_id and existing_type_id[0]:
                            cursor.execute("SELECT type_name FROM tbl_service_type WHERE type_id = %s", [existing_type_id[0]])
                            type_name_row = cursor.fetchone()
                            updated_type_name = type_name_row[0] if type_name_row else None

                response_data = {
                    "message": "Main service updated", 
                    "main_service_id": service_id, 
                    "main_service_name": name, 
                    "main_service_img": img_url if img_url else "Image not updated"
                }
                if type_id or updated_type_name:
                    response_data["type_id"] = type_id if type_id else existing_type_id[0]
                    response_data["type_name"] = updated_type_name
                
                return Response(response_data, status=status.HTTP_200_OK)

            elif obj_type == 'sub_service':
                sub_id = request.data.get('subservice_id')
                name = request.data.get('subservice_name')
                price = request.data.get('price')
                img_file = request.FILES.get('sub_service_img')
                if not sub_id or not name or price is None:
                    return Response({"error": "subservice_id, subservice_name, price required"}, status=status.HTTP_400_BAD_REQUEST)
                img_url = storage_service.upload_image('SUBSERVICE', img_file, img_file.name) if img_file else None
                with connection.cursor() as cursor:
                    if img_url:
                        cursor.execute("UPDATE tbl_subservice SET subservice_name=%s, price=%s, sub_service_img=%s WHERE subservice_id=%s", [name, price, img_url, sub_id])
                    else:
                        cursor.execute("UPDATE tbl_subservice SET subservice_name=%s, price=%s WHERE subservice_id=%s", [name, price, sub_id])
                    if cursor.rowcount == 0:
                        return Response({"error": "Subservice not found"}, status=status.HTTP_404_NOT_FOUND)
                return Response({
                    "message": "Subservice updated", 
                    "subservice_id": sub_id, 
                    "subservice_name": name, 
                    "price": price, 
                    "sub_service_img": img_url
                }, status=status.HTTP_200_OK)

            elif obj_type == 'service':
                service_id = request.data.get('service_id')
                main_id = request.data.get('main_service_id')
                sub_id = request.data.get('subservice_id')
                if not service_id or not main_id or not sub_id:
                    return Response({"error": "service_id, main_service_id, subservice_id required"}, status=status.HTTP_400_BAD_REQUEST)
                with connection.cursor() as cursor:
                    # Check existence
                    cursor.execute("SELECT service_id FROM tbl_service WHERE service_id=%s", [service_id])
                    if not cursor.fetchone():
                        return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)
                    # Update mapping
                    cursor.execute("UPDATE tbl_service SET main_service_id=%s, subservice_id=%s WHERE service_id=%s", [main_id, sub_id, service_id])
                return Response({
                    "message": "Service updated", 
                    "service_id": service_id, 
                    "main_service_id": main_id, 
                    "subservice_id": sub_id
                }, status=status.HTTP_200_OK)

            else:
                return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)

        # ------------------- DELETE -------------------
        elif request.method == 'DELETE':
            obj_type = request.data.get('type') or request.query_params.get('type')
            if not obj_type:
                return Response(
                    {"error": "type is required (send as JSON/form-data or query param)"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with connection.cursor() as cursor:
                if obj_type == 'main_service':
                    main_id = (request.data.get('main_service_id') or 
                               request.query_params.get('main_service_id') or
                               request.data.get('id') or 
                               request.query_params.get('id'))
                    if not main_id:
                        return Response(
                            {"error": "main_service_id is required for main_service deletion"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    # Delete image
                    cursor.execute("SELECT main_service_img FROM tbl_main_service WHERE main_service_id = %s", [main_id])
                    row = cursor.fetchone()
                    if row and row[0]:
                        blob_name = row[0].split('/')[-1].split('?')[0]
                        storage_service.delete_image('MAIN_SERVICE', blob_name)

                    # Delete all service mappings for this main service
                    cursor.execute("DELETE FROM tbl_service WHERE main_service_id = %s", [main_id])
                    # Delete main service
                    cursor.execute("DELETE FROM tbl_main_service WHERE main_service_id = %s", [main_id])
                    if cursor.rowcount == 0:
                        return Response({"error": "Main service not found"}, status=status.HTTP_404_NOT_FOUND)
                    return Response({"message": "Main service deleted", "main_service_id": main_id}, status=status.HTTP_200_OK)

                elif obj_type == 'sub_service':
                    sub_id = (request.data.get('subservice_id') or 
                              request.query_params.get('subservice_id') or
                              request.data.get('id') or 
                              request.query_params.get('id'))
                    if not sub_id:
                        return Response(
                            {"error": "subservice_id is required for sub_service deletion"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    # Delete image
                    cursor.execute("SELECT sub_service_img FROM tbl_subservice WHERE subservice_id = %s", [sub_id])
                    row = cursor.fetchone()
                    if row and row[0]:
                        blob_name = row[0].split('/')[-1].split('?')[0]
                        storage_service.delete_image('SUBSERVICE', blob_name)

                    # Delete all service mappings for this subservice
                    cursor.execute("DELETE FROM tbl_service WHERE subservice_id = %s", [sub_id])
                    # Delete subservice
                    cursor.execute("DELETE FROM tbl_subservice WHERE subservice_id = %s", [sub_id])
                    if cursor.rowcount == 0:
                        return Response({"error": "Subservice not found"}, status=status.HTTP_404_NOT_FOUND)
                    return Response({"message": "Subservice deleted", "subservice_id": sub_id}, status=status.HTTP_200_OK)

                elif obj_type == 'service':
                    # Option 1: by service_id
                    service_id = (request.data.get('service_id') or 
                                  request.query_params.get('service_id') or
                                  request.data.get('id') or 
                                  request.query_params.get('id'))
                    if service_id:
                        cursor.execute("DELETE FROM tbl_service WHERE service_id = %s", [service_id])
                        if cursor.rowcount == 0:
                            return Response({"error": "Service mapping not found"}, status=status.HTTP_404_NOT_FOUND)
                        return Response({"message": "Service mapping deleted", "service_id": service_id}, status=status.HTTP_200_OK)

                    # Option 2: by main_service_id + subservice_id
                    main_id = request.data.get('main_service_id') or request.query_params.get('main_service_id')
                    sub_id = request.data.get('subservice_id') or request.query_params.get('subservice_id')
                    if main_id and sub_id:
                        cursor.execute(
                            "DELETE FROM tbl_service WHERE main_service_id = %s AND subservice_id = %s",
                            [main_id, sub_id]
                        )
                        if cursor.rowcount == 0:
                            return Response({"error": "Service mapping not found"}, status=status.HTTP_404_NOT_FOUND)
                        return Response({"message": "Service mapping deleted", "main_service_id": main_id, "subservice_id": sub_id}, status=status.HTTP_200_OK)

                    return Response(
                        {"error": "For service deletion, provide either 'service_id' or both 'main_service_id' and 'subservice_id'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                else:
                    return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            "error": "Operation failed", 
            "details": str(e)
        }, status=status.HTTP_500_INITIAL_SERVER_ERROR)


# @api_view(['GET', 'PUT'])                     
# @active_user_required
# def user_service_api(request):
#     """
#     User Service API for fetching and updating orders.
#     GET: Fetch orders for the authenticated user (with optional filters)
#     PUT: Update an existing order (order_id in query params)
    
#     Authentication Required: Valid JWT token
#     """
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
#     if not token_user:
#         return Response({"success": False, "error": "Authentication required."},
#                         status=status.HTTP_401_UNAUTHORIZED)

#     logged_in_user_id = token_user.get('user_id')
#     logged_in_role_id = token_user.get('role_id')

#     try:
#         # ===================== GET =====================
#         if request.method == 'GET':
#             user_id = logged_in_user_id
#             order_id = request.query_params.get('order_id')
#             order_status = request.query_params.get('order_status')
#             payment_mode = request.query_params.get('payment_mode')
#             customer_order_status = request.query_params.get('customer_order_status')
#             from_date = request.query_params.get('from_date')
#             to_date = request.query_params.get('to_date')
#             min_amount = request.query_params.get('min_amount')
#             max_amount = request.query_params.get('max_amount')
#             service_id = request.query_params.get('service_id')
#             lang = request.query_params.get('lang', 'en')

#             with connection.cursor() as cursor:
#                 cursor.execute("CALL GetUserOrders(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
#                                [user_id, order_id, order_status, payment_mode, customer_order_status,
#                                 from_date, to_date, min_amount, max_amount, service_id])
#                 rows = cursor.fetchall()

#             # Group and translate (same as before)
#             orders_dict = {}
#             for r in rows:
#                 current_order_id = r[0]
#                 if current_order_id not in orders_dict:
#                     main_service_name_orig = r[21]
#                     if lang != 'en':
#                         translated_main_name = translate_text(main_service_name_orig, lang)
#                     else:
#                         translated_main_name = main_service_name_orig

#                     orders_dict[current_order_id] = {
#                         "order_id": r[0],
#                         "user_id": r[1],
#                         "total_amount": float(r[2]) if r[2] else 0,
#                         "payment_mode": r[3],
#                         "order_status": r[4],
#                         "customer_order_status": r[5],
#                         "latitude": float(r[6]) if r[6] else None,
#                         "longitude": float(r[7]) if r[7] else None,
#                         "otp": r[8],
#                         "confirm_at": str(r[9]) if r[9] else None,
#                         "cancel_at": str(r[10]) if r[10] else None,
#                         # "confirm_at": str(utc_to_ist(r[9])) if r[9] else None,
#                         # "cancel_at": str(utc_to_ist(r[10])) if r[10] else None,
#                         "accepted_by": r[11],
#                         "accepted_by_name": r[23],
#                         "completed_by": r[12],
#                         "completed_by_name": r[24],
#                         "order_at": str(r[19]),
#                         # "order_at": str(utc_to_ist(r[19])),
#                         "services": []
#                     }

#                 subservice_name_orig = r[22]
#                 if lang != 'en':
#                     translated_sub_name = translate_text(subservice_name_orig, lang)
#                 else:
#                     translated_sub_name = subservice_name_orig

#                 orders_dict[current_order_id]["services"].append({
#                     "sale_id": r[13],
#                     "service_id": r[14],
#                     "quantity": r[15],
#                     "item_price": float(r[16]) if r[16] else 0,
#                     "service_datetime": str(r[17]),
#                     "sub_service_img": r[18],
#                     "updated_at": str(r[20]) if r[20] else None,
#                     "main_service_name": translated_main_name if 'translated_main_name' in locals() else r[21],
#                     "subservice_name": translated_sub_name
#                 })

#             data = list(orders_dict.values())
#             return Response({"success": True, "data": data}, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT'])                     
@active_user_required
def user_service_api(request):
    """
    User Service API for fetching and updating orders.
    GET: Fetch orders for the authenticated user (with optional filters)
    PUT: Update an existing order (order_id in query params)
    
    Authentication Required: Valid JWT token
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    logged_in_user_id = token_user.get('user_id')
    logged_in_role_id = token_user.get('role_id')

    try:
        # ===================== GET =====================
        if request.method == 'GET':
            user_id = logged_in_user_id
            order_id = request.query_params.get('order_id')
            order_status = request.query_params.get('order_status')
            payment_mode = request.query_params.get('payment_mode')
            customer_order_status = request.query_params.get('customer_order_status')
            from_date = request.query_params.get('from_date')
            to_date = request.query_params.get('to_date')
            min_amount = request.query_params.get('min_amount')
            max_amount = request.query_params.get('max_amount')
            service_id = request.query_params.get('service_id')
            lang = request.query_params.get('lang', 'en')

            with connection.cursor() as cursor:
                cursor.execute("CALL GetUserOrders(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                               [user_id, order_id, order_status, payment_mode, customer_order_status,
                                from_date, to_date, min_amount, max_amount, service_id])
                rows = cursor.fetchall()

            # Group and translate
            orders_dict = {}
            for r in rows:
                current_order_id = r[0]
                if current_order_id not in orders_dict:
                    # Translate main service name
                    main_service_name_orig = r[21]
                    if lang != 'en':
                        translated_main_name = translate_text(main_service_name_orig, lang)
                    else:
                        translated_main_name = main_service_name_orig
                    
                    # Translate vendor names (accepted_by_name and completed_by_name)
                    accepted_by_name_orig = r[23]  # accepted_by_name
                    completed_by_name_orig = r[24]  # completed_by_name
                    
                    if lang != 'en':
                        if accepted_by_name_orig:
                            accepted_by_name = transliterate_name(accepted_by_name_orig, lang)
                        else:
                            accepted_by_name = accepted_by_name_orig
                        if completed_by_name_orig:
                            completed_by_name = transliterate_name(completed_by_name_orig, lang)
                        else:
                            completed_by_name = completed_by_name_orig
                    else:
                        accepted_by_name = accepted_by_name_orig
                        completed_by_name = completed_by_name_orig
                    
                    # Translate payment mode if needed
                    payment_mode_val = r[3]
                    if lang != 'en' and payment_mode_val:
                        payment_mode_val = translate_text(payment_mode_val, lang)

                    orders_dict[current_order_id] = {
                        "order_id": r[0],
                        "user_id": r[1],
                        "total_amount": float(r[2]) if r[2] else 0,
                        "payment_mode": payment_mode_val,
                        "order_status": r[4],  # Keep as is (English)
                        "customer_order_status": r[5],  # Keep as is (English)
                        "latitude": float(r[6]) if r[6] else None,
                        "longitude": float(r[7]) if r[7] else None,
                        "otp": r[8],
                        "confirm_at": str(r[9]) if r[9] else None,
                        "cancel_at": str(r[10]) if r[10] else None,
                        "accepted_by": r[11],
                        "accepted_by_name": accepted_by_name,
                        "completed_by": r[12],
                        "completed_by_name": completed_by_name,
                        "order_at": str(r[19]),
                        "services": []
                    }

                subservice_name_orig = r[22]
                if lang != 'en':
                    translated_sub_name = translate_text(subservice_name_orig, lang)
                else:
                    translated_sub_name = subservice_name_orig

                orders_dict[current_order_id]["services"].append({
                    "sale_id": r[13],
                    "service_id": r[14],
                    "quantity": r[15],
                    "item_price": float(r[16]) if r[16] else 0,
                    "service_datetime": str(r[17]),
                    "sub_service_img": r[18],
                    "updated_at": str(r[20]) if r[20] else None,
                    "main_service_name": translated_main_name,
                    "subservice_name": translated_sub_name
                })

            data = list(orders_dict.values())
            return Response({"success": True, "data": data}, status=status.HTTP_200_OK)

        # ===================== PUT =====================
        elif request.method == 'PUT':
            user_id = logged_in_user_id
            order_id = request.query_params.get('order_id')
            if not order_id:
                return Response({"success": False, "error": "order_id is required in query params"},
                                status=status.HTTP_400_BAD_REQUEST)

            service_ids = request.data.get('service_id')
            quantities = request.data.get('quantity')
            service_datetime = request.data.get('service_datetime')
            address_text = request.data.get('text')
            customer_order_status = request.data.get('customer_order_status')
            payment_mode = request.data.get('payment_mode')

            lat, lon = None, None
            if address_text:
                lat, lon = get_lat_long_from_address(address_text)
                if not lat or not lon:
                    return Response({"success": False, "error": "Invalid address"},
                                    status=status.HTTP_400_BAD_REQUEST)

            service_ids_json = None
            quantities_json = None
            if service_ids is not None and quantities is not None:
                if not isinstance(service_ids, list) or not isinstance(quantities, list):
                    return Response({"success": False, "error": "service_id and quantity must be arrays"},
                                    status=status.HTTP_400_BAD_REQUEST)
                if len(service_ids) != len(quantities):
                    return Response({"success": False, "error": "service_id and quantity length must match"},
                                    status=status.HTTP_400_BAD_REQUEST)
                import json
                service_ids_json = json.dumps(service_ids)
                quantities_json = json.dumps(quantities)

            from datetime import datetime
            current_time = datetime.now()

            with connection.cursor() as cursor:
                cursor.execute("CALL UpdateOrder(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                               [order_id, user_id, lat, lon, customer_order_status, payment_mode,
                                service_ids_json, quantities_json, service_datetime, current_time])

            # Fetch updated order details using GetOrderDetails
            with connection.cursor() as cursor:
                cursor.execute("CALL GetOrderDetails(%s)", [order_id])
                updated_order = cursor.fetchone()
                cursor.nextset()
                services_rows = cursor.fetchall()

            services = []
            for s in services_rows:
                services.append({
                    "sale_id": s[0],
                    "service_id": s[1],
                    "quantity": s[2],
                    "item_price": float(s[3]) if s[3] else 0,
                    "service_datetime": str(s[4]),
                    "sub_service_img": s[5],
                    "order_at": str(s[6]),
                    "updated_at": str(s[7]) if s[7] else None,
                    "main_service_name": s[8],
                    "subservice_name": s[9]
                })

            response_data = {
                "order_id": updated_order[0],
                "user_id": updated_order[1],
                "total_amount": float(updated_order[2]) if updated_order[2] else 0,
                "payment_mode": updated_order[3],
                "order_status": updated_order[4],
                "customer_order_status": updated_order[5],
                "latitude": float(updated_order[6]) if updated_order[6] else None,
                "longitude": float(updated_order[7]) if updated_order[7] else None,
                "otp": updated_order[8],
                "confirm_at": str(updated_order[9]) if updated_order[9] else None,
                "cancel_at": str(updated_order[10]) if updated_order[10] else None,
                "accepted_by": updated_order[11],
                "accepted_by_name": updated_order[13],
                "completed_by": updated_order[12],
                "completed_by_name": updated_order[14],
                "services": services
            }

            return Response({"success": True, "message": "Order updated successfully", "data": response_data},
                            status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"success": False, "error": "Operation failed", "details": str(e)
                        #  "trace": traceback.format_exc()
                         },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# # Feedback

@api_view(['POST', 'GET', 'PUT', 'DELETE'])             # # 
@active_user_required
def feedback_api(request):
    """
    Feedback API for orders
    POST: Create feedback/complaint for an order
    GET: Get feedback(s) - optionally filter by order_id or feedback_id
    PUT: Update feedback/complaint
    DELETE: Delete feedback
    
    Authentication Required: Valid JWT token
    """
    # ========== TOKEN AUTHENTICATION ==========
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    
    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Get logged-in user info from token
    logged_in_user_id = token_user.get('user_id')
    logged_in_role_id = token_user.get('role_id')
    
    try:
        # ===================== POST - Create Feedback =====================
        if request.method == 'POST':
            order_id = request.data.get('order_id')
            feedback_type = request.data.get('type', 'feedback')
            comment = request.data.get('comment')
            rating = request.data.get('rating')
            
            # Validation
            if not order_id:
                return Response(
                    {"error": "order_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify order exists and belongs to the user
            with connection.cursor() as cursor:
                cursor.execute("SELECT user_id FROM tbl_sales_details WHERE order_id = %s", [order_id])
                order = cursor.fetchone()
                
                if not order:
                    return Response(
                        {"error": "Order not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                if str(order[0]) != str(logged_in_user_id):
                    return Response(
                        {"error": "You can only provide feedback for your own orders"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Check if feedback already exists
                cursor.execute("SELECT feedback_id FROM tbl_feedback WHERE order_id = %s", [order_id])
                if cursor.fetchone():
                    return Response(
                        {"error": "Feedback already exists for this order. Use PUT to update."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate based on type
                if feedback_type == 'feedback':
                    if rating is None:
                        return Response(
                            {"error": "rating is required for feedback"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    try:
                        rating = int(rating)
                        if rating < 1 or rating > 5:
                            return Response(
                                {"error": "rating must be between 1 and 5"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    except ValueError:
                        return Response(
                            {"error": "rating must be a number"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Call stored procedure
                    cursor.callproc('CreateFeedback', [order_id, feedback_type, comment, rating, None, 0])
                    cursor.execute("SELECT @_CreateFeedback_5")  # OUT parameter index 5
                    feedback_id = cursor.fetchone()[0]
                    
                elif feedback_type == 'complaint':
                    if not comment:
                        return Response(
                            {"error": "comment is required for complaint"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    cursor.callproc('CreateFeedback', [order_id, feedback_type, comment, None, 'pending', 0])
                    cursor.execute("SELECT @_CreateFeedback_5")
                    feedback_id = cursor.fetchone()[0]
                    
                else:
                    return Response(
                        {"error": "type must be 'feedback' or 'complaint'"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Fetch the created feedback
                cursor.execute("CALL GetFeedbacks(%s, NULL, NULL, NULL, NULL)", [feedback_id])
                new_feedback = cursor.fetchone()
                
                response_data = {
                    "feedback_id": new_feedback[0],
                    "order_id": new_feedback[1],
                    "type": new_feedback[2],
                    "comment": new_feedback[3],
                    "rating": new_feedback[4],
                    "com_status": new_feedback[5],
                    "created_at": str(new_feedback[6]),
                    "updated_at": str(new_feedback[7])
                }
                
                return Response({
                    "success": True,
                    "message": f"{feedback_type.capitalize()} created successfully",
                    "data": response_data
                }, status=status.HTTP_201_CREATED)


        elif request.method == 'GET':                            # # woring code - added for all langauge
            feedback_id = request.query_params.get('feedback_id')
            order_id = request.query_params.get('order_id')
            filter_type = request.query_params.get('type')
            filter_com_status = request.query_params.get('com_status')
            lang = request.query_params.get('lang', 'en')   # language parameter

            # Convert empty strings to None
            if filter_type == '':
                filter_type = None
            if filter_com_status == '':
                filter_com_status = None

            # Determine target user_id for filtering
            if str(logged_in_role_id) in ['1', '2']:
                target_user_id = None
            else:
                target_user_id = logged_in_user_id

            with connection.cursor() as cursor:
                cursor.callproc('GetFeedbacks', [feedback_id, order_id, target_user_id, filter_type, filter_com_status])

                if feedback_id or order_id:
                    # Single feedback or order-specific: only details
                    rows = cursor.fetchall()
                    response_data = []
                    for r in rows:
                        # Extract fields
                        feedback_type = r[2]
                        comment = r[3]
                        com_status = r[5]
                        user_name = r[9]
                        vendor_name = r[11]

                        if lang != 'en':
                            if feedback_type:
                                feedback_type = translate_text(feedback_type, lang)
                            if comment:
                                comment = translate_text(comment, lang)
                            if com_status:
                                com_status = translate_text(com_status, lang)
                            if user_name:
                                user_name = transliterate_name(user_name, lang)
                            if vendor_name:
                                vendor_name = transliterate_name(vendor_name, lang)

                        response_data.append({
                            "feedback_id": r[0],
                            "order_id": r[1],
                            "type": feedback_type,
                            "comment": comment,
                            "rating": r[4],
                            "com_status": com_status,
                            "created_at": str(r[6]),
                            "updated_at": str(r[7]),
                            "user_id": r[8],
                            "user_name": user_name,
                            "user_mobile": r[10],
                            "vendor_name": vendor_name
                        })
                    return Response({"success": True, "data": response_data}, status=status.HTTP_200_OK)

                else:
                    # General list: first summary, then details
                    summary = cursor.fetchone()
                    if not summary:
                        return Response({"success": True, "data": {"summary": {}, "feedbacks": []}}, status=status.HTTP_200_OK)

                    summary_data = {
                        "total": summary[0],
                        "feedback_count": summary[1],
                        "complaint_count": summary[2],
                        "pending_complaint_count": summary[3],
                        "resolved_complaint_count": summary[4]
                    }

                    cursor.nextset()
                    rows = cursor.fetchall()
                    feedbacks = []
                    for r in rows:
                        feedback_type = r[2]
                        comment = r[3]
                        com_status = r[5]
                        user_name = r[9]
                        vendor_name = r[11]

                        if lang != 'en':
                            if feedback_type:
                                feedback_type = translate_text(feedback_type, lang)
                            if comment:
                                comment = translate_text(comment, lang)
                            if com_status:
                                com_status = translate_text(com_status, lang)
                            if user_name:
                                user_name = transliterate_name(user_name, lang)
                            if vendor_name:
                                vendor_name = transliterate_name(vendor_name, lang)

                        feedbacks.append({
                            "feedback_id": r[0],
                            "order_id": r[1],
                            "type": feedback_type,
                            "comment": comment,
                            "rating": r[4],
                            "com_status": com_status,
                            "created_at": str(r[6]),
                            "updated_at": str(r[7]),
                            "user_id": r[8],
                            "user_name": user_name,
                            "user_mobile": r[10],
                            "vendor_name": vendor_name
                        })

                    return Response({
                        "success": True,
                        "data": {
                            "summary": summary_data,
                            "feedbacks": feedbacks
                        }
                    }, status=status.HTTP_200_OK)
        
        # ===================== PUT - Update Feedback =====================
        elif request.method == 'PUT':
            feedback_id = request.query_params.get('feedback_id')
            if not feedback_id:
                return Response({"error": "feedback_id is required in query params"},
                                status=status.HTTP_400_BAD_REQUEST)

            comment = request.data.get('comment')
            rating = request.data.get('rating')
            com_status = request.data.get('com_status')

            with connection.cursor() as cursor:
                # Check feedback exists and belongs to user
                cursor.execute("""
                    SELECT f.type, sd.user_id 
                    FROM tbl_feedback f
                    INNER JOIN tbl_sales_details sd ON f.order_id = sd.order_id
                    WHERE f.feedback_id = %s
                """, [feedback_id])
                feedback = cursor.fetchone()

                if not feedback:
                    return Response({"error": "Feedback not found"},
                                    status=status.HTTP_404_NOT_FOUND)

                feedback_type = feedback[0]
                feedback_owner_id = feedback[1]

                if str(feedback_owner_id) != str(logged_in_user_id) and str(logged_in_role_id) not in ['1', '2']:
                    return Response({"error": "You can only update your own feedback"},
                                    status=status.HTTP_403_FORBIDDEN)

                # Validate inputs
                rating_val = None
                if feedback_type == 'feedback' and rating is not None:
                    try:
                        rating_val = int(rating)
                        if rating_val < 1 or rating_val > 5:
                            return Response({"error": "rating must be between 1 and 5"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    except ValueError:
                        return Response({"error": "rating must be a number"},
                                        status=status.HTTP_400_BAD_REQUEST)

                com_status_val = None
                if feedback_type == 'complaint' and com_status is not None:
                    if com_status.lower() not in ['pending', 'resolved']:
                        return Response({"error": "com_status must be 'pending' or 'resolved'"},
                                        status=status.HTTP_400_BAD_REQUEST)
                    com_status_val = com_status.lower()

                # Call update procedure
                cursor.callproc('UpdateFeedback', [feedback_id, comment, rating_val, com_status_val])

                # Fetch updated feedback – note: 5 arguments required
                cursor.execute("CALL GetFeedbacks(%s, NULL, NULL, NULL, NULL)", [feedback_id])
                updated_feedback = cursor.fetchone()

                response_data = {
                    "feedback_id": updated_feedback[0],
                    "order_id": updated_feedback[1],
                    "type": updated_feedback[2],
                    "comment": updated_feedback[3],
                    "rating": updated_feedback[4],
                    "com_status": updated_feedback[5],
                    "created_at": str(updated_feedback[6]),
                    "updated_at": str(updated_feedback[7])
                }

                return Response({
                    "success": True,
                    "message": "Feedback updated successfully",
                    "data": response_data
                }, status=status.HTTP_200_OK)
        
        # ===================== DELETE - Delete Feedback =====================
        elif request.method == 'DELETE':
            feedback_id = request.query_params.get('feedback_id')
            
            if not feedback_id:
                return Response(
                    {"error": "feedback_id is required in query params"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with connection.cursor() as cursor:
                # Check ownership
                cursor.execute("""
                    SELECT sd.user_id 
                    FROM tbl_feedback f
                    INNER JOIN tbl_sales_details sd ON f.order_id = sd.order_id
                    WHERE f.feedback_id = %s
                """, [feedback_id])
                result = cursor.fetchone()
                
                if not result:
                    return Response(
                        {"error": "Feedback not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                if str(result[0]) != str(logged_in_user_id) and str(logged_in_role_id) not in ['1', '2']:
                    return Response(
                        {"error": "You can only delete your own feedback"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Call delete procedure
                cursor.execute("CALL DeleteFeedback(%s)", [feedback_id])
                
                return Response({
                    "success": True,
                    "message": "Feedback deleted successfully"
                }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            "error": "Operation failed",
            "details": str(e),
            # "trace": traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 




# ==================== VENDOR FLOW APIS ====================
# code for english lang 

# @api_view(['GET'])                        # # 
# @active_user_required
# @permission_classes([IsAuthenticated])
# def vendor_pending_notifications(request):
#     """
#     GET: Get all pending order notifications for the authenticated vendor
#     - Returns orders that are within 4km radius and not yet accepted/rejected
#     - Distance is calculated in the stored procedure
#     """
#     # ========== TOKEN AUTHENTICATION ==========
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
    
#     if not token_user:
#         return Response(
#             {
#                 "success": False,
#                 "error": "Authentication required. Please provide valid token."
#             },
#             status=status.HTTP_401_UNAUTHORIZED
#         )
    
#     vendor_id = token_user.get('user_id')
#     vendor_role_id = token_user.get('role_id')
    
#     # Verify vendor role
#     if str(vendor_role_id) != '3':
#         return Response(
#             {
#                 "success": False,
#                 "error": "Access denied. Only vendors can view notifications."
#             },
#             status=status.HTTP_403_FORBIDDEN
#         )
    
#     try:
#         # Verify vendor is approved and get location
#         with connection.cursor() as cursor:
#             cursor.execute("""
#                 SELECT is_approved, active_status, user_lat, user_long 
#                 FROM tbl_user 
#                 WHERE user_id = %s
#             """, [vendor_id])
            
#             vendor = cursor.fetchone()
#             if not vendor:
#                 return Response(
#                     {"error": "Vendor not found"},
#                     status=status.HTTP_404_NOT_FOUND
#                 )
            
#             if vendor[0] != 'approved':
#                 return Response(
#                     {
#                         "success": False,
#                         "error": "Your account is not approved yet. Please wait for admin approval."
#                     },
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             if vendor[1] != '1':
#                 return Response(
#                     {
#                         "success": False,
#                         "error": "Your account is inactive. Please contact admin."
#                     },
#                     status=status.HTTP_403_FORBIDDEN
#                 )
            
#             vendor_lat = vendor[2]
#             vendor_lon = vendor[3]
#             if not vendor_lat or not vendor_lon:
#                 return Response(
#                     {
#                         "success": False,
#                         "error": "Vendor location not set. Please update your location in profile."
#                     },
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
        
#         # Call stored procedure to get pending notifications with distance
#         with connection.cursor() as cursor:
#             cursor.callproc('GetVendorPendingNotifications', [vendor_id, vendor_lat, vendor_lon])
#             rows = cursor.fetchall()
        
#         # Build the response in the same structure as before
#         notifications = []              # # if this code does not display distance then open bellows code
#         for row in rows:
#             # row indices based on SELECT order in procedure
#             notification = {
#                 "notification_id": row[0],
#                 "order_id": row[1],
#                 "vendor_id": row[2],
#                 "accepted_by": row[3],
#                 "rejected_by": row[4],
#                 "accepted_at": str(row[5]) if row[5] else None,
#                 "rejected_at": str(row[6]) if row[6] else None,
#                 "order_at": str(row[7]),
#                 "reject_reason": row[8],
#                 "order_details": {
#                     "customer_id": row[9],
#                     "customer_name": row[10],
#                     "customer_mobile": row[11],
#                     "total_amount": float(row[12]) if row[12] else 0,
#                     "payment_mode": row[13],
#                     "order_status": row[14],
#                     "customer_order_status": row[15],
#                     "customer_latitude": float(row[16]) if row[16] else None,
#                     "customer_longitude": float(row[17]) if row[17] else None,
#                     "otp": row[18],
#                     "distance_from_vendor_km": float(row[19]) if row[19] else None
#                 }
#             }
#             notifications.append(notification)

        
#         return Response({
#             "success": True,
#             "message": "Pending notifications fetched successfully",
#             "total_notifications": len(notifications),
#             "data": notifications
#         }, status=status.HTTP_200_OK)
        
#     except Exception as e:
#         return Response({
#             "success": False,
#             "error": "Failed to fetch notifications",
#             "details": str(e),
#             # "trace": traceback.format_exc()
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





# # code for multilangauge 

@api_view(['GET'])
@active_user_required
@permission_classes([IsAuthenticated])
def vendor_pending_notifications(request):
    """
    GET: Get all pending order notifications for the authenticated vendor
    - Returns orders that are within 4km radius and not yet accepted/rejected
    - Distance is calculated in the stored procedure
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    
    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')
    
    # Verify vendor role
    if str(vendor_role_id) != '3':
        return Response(
            {
                "success": False,
                "error": "Access denied. Only vendors can view notifications."
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get language parameter
    lang = request.query_params.get('lang', 'en')
    
    try:
        # Verify vendor is approved and get location
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT is_approved, active_status, user_lat, user_long 
                FROM tbl_user 
                WHERE user_id = %s
            """, [vendor_id])
            
            vendor = cursor.fetchone()
            if not vendor:
                return Response(
                    {"error": "Vendor not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if vendor[0] != 'approved':
                return Response(
                    {
                        "success": False,
                        "error": "Your account is not approved yet. Please wait for admin approval."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if vendor[1] != '1':
                return Response(
                    {
                        "success": False,
                        "error": "Your account is inactive. Please contact admin."
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            vendor_lat = vendor[2]
            vendor_lon = vendor[3]
            if not vendor_lat or not vendor_lon:
                return Response(
                    {
                        "success": False,
                        "error": "Vendor location not set. Please update your location in profile."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Call stored procedure to get pending notifications with distance
        with connection.cursor() as cursor:
            cursor.callproc('GetVendorPendingNotifications', [vendor_id, vendor_lat, vendor_lon])
            rows = cursor.fetchall()
        
        # Build the response with language translation
        notifications = []
        for row in rows:
            # Translate customer name if needed
            customer_name = row[10]
            order_status = row[14]
            customer_order_status = row[15]
            payment_mode = row[13]
            
            if lang != 'en':
                if customer_name:
                    customer_name = transliterate_name(customer_name, lang)
                if order_status:
                    order_status = translate_text(order_status, lang)
                if customer_order_status:
                    customer_order_status = translate_text(customer_order_status, lang)
                if payment_mode:
                    payment_mode = translate_text(payment_mode, lang)
            
            notification = {
                "notification_id": row[0],
                "order_id": row[1],
                "vendor_id": row[2],
                "accepted_by": row[3],
                "rejected_by": row[4],
                "accepted_at": str(row[5]) if row[5] else None,
                "rejected_at": str(row[6]) if row[6] else None,
                "order_at": str(row[7]),
                "reject_reason": row[8],
                "order_details": {
                    "customer_id": row[9],
                    "customer_name": customer_name,
                    "customer_mobile": row[11],
                    "total_amount": float(row[12]) if row[12] else 0,
                    "payment_mode": payment_mode,
                    "order_status": order_status,
                    "customer_order_status": customer_order_status,
                    "customer_latitude": float(row[16]) if row[16] else None,
                    "customer_longitude": float(row[17]) if row[17] else None,
                    "otp": row[18],
                    "distance_from_vendor_km": float(row[19]) if row[19] else None
                }
            }
            notifications.append(notification)
        
        return Response({
            "success": True,
            "message": "Pending notifications fetched successfully",
            "total_notifications": len(notifications),
            "data": notifications
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch notifications",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

# # # code for english lang 

# @api_view(['GET'])
# @active_user_required
# @permission_classes([IsAuthenticated])
# def vendor_order_history(request):
#     """
#     GET: Get all orders (accepted/rejected) history for the authenticated vendor
#     Optional filters:
#         - status: 'accepted', 'rejected', 'all' (default: 'all') – based on notification status
#         - order_status: 'pending', 'accepted', 'inprocess', 'completed', etc. – based on order status
#     """
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
#     if not token_user:
#         return Response({"success": False, "error": "Authentication required."}, 
#                         status=status.HTTP_401_UNAUTHORIZED)

#     vendor_id = token_user.get('user_id')
#     vendor_role_id = token_user.get('role_id')
#     if str(vendor_role_id) != '3':
#         return Response({"success": False, "error": "Access denied. Only vendors can view order history."},
#                         status=status.HTTP_403_FORBIDDEN)

#     try:
#         status_filter = request.query_params.get('status', 'all')
#         if status_filter not in ['all', 'accepted', 'rejected']:
#             return Response({"success": False, "error": "Invalid status filter. Use: all, accepted, or rejected"},
#                             status=status.HTTP_400_BAD_REQUEST)

#         order_status_filter = request.query_params.get('order_status')  # new filter

#         with connection.cursor() as cursor:
#             cursor.callproc('GetVendorOrderHistory', [vendor_id, status_filter, order_status_filter])
#             rows = cursor.fetchall()

#         notifications = []
#         for row in rows:
#             notification = {
#                 "notification_id": row[0],
#                 "order_id": row[1],
#                 "vendor_id": row[2],
#                 "accepted_by": row[3],
#                 "rejected_by": row[4],
#                 "accepted_at": str(row[5]) if row[5] else None,
#                 "rejected_at": str(row[6]) if row[6] else None,
#                 "order_at": str(row[7]),
#                 "reject_reason": row[8],
#                 "order_details": {
#                     "customer_id": row[9],
#                     "customer_name": row[10],
#                     "customer_mobile": row[11],
#                     "total_amount": float(row[12]) if row[12] else 0,
#                     "payment_mode": row[13],
#                     "order_status": row[14],
#                     "customer_order_status": row[15],
#                     "customer_latitude": float(row[16]) if row[16] else None,
#                     "customer_longitude": float(row[17]) if row[17] else None,
#                     "otp": row[18],
#                     "distance_from_vendor_km": None  # Not computed for history
#                 }
#             }
#             notifications.append(notification)

#         return Response({
#             "success": True,
#             "message": f"{status_filter.capitalize()} orders fetched successfully",
#             "total_orders": len(notifications),
#             "data": notifications
#         }, status=status.HTTP_200_OK)

#     except Exception as e:
#         return Response({
#             "success": False,
#             "error": "Failed to fetch order history",
#             "details": str(e),
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# # # code for multilangauge 
# @api_view(['GET'])
# @active_user_required
# @permission_classes([IsAuthenticated])
# def vendor_order_history(request):
#     """
#     GET: Get all orders (accepted/rejected) history for the authenticated vendor
#     Optional filters:
#         - status: 'accepted', 'rejected', 'all' (default: 'all') – based on notification status
#         - order_status: 'pending', 'accepted', 'inprocess', 'completed', etc. – based on order status
#     """
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
#     if not token_user:
#         return Response({"success": False, "error": "Authentication required."}, 
#                         status=status.HTTP_401_UNAUTHORIZED)

#     vendor_id = token_user.get('user_id')
#     vendor_role_id = token_user.get('role_id')
#     if str(vendor_role_id) != '3':
#         return Response({"success": False, "error": "Access denied. Only vendors can view order history."},
#                         status=status.HTTP_403_FORBIDDEN)

#     # Get language parameter
#     lang = request.query_params.get('lang', 'en')

#     try:
#         status_filter = request.query_params.get('status', 'all')
#         if status_filter not in ['all', 'accepted', 'rejected']:
#             return Response({"success": False, "error": "Invalid status filter. Use: all, accepted, or rejected"},
#                             status=status.HTTP_400_BAD_REQUEST)

#         order_status_filter = request.query_params.get('order_status')  # new filter

#         with connection.cursor() as cursor:
#             cursor.callproc('GetVendorOrderHistory', [vendor_id, status_filter, order_status_filter])
#             rows = cursor.fetchall()

#         notifications = []
#         for row in rows:
#             # Translate text fields
#             customer_name = row[10]
#             order_status = row[14]
#             customer_order_status = row[15]
#             payment_mode = row[13]
            
#             if lang != 'en':
#                 if customer_name:
#                     customer_name = transliterate_name(customer_name, lang)
#                 if order_status:
#                     order_status = translate_text(order_status, lang)
#                 if customer_order_status:
#                     customer_order_status = translate_text(customer_order_status, lang)
#                 if payment_mode:
#                     payment_mode = translate_text(payment_mode, lang)
            
#             notification = {
#                 "notification_id": row[0],
#                 "order_id": row[1],
#                 "vendor_id": row[2],
#                 "accepted_by": row[3],
#                 "rejected_by": row[4],
#                 "accepted_at": str(row[5]) if row[5] else None,
#                 "rejected_at": str(row[6]) if row[6] else None,
#                 "order_at": str(row[7]),
#                 "reject_reason": row[8],
#                 "order_details": {
#                     "customer_id": row[9],
#                     "customer_name": customer_name,
#                     "customer_mobile": row[11],
#                     "total_amount": float(row[12]) if row[12] else 0,
#                     "payment_mode": payment_mode,
#                     "order_status": order_status,
#                     "customer_order_status": customer_order_status,
#                     "customer_latitude": float(row[16]) if row[16] else None,
#                     "customer_longitude": float(row[17]) if row[17] else None,
#                     "otp": row[18],
#                     "distance_from_vendor_km": None  # Not computed for history
#                 }
#             }
#             notifications.append(notification)

#         return Response({
#             "success": True,
#             "message": f"{status_filter.capitalize()} orders fetched successfully",
#             "total_orders": len(notifications),
#             "data": notifications
#         }, status=status.HTTP_200_OK)

#     except Exception as e:
#         return Response({
#             "success": False,
#             "error": "Failed to fetch order history",
#             "details": str(e),
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# # code for orser status in english for all langauge 

@api_view(['GET'])
@active_user_required
@permission_classes([IsAuthenticated])
def vendor_order_history(request):
    """
    GET: Get all orders (accepted/rejected) history for the authenticated vendor
    Optional filters:
        - status: 'accepted', 'rejected', 'all' (default: 'all') – based on notification status
        - order_status: 'pending', 'accepted', 'inprocess', 'completed', etc. – based on order status
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."}, 
                        status=status.HTTP_401_UNAUTHORIZED)

    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')
    if str(vendor_role_id) != '3':
        return Response({"success": False, "error": "Access denied. Only vendors can view order history."},
                        status=status.HTTP_403_FORBIDDEN)

    # Get language parameter
    lang = request.query_params.get('lang', 'en')

    try:
        status_filter = request.query_params.get('status', 'all')
        if status_filter not in ['all', 'accepted', 'rejected']:
            return Response({"success": False, "error": "Invalid status filter. Use: all, accepted, or rejected"},
                            status=status.HTTP_400_BAD_REQUEST)

        order_status_filter = request.query_params.get('order_status')

        with connection.cursor() as cursor:
            cursor.callproc('GetVendorOrderHistory', [vendor_id, status_filter, order_status_filter])
            rows = cursor.fetchall()

        notifications = []
        for row in rows:
            # Translate only text fields (not statuses)
            customer_name = row[10]
            payment_mode = row[13]
            
            if lang != 'en':
                if customer_name:
                    customer_name = transliterate_name(customer_name, lang)
                if payment_mode:
                    payment_mode = translate_text(payment_mode, lang)
            
            notification = {
                "notification_id": row[0],
                "order_id": row[1],
                "vendor_id": row[2],
                "accepted_by": row[3],
                "rejected_by": row[4],
                "accepted_at": str(row[5]) if row[5] else None,
                "rejected_at": str(row[6]) if row[6] else None,
                "order_at": str(row[7]),
                "reject_reason": row[8],
                "order_details": {
                    "customer_id": row[9],
                    "customer_name": customer_name,
                    "customer_mobile": row[11],
                    "total_amount": float(row[12]) if row[12] else 0,
                    "payment_mode": payment_mode,
                    "order_status": row[14],  # Keep as is (English)
                    "customer_order_status": row[15],  # Keep as is (English)
                    "customer_latitude": float(row[16]) if row[16] else None,
                    "customer_longitude": float(row[17]) if row[17] else None,
                    "otp": row[18],
                    "distance_from_vendor_km": None
                }
            }
            notifications.append(notification)

        return Response({
            "success": True,
            "message": f"{status_filter.capitalize()} orders fetched successfully",
            "total_orders": len(notifications),
            "data": notifications
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch order history",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])                            # # 
@active_user_required
@permission_classes([IsAuthenticated])
def vendor_accept_order(request):
    """
    POST: Accept an order by vendor
    - Uses stored procedure to atomically update notification and order details
    - Returns the updated order information
    """
    # ========== TOKEN AUTHENTICATION ==========
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    
    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')
    
    # Verify vendor role
    if str(vendor_role_id) != '3':
        return Response(
            {
                "success": False,
                "error": "Access denied. Only vendors can accept orders."
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    order_id = request.data.get('order_id')
    notification_id = request.data.get('notification_id')
    
    if not order_id or not notification_id:
        return Response(
            {
                "success": False,
                "error": "order_id and notification_id are required"
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from django.utils import timezone
        current_time = timezone.now()
        
        with connection.cursor() as cursor:
            # Call the stored procedure
            cursor.callproc('AcceptOrder', [vendor_id, order_id, notification_id, current_time])
            
            # Fetch the returned order details
            order_details = cursor.fetchone()
            if not order_details:
                return Response(
                    {
                        "success": False,
                        "error": "Failed to retrieve order details after acceptance"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Build response exactly as before
        return Response({
            "success": True,
            "message": "Order accepted successfully",
            "data": {
                "order_id": order_details[0],
                "customer_id": order_details[1],
                "customer_name": order_details[10],
                "customer_mobile": order_details[11],
                "total_amount": float(order_details[2]) if order_details[2] else 0,
                "payment_mode": order_details[3],
                "order_status": order_details[4],
                "customer_latitude": float(order_details[6]) if order_details[6] else None,
                "customer_longitude": float(order_details[7]) if order_details[7] else None,
                "otp": order_details[8],
                "confirm_at": str(order_details[9]) if order_details[9] else None,
                "accepted_by": vendor_id
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        # Catch any error raised by the stored procedure (e.g., via SIGNAL)
        return Response({
            "success": False,
            "error": "Failed to accept order",
            "details": str(e),
            # "trace": traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
    


@api_view(['POST'])                                   # # 
@active_user_required
def vendor_confirm_order(request):
    """
    POST: Confirm an order by verifying OTP
    - Requires order to be in 'accepted' state and assigned to this vendor
    - Verifies OTP, then sets order_status = 'inprocess' and confirm_at = NOW()
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')
    if str(vendor_role_id) != '3':
        return Response({"success": False, "error": "Only vendors can confirm orders."},
                        status=status.HTTP_403_FORBIDDEN)

    order_id = request.data.get('order_id')
    otp = request.data.get('otp')
    if not order_id or not otp:
        return Response({"success": False, "error": "order_id and otp are required"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        from django.utils import timezone
        current_time = timezone.now()

        with connection.cursor() as cursor:
            # Call the stored procedure
            cursor.callproc('ConfirmOrder', [vendor_id, order_id, otp, current_time])
            
            # Fetch the updated order details
            updated = cursor.fetchone()
            if not updated:
                return Response(
                    {"success": False, "error": "Failed to retrieve updated order details"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response({
            "success": True,
            "message": "Order confirmed and is now in process.",
            "data": {
                "order_id": updated[0],
                "order_status": updated[1],
                "confirm_at": str(updated[2])
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to confirm order",
            "details": str(e),
            # "trace": traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


 
@api_view(['POST'])                                          # # 
@active_user_required
@permission_classes([IsAuthenticated])
def vendor_reject_order(request):
    """
    POST: Reject an order by vendor
    - If order is accepted by this vendor: 
        * Order becomes available again (status = PENDING)
        * New notifications sent to all vendors
        * Original acceptance is recorded as rejection with reason
    - If order is pending: Simple rejection (only for this vendor)
    """
    from .auth import get_user_from_token
    from django.utils import timezone
    from .vendor_services import VendorService

    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')

    if str(vendor_role_id) != '3':
        return Response({"success": False, "error": "Access denied. Only vendors can reject orders."},
                        status=status.HTTP_403_FORBIDDEN)

    order_id = request.data.get('order_id')
    notification_id = request.data.get('notification_id')
    reject_reason = request.data.get('reject_reason')

    if not order_id or not notification_id:
        return Response({"success": False, "error": "order_id and notification_id are required"},
                        status=status.HTTP_400_BAD_REQUEST)

    if not reject_reason or reject_reason.strip() == '':
        return Response({"success": False, "error": "reject_reason is mandatory."},
                        status=status.HTTP_400_BAD_REQUEST)

    current_time = timezone.now()

    try:
        with connection.cursor() as cursor:
            # Call stored procedure
            cursor.callproc('RejectOrder', [
                vendor_id, order_id, notification_id, reject_reason, current_time,
                '', '', 0, 0, 0, 0, 0  # placeholders for OUT parameters
            ])

            # Retrieve OUT parameters (indices 6..12)
            cursor.execute("SELECT @_RejectOrder_6, @_RejectOrder_7, @_RejectOrder_8, @_RejectOrder_9, @_RejectOrder_10, @_RejectOrder_11, @_RejectOrder_12")
            out = cursor.fetchone()
            p_case = out[0]
            p_message = out[1]
            p_pending_count = out[2]
            p_customer_id = out[3]
            p_order_lat = out[4]
            p_order_lon = out[5]
            p_order_at = out[6]

        # Handle normal rejection
        if p_case == 'normal':
            message = f"Order rejected successfully. Order is still available for {p_pending_count} other vendor(s)."
            if p_pending_count == 0:
                message = "Order rejected successfully. No more vendors available for this order."

            return Response({
                "success": True,
                "message": message,
                "data": {
                    "order_id": order_id,
                    "notification_id": notification_id,
                    "rejected_by": vendor_id,
                    "rejected_at": str(current_time),
                    "reject_reason": reject_reason,
                    "action": "normal_rejection",
                    "order_status": "PENDING",
                    "pending_notifications": p_pending_count
                }
            }, status=status.HTTP_200_OK)

        # Handle reopened case (vendor had accepted and is now backing out)
        elif p_case == 'reopened':
            # Send fresh notifications to nearby vendors
            notification_result = VendorService.send_notification_to_vendors(
                order_id=order_id,
                user_id=p_customer_id,
                order_lat=float(p_order_lat) if p_order_lat else None,
                order_lon=float(p_order_lon) if p_order_lon else None,
                order_at=p_order_at or current_time
            )

            message = f"Order rejected after acceptance. Order has been reopened and notifications sent to {notification_result['total_vendors_notified']} vendors."

            return Response({
                "success": True,
                "message": message,
                "data": {
                    "order_id": order_id,
                    "notification_id": notification_id,
                    "rejected_by": vendor_id,
                    "rejected_at": str(current_time),
                    "reject_reason": reject_reason,
                    "action": "order_reopened",
                    "order_status": "PENDING",
                    "new_notifications_sent": notification_result['total_vendors_notified'],
                    "nearby_vendors": notification_result['nearby_vendors']
                }
            }, status=status.HTTP_200_OK)

        else:
            # Should not happen
            return Response({"success": False, "error": "Unexpected case from procedure"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        # Handle errors signaled by the procedure (e.g., order already accepted by another vendor)
        error_message = str(e)
        if "Order already accepted by another vendor" in error_message:
            # Try to extract the accepting vendor's name for a friendlier message
            import re
            match = re.search(r'ID: (\d+)', error_message)
            if match:
                other_vendor_id = match.group(1)
                with connection.cursor() as cur:
                    cur.execute("SELECT name FROM tbl_user WHERE user_id = %s", [other_vendor_id])
                    name_row = cur.fetchone()
                    vendor_name = name_row[0] if name_row else "Another vendor"
                return Response({
                    "success": False,
                    "error": "This order has already been accepted by another vendor",
                    "message": f"This order is no longer available as it has been accepted by {vendor_name}",
                    "order_status": "ACCEPTED",
                    "accepted_by": other_vendor_id,
                    "accepted_by_name": vendor_name
                }, status=status.HTTP_400_BAD_REQUEST)
        # Generic error response
        return Response({
            "success": False,
            "error": "Failed to reject order",
            "details": error_message,
            # "trace": traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['POST'])                               # # 
@active_user_required
def vendor_complete_order(request):
    """
    POST: Complete an order by vendor
    - Uses stored procedure CompleteOrder
    - Requires order status = 'inprocess' and customer_order_status = 'completed'
    - Vendor must be the one assigned to the order (accepted_by)
    - Updates order_status = 'completed', sets completed_by and completed_at
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response(
            {"success": False, "error": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')
    if str(vendor_role_id) != '3':
        return Response(
            {"success": False, "error": "Only vendors can complete orders."},
            status=status.HTTP_403_FORBIDDEN
        )

    order_id = request.data.get('order_id')
    if not order_id:
        return Response(
            {"success": False, "error": "order_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from django.utils import timezone
        current_time = timezone.now()

        with connection.cursor() as cursor:
            cursor.callproc('CompleteOrder', [vendor_id, order_id, current_time])
            result = cursor.fetchone()  # returns (order_id, completed_by, completed_at, order_status)

            if not result:
                return Response(
                    {"success": False, "error": "Failed to retrieve updated order"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response({
            "success": True,
            "message": "Order completed successfully",
            "data": {
                "order_id": result[0],
                "completed_by": result[1],
                "completed_at": str(result[2]),
                "order_status": result[3]
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to complete order",
            "details": str(e),
            # "trace": traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# # # code for english lang 

# @api_view(['GET'])                                      # # 
# @active_user_required
# @permission_classes([IsAuthenticated])
# def vendor_order_details(request, order_id):
#     """
#     GET: Get detailed information about a specific order including all services
#     """
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
#     if not token_user:
#         return Response(
#             {"success": False, "error": "Authentication required."},
#             status=status.HTTP_401_UNAUTHORIZED
#         )

#     vendor_id = token_user.get('user_id')
#     vendor_role_id = token_user.get('role_id')

#     if str(vendor_role_id) != '3':
#         return Response(
#             {"success": False, "error": "Access denied. Only vendors can view order details."},
#             status=status.HTTP_403_FORBIDDEN
#         )

#     try:
#         with connection.cursor() as cursor:
#             cursor.callproc('GetVendorOrderDetails', [vendor_id, order_id])
            
#             # First result set: order details
#             order_base = cursor.fetchone()
#             if not order_base:
#                 # This should not happen if procedure raised an error, but handle gracefully
#                 return Response(
#                     {"error": "Order not found"},
#                     status=status.HTTP_404_NOT_FOUND
#                 )
            
#             # Move to next result set
#             cursor.nextset()
            
#             # Second result set: services
#             services_rows = cursor.fetchall()
        
#         # Build services list
#         services = []
#         for r in services_rows:
#             services.append({
#                 'sale_id': r[0],
#                 'service_id': r[1],
#                 'quantity': r[2],
#                 'price': float(r[3]) if r[3] else 0,
#                 'service_datetime': str(r[4]),
#                 'order_at': str(r[5]),
#                 'main_service_name': r[6],
#                 'subservice_name': r[7],
#                 'sub_service_img': r[8]
#             })
        
#         response_data = {
#             'order_id': order_base[0],
#             'customer_id': order_base[1],
#             'customer_name': order_base[14],
#             'customer_mobile': order_base[15],
#             'total_amount': float(order_base[2]) if order_base[2] else 0,
#             'payment_mode': order_base[3],
#             'order_status': order_base[4],
#             'customer_order_status': order_base[5],
#             'customer_latitude': float(order_base[6]) if order_base[6] else None,
#             'customer_longitude': float(order_base[7]) if order_base[7] else None,
#             'otp': order_base[8],
#             'confirm_at': str(order_base[9]) if order_base[9] else None,
#             'cancel_at': str(order_base[10]) if order_base[10] else None,
#             'accepted_by': order_base[11],
#             'completed_by': order_base[12],
#             'completed_at': str(order_base[13]) if order_base[13] else None,
#             'services': services
#         }
        
#         return Response({"success": True, "data": response_data}, status=status.HTTP_200_OK)
        
#     except Exception as e:
#         error_message = str(e)
#         # Match specific error messages from the stored procedure
#         if "Vendor does not have access" in error_message:
#             return Response(
#                 {"success": False, "error": "You don't have access to this order"},
#                 status=status.HTTP_403_FORBIDDEN
#             )
#         elif "Order not found" in error_message:
#             return Response(
#                 {"error": "Order not found"},
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         else:
#             return Response({
#                 "success": False,
#                 "error": "Failed to fetch order details",
#                 "details": error_message,
#                 # "trace": traceback.format_exc()
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# # code for multilangauge 
@api_view(['GET'])
@active_user_required
@permission_classes([IsAuthenticated])
def vendor_order_details(request, order_id):
    """
    GET: Get detailed information about a specific order including all services
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response(
            {"success": False, "error": "Authentication required."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    vendor_id = token_user.get('user_id')
    vendor_role_id = token_user.get('role_id')

    if str(vendor_role_id) != '3':
        return Response(
            {"success": False, "error": "Access denied. Only vendors can view order details."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Get language parameter
    lang = request.query_params.get('lang', 'en')

    try:
        with connection.cursor() as cursor:
            cursor.callproc('GetVendorOrderDetails', [vendor_id, order_id])
            
            # First result set: order details
            order_base = cursor.fetchone()
            if not order_base:
                return Response(
                    {"error": "Order not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Translate customer name if needed
            customer_name = order_base[14]
            if lang != 'en' and customer_name:
                customer_name = transliterate_name(customer_name, lang)
            
            # Move to next result set
            cursor.nextset()
            
            # Second result set: services
            services_rows = cursor.fetchall()
        
        # Build services list with translations
        services = []
        for r in services_rows:
            main_service_name = r[6]
            subservice_name = r[7]
            
            if lang != 'en':
                if main_service_name:
                    main_service_name = translate_text(main_service_name, lang)
                if subservice_name:
                    subservice_name = translate_text(subservice_name, lang)
            
            services.append({
                'sale_id': r[0],
                'service_id': r[1],
                'quantity': r[2],
                'price': float(r[3]) if r[3] else 0,
                'service_datetime': str(r[4]),
                'order_at': str(r[5]),
                'main_service_name': main_service_name,
                'subservice_name': subservice_name,
                'sub_service_img': r[8]
            })
        
        response_data = {
            'order_id': order_base[0],
            'customer_id': order_base[1],
            'customer_name': customer_name,
            'customer_mobile': order_base[15],
            'total_amount': float(order_base[2]) if order_base[2] else 0,
            'payment_mode': order_base[3],
            'order_status': order_base[4],
            'customer_order_status': order_base[5],
            'customer_latitude': float(order_base[6]) if order_base[6] else None,
            'customer_longitude': float(order_base[7]) if order_base[7] else None,
            'otp': order_base[8],
            'confirm_at': str(order_base[9]) if order_base[9] else None,
            'cancel_at': str(order_base[10]) if order_base[10] else None,
            'accepted_by': order_base[11],
            'completed_by': order_base[12],
            'completed_at': str(order_base[13]) if order_base[13] else None,
            'services': services
        }
        
        return Response({"success": True, "data": response_data}, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_message = str(e)
        if "Vendor does not have access" in error_message:
            return Response(
                {"success": False, "error": "You don't have access to this order"},
                status=status.HTTP_403_FORBIDDEN
            )
        elif "Order not found" in error_message:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            return Response({
                "success": False,
                "error": "Failed to fetch order details",
                "details": error_message,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# # Admin 

@api_view(['GET'])                           # # working code - for all langauge 
@active_user_required
def user_detals(request):
    """
    GET: Get user details with statistics for admin.
    - If user_id is provided: returns detailed profile + all orders with services.
    - If user_id is NOT provided: returns aggregated counts and list of users.
    Supports filtering by search, active_status, date range, and language.
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    admin_id = token_user.get('user_id')
    admin_role = token_user.get('role_id')

    if str(admin_role) not in ['1', '2']:
        return Response({"success": False, "error": "Access denied. Admins only."},
                        status=status.HTTP_403_FORBIDDEN)

    # Get query parameters
    user_id = request.query_params.get('user_id')
    search = request.query_params.get('search')
    active_status = request.query_params.get('active_status')
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    lang = request.query_params.get('lang', 'en')

    try:
        with connection.cursor() as cursor:

            # ========== SINGLE USER DETAILS VIEW ==========
            if user_id:
                cursor.callproc('GetUserDetails', [user_id, from_date, to_date])
                user_row = cursor.fetchone()
                if not user_row:
                    return Response({"error": "User not found or not a regular user"},
                                    status=status.HTTP_404_NOT_FOUND)

                user_id_db, name, contact, active, total_orders, total_spend = user_row

                # Transliterate user name
                if lang != 'en':
                    name = transliterate_name(name, lang)

                cursor.nextset()
                orders_rows = cursor.fetchall()

                orders_dict = {}
                for r in orders_rows:
                    oid = r[0]
                    if oid not in orders_dict:
                        # Translate order-level text fields
                        payment_mode = r[2]
                        order_status = r[3]
                        customer_order_status = r[4]
                        accepted_by_name = r[22]
                        completed_by_name = r[23]

                        if lang != 'en':
                            if payment_mode:
                                payment_mode = translate_text(payment_mode, lang)
                            if order_status:
                                order_status = translate_text(order_status, lang)
                            if customer_order_status:
                                customer_order_status = translate_text(customer_order_status, lang)
                            if accepted_by_name:
                                accepted_by_name = transliterate_name(accepted_by_name, lang)
                            if completed_by_name:
                                completed_by_name = transliterate_name(completed_by_name, lang)

                        # Translate service names (indices 19 and 20)
                        main_name_orig = r[19]
                        sub_name_orig = r[20]
                        if lang != 'en':
                            translated_main = translate_text(main_name_orig, lang)
                            translated_sub = translate_text(sub_name_orig, lang)
                        else:
                            translated_main = main_name_orig
                            translated_sub = sub_name_orig

                        orders_dict[oid] = {
                            "order_id": oid,
                            "total_amount": float(r[1]) if r[1] else 0,
                            "payment_mode": payment_mode,
                            "order_status": order_status,
                            "customer_order_status": customer_order_status,
                            "customer_latitude": float(r[5]) if r[5] else None,
                            "customer_longitude": float(r[6]) if r[6] else None,
                            "otp": r[7],
                            "confirm_at": str(r[8]) if r[8] else None,
                            "cancel_at": str(r[9]) if r[9] else None,
                            "accepted_by": r[10],
                            "accepted_by_name": accepted_by_name,
                            "completed_by": r[11],
                            "completed_by_name": completed_by_name,
                            "completed_at": str(r[12]) if r[12] else None,
                            "order_at": str(r[13]),
                            "services": []
                        }
                    # Append service (translated names already computed)
                    orders_dict[oid]["services"].append({
                        "sale_id": r[14],
                        "service_id": r[15],
                        "quantity": r[16],
                        "price": float(r[17]) if r[17] else 0,
                        "service_datetime": str(r[18]),
                        "main_service_name": translated_main,
                        "subservice_name": translated_sub,
                        "sub_service_img": r[21]
                    })

                return Response({
                    "success": True,
                    "data": {
                        "user_id": user_id_db,
                        "name": name,
                        "contact_number": contact,
                        "active_status": active,
                        "total_booking_count": total_orders,
                        "total_spend_amount": float(total_spend),
                        "orders": list(orders_dict.values())
                    }
                }, status=status.HTTP_200_OK)

            # ========== AGGREGATED LIST VIEW ==========
            cursor.callproc('GetUserStats', [search, active_status, from_date, to_date])
            totals = cursor.fetchone()
            total_bookings = totals[0]
            total_active = totals[1]
            total_inactive = totals[2]
            total_users = total_active + total_inactive

            cursor.nextset()
            rows = cursor.fetchall()

            user_list = []
            for row in rows:
                user_name = row[1]
                last_order_status = row[8]
                last_payment_mode = row[12]
                last_completed_by_name = row[10]

                if lang != 'en':
                    user_name = transliterate_name(user_name, lang)
                    if last_order_status:
                        last_order_status = translate_text(last_order_status, lang)
                    if last_payment_mode:
                        last_payment_mode = translate_text(last_payment_mode, lang)
                    if last_completed_by_name:
                        last_completed_by_name = transliterate_name(last_completed_by_name, lang)

                user_list.append({
                    "user_id": row[0],
                    "name": user_name,
                    "contact_number": row[2],
                    "user_total_booking_count": row[3],
                    "user_total_spend_amount": float(row[4]),
                    "user_active_status": row[5],
                    "last_order_at": str(row[6]) if row[6] else None,
                    "last_confirm_at": str(row[7]) if row[7] else None,
                    "last_order_status": last_order_status,
                    "last_completed_by": row[9],
                    "last_completed_by_name": last_completed_by_name,
                    "last_completed_at": str(row[11]) if row[11] else None,
                    "last_payment_mode": last_payment_mode
                })

            return Response({
                "success": True,
                "data": {
                    "total_booking_count": total_bookings,
                    "total_active_user_count": total_active,
                    "total_blocked_user_count": total_inactive,
                    "total_users": total_users,
                    "user_data": user_list
                }
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch admin stats",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# @api_view(['GET'])                            # # workig code - with all langauge
# @active_user_required
# def vendor_details(request):
#     """
#     GET: Get vendor details with statistics for admin.
#     - If vendor_id is provided: returns detailed profile + orders.
#         Optional query param: order_status (accepted, completed, rejected, all) – default all.
#     - If vendor_id is NOT provided: returns aggregated counts and list of vendors.
#     Supports filtering by search, approval_status, active_status, date range, and language.
#     """
#     from .auth import get_user_from_token
#     token_user = get_user_from_token(request)
#     if not token_user:
#         return Response({"success": False, "error": "Authentication required."},
#                         status=status.HTTP_401_UNAUTHORIZED)

#     admin_role = token_user.get('role_id')
#     if str(admin_role) not in ['1', '2']:
#         return Response({"success": False, "error": "Access denied. Admins only."},
#                         status=status.HTTP_403_FORBIDDEN)

#     vendor_id = request.query_params.get('vendor_id')
#     search = request.query_params.get('search')
#     approval_status = request.query_params.get('approval_status')
#     active_status = request.query_params.get('active_status')
#     from_date = request.query_params.get('from_date')
#     to_date = request.query_params.get('to_date')
#     order_status = request.query_params.get('order_status', 'all')
#     lang = request.query_params.get('lang', 'en')

#     try:
#         with connection.cursor() as cursor:
#             # ========== SINGLE VENDOR DETAILS VIEW ==========
#             if vendor_id:
#                 order_status_filter = request.query_params.get('order_status')
#                 notification_filter = request.query_params.get('notification_filter', 'all')

#                 cursor.callproc('GetVendorDetails', [vendor_id, from_date, to_date, order_status_filter, notification_filter])

#                 # 1. Vendor profile
#                 vendor_row = cursor.fetchone()
#                 if not vendor_row:
#                     return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)

#                 (vendor_id_db, name, contact, aadhar, aadhar_img, stamp_img,
#                 approval, active, lat, lon, created_at,
#                 total_accepted, total_completed, total_earnings) = vendor_row

#                 # Transliterate vendor name
#                 if lang != 'en':
#                     name = transliterate_name(name, lang)

#                 # 2. Orders (now with feedback columns at indices 23-28)
#                 cursor.nextset()
#                 orders_rows = cursor.fetchall()
#                 orders = []
#                 current_order = None
#                 for r in orders_rows:
#                     oid = r[0]
#                     if current_order is None or current_order['order_id'] != oid:
#                         if current_order:
#                             orders.append(current_order)

#                         # Translate order-level fields
#                         payment_mode = r[5]
#                         order_status_val = r[6]
#                         customer_order_status_val = r[7]
#                         customer_name = r[2]

#                         if lang != 'en':
#                             if payment_mode:
#                                 payment_mode = translate_text(payment_mode, lang)
#                             if order_status_val:
#                                 order_status_val = translate_text(order_status_val, lang)
#                             if customer_order_status_val:
#                                 customer_order_status_val = translate_text(customer_order_status_val, lang)
#                             if customer_name:
#                                 customer_name = transliterate_name(customer_name, lang)

#                         # Translate service names (indices 20, 21)
#                         main_name_orig = r[20]
#                         sub_name_orig = r[21]
#                         if lang != 'en':
#                             translated_main = translate_text(main_name_orig, lang)
#                             translated_sub = translate_text(sub_name_orig, lang)
#                         else:
#                             translated_main = main_name_orig
#                             translated_sub = sub_name_orig

#                         # Translate feedback fields (if any)
#                         feedback = None
#                         if r[23] is not None:
#                             fb_type = r[23]
#                             fb_comment = r[24]
#                             fb_com_status = r[26]
#                             if lang != 'en':
#                                 if fb_type:
#                                     fb_type = translate_text(fb_type, lang)
#                                 if fb_comment:
#                                     fb_comment = translate_text(fb_comment, lang)
#                                 if fb_com_status:
#                                     fb_com_status = translate_text(fb_com_status, lang)
#                             feedback = {
#                                 "type": fb_type,
#                                 "comment": fb_comment,
#                                 "rating": float(r[25]) if r[25] is not None else None,
#                                 "com_status": fb_com_status,
#                                 "created_at": str(r[27]) if r[27] else None,
#                                 "updated_at": str(r[28]) if r[28] else None
#                             }

#                         current_order = {
#                             "order_id": oid,
#                             "customer_id": r[1],
#                             "customer_name": customer_name,
#                             "customer_mobile": r[3],
#                             "total_amount": float(r[4]) if r[4] else 0,
#                             "payment_mode": payment_mode,
#                             "order_status": order_status_val,
#                             "customer_order_status": customer_order_status_val,
#                             "customer_latitude": float(r[8]) if r[8] else None,
#                             "customer_longitude": float(r[9]) if r[9] else None,
#                             "otp": r[10],
#                             "confirm_at": str(r[11]) if r[11] else None,
#                             "cancel_at": str(r[12]) if r[12] else None,
#                             "completed_at": str(r[13]) if r[13] else None,
#                             "order_at": str(r[14]),
#                             "services": [],
#                             "feedback": feedback
#                         }
#                     # Append service (translated names already computed)
#                     current_order["services"].append({
#                         "sale_id": r[15],
#                         "service_id": r[16],
#                         "quantity": r[17],
#                         "price": float(r[18]) if r[18] else 0,
#                         "service_datetime": str(r[19]),
#                         "main_service_name": translated_main,
#                         "subservice_name": translated_sub,
#                         "sub_service_img": r[22]
#                     })
#                 if current_order:
#                     orders.append(current_order)

#                 # 3. Notification summary (numeric, no translation needed)
#                 cursor.nextset()
#                 notif_summary_row = cursor.fetchone()
#                 notification_summary = {
#                     "total_notifications": notif_summary_row[0],
#                     "accepted_count": float(notif_summary_row[1] or 0),
#                     "rejected_count": float(notif_summary_row[2] or 0),
#                     "pending_count": float(notif_summary_row[3] or 0)
#                 }

#                 # 4. Notification details – fetch and discard
#                 cursor.nextset()
#                 cursor.fetchall()

#                 return Response({
#                     "success": True,
#                     "data": {
#                         "vendor_id": vendor_id_db,
#                         "name": name,
#                         "contact_number": contact,
#                         "aadhar_number": aadhar,
#                         "aadhar_img": aadhar_img,
#                         "stamp_img": stamp_img,
#                         "approval_status": approval,      # not translated (code)
#                         "active_status": active,          # not translated (code)
#                         "latitude": float(lat) if lat else None,
#                         "longitude": float(lon) if lon else None,
#                         "created_at": str(created_at),
#                         "total_orders_accepted": total_accepted,
#                         "total_orders_completed": total_completed,
#                         "total_earnings": float(total_earnings),
#                         "orders": orders,
#                         "notification_summary": notification_summary
#                     }
#                 }, status=status.HTTP_200_OK)

#             # ========== AGGREGATED LIST VIEW ==========
#             cursor.callproc('GetVendorStats', [search, approval_status, active_status, from_date, to_date])
#             totals = cursor.fetchone()
#             total_vendors = totals[0]
#             total_active = totals[1]
#             total_inactive = totals[2]
#             total_pending = totals[3]

#             cursor.nextset()
#             rows = cursor.fetchall()

#             vendor_list = []
#             for row in rows:
#                 vendor_name = row[1]
#                 last_order_status = row[10]
#                 last_customer_name = row[12]

#                 if lang != 'en':
#                     vendor_name = transliterate_name(vendor_name, lang)
#                     if last_order_status:
#                         last_order_status = translate_text(last_order_status, lang)
#                     if last_customer_name:
#                         last_customer_name = transliterate_name(last_customer_name, lang)

#                 vendor_list.append({
#                     "vendor_id": row[0],
#                     "name": vendor_name,
#                     "contact_number": row[2],
#                     "approval_status": row[3],
#                     "active_status": row[4],
#                     "total_orders_accepted": row[5],
#                     "total_orders_completed": row[6],
#                     "total_earnings": float(row[7]),
#                     "last_order_at": str(row[8]) if row[8] else None,
#                     "last_confirm_at": str(row[9]) if row[9] else None,
#                     "last_order_status": last_order_status,
#                     "last_customer_id": row[11],
#                     "last_customer_name": last_customer_name
#                 })

#             return Response({
#                 "success": True,
#                 "data": {
#                     "total_vendors_count": total_vendors,
#                     "total_active_vendors": total_active,
#                     "total_inactive_vendors": total_inactive,
#                     "total_pending_approval_vendors": total_pending,
#                     "vendor_data": vendor_list
#                 }
#             }, status=status.HTTP_200_OK)

#     except Exception as e:
#         return Response({
#             "success": False,
#             "error": "Failed to fetch vendor stats",
#             "details": str(e),
#         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@active_user_required
def vendor_details(request):
    """
    GET: Get vendor details with statistics for admin.
    - If vendor_id is provided: returns detailed profile + orders.
        Optional query param: order_status (accepted, completed, rejected, all) – default all.
    - If vendor_id is NOT provided: returns aggregated counts and list of vendors.
    Supports filtering by search, approval_status, active_status, date range, and language.
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    admin_role = token_user.get('role_id')
    if str(admin_role) not in ['1', '2']:
        return Response({"success": False, "error": "Access denied. Admins only."},
                        status=status.HTTP_403_FORBIDDEN)

    vendor_id = request.query_params.get('vendor_id')
    search = request.query_params.get('search')
    approval_status = request.query_params.get('approval_status')
    active_status = request.query_params.get('active_status')
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    order_status = request.query_params.get('order_status', 'all')
    lang = request.query_params.get('lang', 'en')

    try:
        with connection.cursor() as cursor:
            # ========== SINGLE VENDOR DETAILS VIEW ==========
            if vendor_id:
                order_status_filter = request.query_params.get('order_status')
                notification_filter = request.query_params.get('notification_filter', 'all')

                cursor.callproc('GetVendorDetails', [vendor_id, from_date, to_date, order_status_filter, notification_filter])

                # 1. Vendor profile - dynamically handle columns
                vendor_row = cursor.fetchone()
                if not vendor_row:
                    return Response({"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)

                # Get basic info from first few columns (always present)
                vendor_id_db = vendor_row[0]
                name = vendor_row[1]
                contact = vendor_row[2]
                aadhar = vendor_row[3]
                aadhar_img = vendor_row[4]
                stamp_img = vendor_row[5]
                
                # Get additional fields from a separate query (safe approach)
                cursor.execute("""
                    SELECT 
                        certificate, 
                        decline_reason, 
                        is_approved, 
                        active_status, 
                        user_lat, 
                        user_long, 
                        created_at,
                        COALESCE((
                            SELECT COUNT(DISTINCT order_id) 
                            FROM tbl_sales_details 
                            WHERE accepted_by = %s
                        ), 0) AS total_orders_accepted,
                        COALESCE((
                            SELECT COUNT(DISTINCT order_id) 
                            FROM tbl_sales_details 
                            WHERE accepted_by = %s AND order_status = 'completed'
                        ), 0) AS total_orders_completed,
                        COALESCE((
                            SELECT SUM(total_amount) 
                            FROM tbl_sales_details 
                            WHERE accepted_by = %s AND order_status = 'completed'
                        ), 0) AS total_earnings
                    FROM tbl_user 
                    WHERE user_id = %s
                """, [vendor_id_db, vendor_id_db, vendor_id_db, vendor_id_db])
                
                vendor_info = cursor.fetchone()
                
                certificate = vendor_info[0] if vendor_info else None
                decline_reason = vendor_info[1] if vendor_info else None
                approval = vendor_info[2] if vendor_info else None
                active = vendor_info[3] if vendor_info else None
                lat = vendor_info[4] if vendor_info else None
                lon = vendor_info[5] if vendor_info else None
                created_at = vendor_info[6] if vendor_info else None
                total_accepted = vendor_info[7] if vendor_info else 0
                total_completed = vendor_info[8] if vendor_info else 0
                total_earnings = vendor_info[9] if vendor_info else 0

                # Transliterate vendor name
                if lang != 'en' and name:
                    name = transliterate_name(name, lang)
                
                # Translate decline reason if needed
                decline_reason_translated = decline_reason
                if lang != 'en' and decline_reason:
                    decline_reason_translated = translate_text(decline_reason, lang)

                # 2. Orders
                cursor.nextset()
                orders_rows = cursor.fetchall()
                orders = []
                current_order = None
                
                for r in orders_rows:
                    oid = r[0]
                    if current_order is None or current_order['order_id'] != oid:
                        if current_order:
                            orders.append(current_order)

                        # Translate order-level fields
                        payment_mode = r[5] if len(r) > 5 else None
                        order_status_val = r[6] if len(r) > 6 else None
                        customer_order_status_val = r[7] if len(r) > 7 else None
                        customer_name = r[2] if len(r) > 2 else None

                        if lang != 'en':
                            if payment_mode:
                                payment_mode = translate_text(payment_mode, lang)
                            if order_status_val:
                                order_status_val = translate_text(order_status_val, lang)
                            if customer_order_status_val:
                                customer_order_status_val = translate_text(customer_order_status_val, lang)
                            if customer_name:
                                customer_name = transliterate_name(customer_name, lang)

                        # Translate service names
                        main_name_orig = r[20] if len(r) > 20 else None
                        sub_name_orig = r[21] if len(r) > 21 else None
                        if lang != 'en':
                            translated_main = translate_text(main_name_orig, lang) if main_name_orig else None
                            translated_sub = translate_text(sub_name_orig, lang) if sub_name_orig else None
                        else:
                            translated_main = main_name_orig
                            translated_sub = sub_name_orig

                        # Translate feedback fields (if any)
                        feedback = None
                        if len(r) > 23 and r[23] is not None:
                            fb_type = r[23]
                            fb_comment = r[24] if len(r) > 24 else None
                            fb_com_status = r[26] if len(r) > 26 else None
                            if lang != 'en':
                                if fb_type:
                                    fb_type = translate_text(fb_type, lang)
                                if fb_comment:
                                    fb_comment = translate_text(fb_comment, lang)
                                if fb_com_status:
                                    fb_com_status = translate_text(fb_com_status, lang)
                            feedback = {
                                "type": fb_type,
                                "comment": fb_comment,
                                "rating": float(r[25]) if len(r) > 25 and r[25] is not None else None,
                                "com_status": fb_com_status,
                                "created_at": str(r[27]) if len(r) > 27 and r[27] else None,
                                "updated_at": str(r[28]) if len(r) > 28 and r[28] else None
                            }

                        current_order = {
                            "order_id": oid,
                            "customer_id": r[1] if len(r) > 1 else None,
                            "customer_name": customer_name,
                            "customer_mobile": r[3] if len(r) > 3 else None,
                            "total_amount": float(r[4]) if len(r) > 4 and r[4] else 0,
                            "payment_mode": payment_mode,
                            "order_status": order_status_val,
                            "customer_order_status": customer_order_status_val,
                            "customer_latitude": float(r[8]) if len(r) > 8 and r[8] else None,
                            "customer_longitude": float(r[9]) if len(r) > 9 and r[9] else None,
                            "otp": r[10] if len(r) > 10 else None,
                            "confirm_at": str(r[11]) if len(r) > 11 and r[11] else None,
                            "cancel_at": str(r[12]) if len(r) > 12 and r[12] else None,
                            "completed_at": str(r[13]) if len(r) > 13 and r[13] else None,
                            "order_at": str(r[14]) if len(r) > 14 and r[14] else None,
                            "services": [],
                            "feedback": feedback
                        }
                    
                    # Append service
                    if len(r) > 15:
                        current_order["services"].append({
                            "sale_id": r[15],
                            "service_id": r[16],
                            "quantity": r[17],
                            "price": float(r[18]) if r[18] else 0,
                            "service_datetime": str(r[19]) if r[19] else None,
                            "main_service_name": translated_main,
                            "subservice_name": translated_sub,
                            "sub_service_img": r[22] if len(r) > 22 else None
                        })
                
                if current_order:
                    orders.append(current_order)

                # 3. Notification summary
                cursor.nextset()
                notif_summary_row = cursor.fetchone()
                notification_summary = {
                    "total_notifications": notif_summary_row[0] if notif_summary_row else 0,
                    "accepted_count": float(notif_summary_row[1] or 0) if notif_summary_row and len(notif_summary_row) > 1 else 0,
                    "rejected_count": float(notif_summary_row[2] or 0) if notif_summary_row and len(notif_summary_row) > 2 else 0,
                    "pending_count": float(notif_summary_row[3] or 0) if notif_summary_row and len(notif_summary_row) > 3 else 0
                }

                # 4. Notification details – fetch and discard
                cursor.nextset()
                cursor.fetchall()

                return Response({
                    "success": True,
                    "data": {
                        "vendor_id": vendor_id_db,
                        "name": name,
                        "contact_number": contact,
                        "aadhar_number": aadhar,
                        "aadhar_img": aadhar_img,
                        "stamp_img": stamp_img,
                        "certificate": certificate,
                        "decline_reason": decline_reason,
                        "decline_reason_translated": decline_reason_translated,
                        "approval_status": approval,
                        "active_status": active,
                        "latitude": float(lat) if lat else None,
                        "longitude": float(lon) if lon else None,
                        "created_at": str(created_at) if created_at else None,
                        "total_orders_accepted": total_accepted or 0,
                        "total_orders_completed": total_completed or 0,
                        "total_earnings": float(total_earnings) if total_earnings else 0,
                        "orders": orders,
                        "notification_summary": notification_summary
                    }
                }, status=status.HTTP_200_OK)

            # ========== AGGREGATED LIST VIEW ==========
            cursor.callproc('GetVendorStats', [search, approval_status, active_status, from_date, to_date])
            totals = cursor.fetchone()
            total_vendors = totals[0] if totals else 0
            total_active = totals[1] if totals and len(totals) > 1 else 0
            total_inactive = totals[2] if totals and len(totals) > 2 else 0
            total_pending = totals[3] if totals and len(totals) > 3 else 0

            cursor.nextset()
            rows = cursor.fetchall()

            vendor_list = []
            for row in rows:
                vendor_name = row[1] if len(row) > 1 else None
                last_order_status = row[10] if len(row) > 10 else None
                last_customer_name = row[12] if len(row) > 12 else None

                # Fetch certificate and decline_reason for each vendor
                cursor.execute("""
                    SELECT certificate, decline_reason 
                    FROM tbl_user 
                    WHERE user_id = %s
                """, [row[0]])
                additional = cursor.fetchone()
                certificate = additional[0] if additional else None
                decline_reason = additional[1] if additional else None

                if lang != 'en':
                    if vendor_name:
                        vendor_name = transliterate_name(vendor_name, lang)
                    if last_order_status:
                        last_order_status = translate_text(last_order_status, lang)
                    if last_customer_name:
                        last_customer_name = transliterate_name(last_customer_name, lang)

                vendor_list.append({
                    "vendor_id": row[0],
                    "name": vendor_name,
                    "contact_number": row[2] if len(row) > 2 else None,
                    "approval_status": row[3] if len(row) > 3 else None,
                    "active_status": row[4] if len(row) > 4 else None,
                    "total_orders_accepted": row[5] if len(row) > 5 else 0,
                    "total_orders_completed": row[6] if len(row) > 6 else 0,
                    "total_earnings": float(row[7]) if len(row) > 7 and row[7] else 0,
                    "last_order_at": str(row[8]) if len(row) > 8 and row[8] else None,
                    "last_confirm_at": str(row[9]) if len(row) > 9 and row[9] else None,
                    "last_order_status": last_order_status,
                    "last_customer_id": row[11] if len(row) > 11 else None,
                    "last_customer_name": last_customer_name,
                    "certificate": certificate,
                    "decline_reason": decline_reason
                })

            return Response({
                "success": True,
                "data": {
                    "total_vendors_count": total_vendors,
                    "total_active_vendors": total_active,
                    "total_inactive_vendors": total_inactive,
                    "total_pending_approval_vendors": total_pending,
                    "vendor_data": vendor_list
                }
            }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return Response({
            "success": False,
            "error": "Failed to fetch vendor stats",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])                       # # workig code - with all langauge
@active_user_required
def order_details(request):
    """
    GET: Get order details with statistics for admin.
    - If order_id is provided: returns full details of that order.
    - If order_id is NOT provided: returns aggregated stats and list of orders.
    Supports filtering by date range, order_status, payment_mode, customer_order_status,
    total_amount range, search (order_id or customer name), and language.
    """
    from .auth import get_user_from_token
    from rest_framework import status
    from .translation_service import translate_text, transliterate_name

    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    admin_role = token_user.get('role_id')
    if str(admin_role) not in ['1', '2']:
        return Response({"success": False, "error": "Access denied. Admins only."},
                        status=status.HTTP_403_FORBIDDEN)

    order_id = request.query_params.get('order_id')
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    order_status = request.query_params.get('order_status')
    payment_mode = request.query_params.get('payment_mode')
    customer_status = request.query_params.get('customer_status')
    min_amount = request.query_params.get('min_amount')
    max_amount = request.query_params.get('max_amount')
    search = request.query_params.get('search')
    lang = request.query_params.get('lang', 'en')

    try:
        with connection.cursor() as cursor:

            # ========== SINGLE ORDER DETAILS VIEW ==========
            if order_id:
                cursor.callproc('GetOrderDetails', [order_id])
                header = cursor.fetchone()
                if not header:
                    return Response({"error": "Order not found"},
                                    status=status.HTTP_404_NOT_FOUND)

                # Transliterate names
                customer_name = header[15]
                vendor_name = header[13]
                completed_by_name = header[14]
                if lang != 'en':
                    customer_name = transliterate_name(customer_name, lang)
                    vendor_name = transliterate_name(vendor_name, lang)
                    completed_by_name = transliterate_name(completed_by_name, lang)

                # Translate other textual fields
                payment_mode_val = header[3]
                order_status_val = header[4]
                customer_order_status_val = header[5]
                if lang != 'en':
                    if payment_mode_val:
                        payment_mode_val = translate_text(payment_mode_val, lang)
                    if order_status_val:
                        order_status_val = translate_text(order_status_val, lang)
                    if customer_order_status_val:
                        customer_order_status_val = translate_text(customer_order_status_val, lang)

                # Feedback translation
                feedback = None
                if header[19] is not None:
                    fb_type = header[19]
                    fb_comment = header[20]
                    fb_com_status = header[22]
                    if lang != 'en':
                        if fb_type:
                            fb_type = translate_text(fb_type, lang)
                        if fb_comment:
                            fb_comment = translate_text(fb_comment, lang)
                        if fb_com_status:
                            fb_com_status = translate_text(fb_com_status, lang)
                    feedback = {
                        "type": fb_type,
                        "comment": fb_comment,
                        "rating": float(header[21]) if header[21] is not None else None,
                        "com_status": fb_com_status,
                        "created_at": str(header[23]) if header[23] else None,
                        "updated_at": str(header[24]) if header[24] else None
                    }

                order_data = {
                    "order_id": header[0],
                    "customer_id": header[1],
                    "customer_name": customer_name,
                    "customer_mobile": header[16],
                    "vendor_id": header[11],
                    "vendor_name": vendor_name,
                    "completed_by_id": header[12],
                    "completed_by_name": completed_by_name,
                    "total_amount": float(header[2]) if header[2] else 0,
                    "payment_mode": payment_mode_val,
                    "order_status": order_status_val,
                    "customer_order_status": customer_order_status_val,
                    "customer_latitude": float(header[6]) if header[6] else None,
                    "customer_longitude": float(header[7]) if header[7] else None,
                    "otp": header[8],
                    "confirm_at": str(header[9]) if header[9] else None,
                    "cancel_at": str(header[10]) if header[10] else None,
                    "completed_at": str(header[17]) if header[17] else None,
                    "order_at": str(header[18]),
                    "services": [],
                    "feedback": feedback
                }

                cursor.nextset()
                services_rows = cursor.fetchall()
                for s in services_rows:
                    # Translate service names
                    main_name_orig = s[8]
                    sub_name_orig = s[9]
                    if lang != 'en':
                        main_service_name = translate_text(main_name_orig, lang)
                        subservice_name = translate_text(sub_name_orig, lang)
                    else:
                        main_service_name = main_name_orig
                        subservice_name = sub_name_orig

                    order_data["services"].append({
                        "sale_id": s[0],
                        "service_id": s[1],
                        "quantity": s[2],
                        "price": float(s[3]) if s[3] else 0,
                        "service_datetime": str(s[4]),
                        "main_service_name": main_service_name,
                        "subservice_name": subservice_name,
                        "sub_service_img": s[5]
                    })

                return Response({
                    "success": True,
                    "data": order_data
                }, status=status.HTTP_200_OK)

            # ========== AGGREGATED LIST VIEW ==========
            cursor.callproc('GetOrderStats', [
                from_date, to_date, order_status, payment_mode, search,
                customer_status, min_amount, max_amount
            ])
            totals = cursor.fetchone()
            total_orders = totals[0]
            total_revenue = totals[1]
            pending = totals[2]
            accepted = totals[3]
            inprocess = totals[4]
            completed = totals[5]
            cancelled = totals[6]

            cursor.nextset()
            rows = cursor.fetchall()

            order_list = []
            for row in rows:
                # Translate names
                customer_name = row[2]
                vendor_name = row[5]
                if lang != 'en':
                    customer_name = transliterate_name(customer_name, lang)
                    vendor_name = transliterate_name(vendor_name, lang)

                # Translate statuses and payment mode
                payment_mode_val = row[7]
                order_status_val = row[8]
                customer_order_status_val = row[9]
                if lang != 'en':
                    if payment_mode_val:
                        payment_mode_val = translate_text(payment_mode_val, lang)
                    if order_status_val:
                        order_status_val = translate_text(order_status_val, lang)
                    if customer_order_status_val:
                        customer_order_status_val = translate_text(customer_order_status_val, lang)

                # Feedback translation
                feedback = None
                if row[13] is not None:
                    fb_type = row[13]
                    fb_comment = row[14]
                    fb_com_status = row[16]
                    if lang != 'en':
                        if fb_type:
                            fb_type = translate_text(fb_type, lang)
                        if fb_comment:
                            fb_comment = translate_text(fb_comment, lang)
                        if fb_com_status:
                            fb_com_status = translate_text(fb_com_status, lang)
                    feedback = {
                        "type": fb_type,
                        "comment": fb_comment,
                        "rating": float(row[15]) if row[15] is not None else None,
                        "com_status": fb_com_status,
                        "created_at": str(row[17]) if row[17] else None,
                        "updated_at": str(row[18]) if row[18] else None
                    }

                order_list.append({
                    "order_id": row[0],
                    "customer_id": row[1],
                    "customer_name": customer_name,
                    "customer_mobile": row[3],
                    "vendor_id": row[4],
                    "vendor_name": vendor_name,
                    "total_amount": float(row[6]) if row[6] else 0,
                    "payment_mode": payment_mode_val,
                    "order_status": order_status_val,
                    "customer_order_status": customer_order_status_val,
                    "order_at": str(row[10]),
                    "confirm_at": str(row[11]) if row[11] else None,
                    "completed_at": str(row[12]) if row[12] else None,
                    "feedback": feedback
                })

            return Response({
                "success": True,
                "data": {
                    "total_orders": total_orders,
                    "total_revenue": float(total_revenue),
                    "pending_orders": pending,
                    "accepted_orders": accepted,
                    "inprocess_orders": inprocess,
                    "completed_orders": completed,
                    "cancelled_orders": cancelled,
                    "order_data": order_list
                }
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch order stats",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


# # cart

@api_view(['POST'])
@active_user_required
def cart_add(request):
    """
    POST: Add or update a service in the user's cart.
    - If quantity > 0: adds/updates the item.
    - If quantity = 0: removes the item from cart.
    Body: { "service_id": int, "quantity": int }
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    user_id = token_user.get('user_id')
    service_id = request.data.get('service_id')
    quantity = request.data.get('quantity')

    if service_id is None or quantity is None:
        return Response({"error": "service_id and quantity are required"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        quantity = int(quantity)
        if quantity < 0:
            return Response({"error": "quantity must be zero or positive"},
                            status=status.HTTP_400_BAD_REQUEST)
    except ValueError:
        return Response({"error": "quantity must be an integer"},
                        status=status.HTTP_400_BAD_REQUEST)

    # If quantity is zero, we don't need to fetch price
    price = None
    if quantity > 0:
        with connection.cursor() as cursor:
            cursor.execute("SELECT ss.price FROM tbl_service ts INNER JOIN tbl_subservice ss ON ts.subservice_id = ss.subservice_id WHERE ts.service_id = %s", [service_id])
            row = cursor.fetchone()
            if not row:
                return Response({"error": "Invalid service_id"}, status=status.HTTP_400_BAD_REQUEST)
            unit_price = row[0]
            total_price = unit_price * quantity
    else:
        total_price = None

    with connection.cursor() as cursor:
        cursor.callproc('AddToCart', [user_id, service_id, quantity, total_price])

    if quantity == 0:
        return Response({"success": True, "message": "Item removed from cart"}, status=status.HTTP_200_OK)
    else:
        return Response({"success": True, "message": "Item added to cart"}, status=status.HTTP_200_OK) 

@api_view(['GET'])
@active_user_required
def cart_view(request):
    """
    GET: List all items in the user's cart.
    - price field now holds the line total (unit_price * quantity).
    - total_amount is the sum of all line totals.
    Optional query param: lang (default 'en')
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    user_id = token_user.get('user_id')
    lang = request.query_params.get('lang', 'en')

    with connection.cursor() as cursor:
        cursor.callproc('GetCart', [user_id])
        rows = cursor.fetchall()

    items = []
    for r in rows:
        # Original English names from DB
        service_name_orig = r[6]   # service_name
        main_name_orig = r[9]       # main_service_name

        if lang != 'en':
            translated_service = translate_text(service_name_orig, lang)
            translated_main = translate_text(main_name_orig, lang)
        else:
            translated_service = service_name_orig
            translated_main = main_name_orig

        items.append({
            "cart_id": r[0],
            "service_id": r[1],
            "quantity": r[2],
            "price": float(r[3]),          # this is now the line total
            "added_at": str(r[4]),
            "updated_at": str(r[5]),
            "service_name": translated_service,
            "sub_service_img": r[7],
            "main_service_id": r[8],
            "main_service_name": translated_main
        })

    # Total is sum of line totals (price column)
    total = sum(item['price'] for item in items)

    return Response({
        "success": True,
        "data": {
            "items": items,
            "total_amount": total,
            "item_count": len(items)
        }
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@active_user_required
def cart_remove(request):
    """
    DELETE: Remove a service from cart.
    Query param: service_id
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    user_id = token_user.get('user_id')
    service_id = request.query_params.get('service_id')

    if not service_id:
        return Response({"error": "service_id query param required"},
                        status=status.HTTP_400_BAD_REQUEST)

    with connection.cursor() as cursor:
        cursor.callproc('RemoveFromCart', [user_id, service_id])

    return Response({"success": True, "message": "Item removed from cart"}, status=status.HTTP_200_OK)


@api_view(['POST'])
@active_user_required
def cart_checkout(request):
    """
    POST: Convert current cart into a real order.
    Body (either):
        - { "service_datetime": "...", "text": "address" }  # converts address to lat/lon
        - { "service_datetime": "...", "lat": xx, "long": yy }  # direct coordinates
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    user_id = token_user.get('user_id')
    service_datetime = request.data.get('service_datetime')
    address_text = request.data.get('text')
    lat = request.data.get('lat')
    lon = request.data.get('long')

    # Validation: either text OR (lat and long) must be provided
    if not service_datetime:
        return Response({"error": "service_datetime required"},
                        status=status.HTTP_400_BAD_REQUEST)

    if not address_text and (lat is None or lon is None):
        return Response({"error": "Either 'text' (address) or both 'lat' and 'long' are required"},
                        status=status.HTTP_400_BAD_REQUEST)

    # Get cart items
    with connection.cursor() as cursor:
        cursor.execute("SELECT service_id, quantity FROM tbl_cart WHERE user_id = %s", [user_id])
        cart_items = cursor.fetchall()

    if not cart_items:
        return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

    service_ids = [item[0] for item in cart_items]
    quantities = [item[1] for item in cart_items]

    # Determine coordinates
    if address_text:
        lat, lon = get_lat_long_from_address(address_text)
        if not lat or not lon:
            return Response({"error": "Invalid address"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        # Direct coordinates are already in lat, lon variables
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return Response({"error": "Invalid latitude or longitude"}, status=status.HTTP_400_BAD_REQUEST)

    import random
    from datetime import datetime
    otp = random.randint(1000, 9999)
    s_datetime = datetime.strptime(service_datetime, "%Y-%m-%d %H:%M:%S")
    order_time = datetime.now()

    import json
    service_ids_json = json.dumps(service_ids)
    quantities_json = json.dumps(quantities)

    with connection.cursor() as cursor:
        cursor.execute("CALL CreateOrder(%s, %s, %s, %s, %s, %s, %s, %s, @order_id, @total_amount)",
                       [user_id, service_ids_json, quantities_json, s_datetime, lat, lon, otp, order_time])
        cursor.execute("SELECT @order_id, @total_amount")
        result = cursor.fetchone()
        order_id = result[0]
        total_amount = result[1]

        # Clear cart
        cursor.callproc('ClearCart', [user_id])

    # Send notifications to vendors
    try:
        from .vendor_services import VendorService
        notification_result = VendorService.send_notification_to_vendors(
            order_id=order_id,
            user_id=user_id,
            order_lat=lat,
            order_lon=lon,
            order_at=order_time
        )
        notification_info = {
            "vendors_notified": notification_result['total_vendors_notified'],
            "nearby_vendors": notification_result.get('nearby_vendors', [])
        }
        if notification_info['vendors_notified'] == 0:
            notification_info['message'] = "No vendors available in your area at the moment."
    except Exception as e:
        print(f"Error sending vendor notifications: {str(e)}")
        notification_info = {
            "vendors_notified": 0,
            "nearby_vendors": [],
            "error": "Failed to send notifications",
            "message": "Unable to notify vendors. Please try again later."
        }

    return Response({
        "success": True,
        "message": "Order created successfully",
        "data": {
            "order_id": order_id,
            "user_id": user_id,
            "latitude": lat,
            "longitude": lon,
            "otp": otp,
            "total_amount": total_amount,
            "customer_order_status": "pending",
            "order_status": "PENDING",
            "order_at": str(order_time),
            "notification": notification_info
        }
    }, status=status.HTTP_201_CREATED)





@api_view(['GET'])                                # # workig code - with all langauge
@active_user_required
def admin_dashboard(request):
    """
    GET: Returns dashboard statistics for admin.
    - Overall counts: bookings, revenue, users, vendors, pending vendors, cancelled orders,
      completed orders, pending orders, total main services, total subservices.
    - Year-wise revenue
    - Month-wise revenue
    - Top 5 most booked services (with names translated based on lang param, and price)
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    admin_role = token_user.get('role_id')
    if str(admin_role) not in ['1', '2']:
        return Response({"success": False, "error": "Access denied. Admins only."},
                        status=status.HTTP_403_FORBIDDEN)

    lang = request.query_params.get('lang', 'en')

    try:
        with connection.cursor() as cursor:
            cursor.callproc('GetDashboardStats')
            # First result set: overall counts (10 columns)
            totals = cursor.fetchone()
            overall = {
                "total_bookings": totals[0],
                "total_revenue": float(totals[1]),
                "total_users": totals[2],
                "total_vendors": totals[3],
                "pending_approval_vendors": totals[4],
                "total_cancelled_orders": totals[5],
                "completed_orders": totals[6],
                "pending_orders": totals[7],
                "total_main_services": totals[8],
                "total_subservices": totals[9]
            }

            # Move to next result set
            cursor.nextset()
            # Second result set: year-wise revenue
            year_rows = cursor.fetchall()
            year_wise = [{"year": r[0], "revenue": float(r[1])} for r in year_rows]

            # Move to next result set
            cursor.nextset()
            # Third result set: month-wise revenue
            month_rows = cursor.fetchall()
            month_wise = [{"year": r[0], "month": r[1], "revenue": float(r[2])} for r in month_rows]

            # Move to next result set
            cursor.nextset()
            # Fourth result set: top 5 services (with price)
            top_services_rows = cursor.fetchall()
            top_services = []
            for r in top_services_rows:
                service_id = r[0]
                service_name_en = r[1]
                main_service_name_en = r[2]
                price = float(r[3])
                booking_count = r[4]

                if lang != 'en':
                    service_name = translate_text(service_name_en, lang)
                    main_service_name = translate_text(main_service_name_en, lang)
                else:
                    service_name = service_name_en
                    main_service_name = main_service_name_en

                top_services.append({
                    "service_id": service_id,
                    "service_name": service_name,
                    "main_service_name": main_service_name,
                    "price": price,
                    "booking_count": booking_count
                })

        return Response({
            "success": True,
            "data": {
                "overall": overall,
                "year_wise_revenue": year_wise,
                "month_wise_revenue": month_wise,
                "top_services": top_services
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch dashboard stats",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# # order notification

@api_view(['GET'])                               # # workig code - with all langauge
@active_user_required
def vendor_notification_report(request):
    """
    GET: Returns notification report for vendors (admin only).
    Optional filters:
        - vendor_id (int) – get report for a specific vendor
        - from_date (YYYY-MM-DD)
        - to_date (YYYY-MM-DD)
        - notification_filter (string) – 'accepted', 'rejected', 'pending', 'completed', or 'all' (default)
    Returns summary per vendor and detailed notification list.
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    admin_role = token_user.get('role_id')
    if str(admin_role) not in ['1', '2']:
        return Response({"success": False, "error": "Access denied. Admins only."},
                        status=status.HTTP_403_FORBIDDEN)

    vendor_id = request.query_params.get('vendor_id')
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    notification_filter = request.query_params.get('notification_filter', 'all')
    valid_filters = ['accepted', 'rejected', 'pending', 'completed', 'all']
    if notification_filter not in valid_filters:
        notification_filter = 'all'
    lang = request.query_params.get('lang', 'en')

    try:
        with connection.cursor() as cursor:
            cursor.callproc('GetVendorNotificationReport', [vendor_id, from_date, to_date, notification_filter])
            # First result set: summary per vendor
            summary_rows = cursor.fetchall()
            summary = []
            for row in summary_rows:
                vendor_name = row[1]
                if lang != 'en':
                    vendor_name = transliterate_name(vendor_name, lang)
                summary.append({
                    "vendor_id": row[0],
                    "vendor_name": vendor_name,
                    "vendor_mobile": row[2],
                    "total_notifications": row[3],
                    "total_accepted": row[4],
                    "total_rejected": row[5],
                    "total_pending": row[6]
                })

            # Move to next result set
            cursor.nextset()
            # Second result set: detailed list
            detail_rows = cursor.fetchall()
            details = []
            for r in detail_rows:
                # Fields to translate/transliterate
                vendor_name = r[3]
                customer_name = r[11]
                payment_mode = r[13]
                order_status = r[14]
                customer_order_status = r[15]
                reject_reason = r[9]

                if lang != 'en':
                    if vendor_name:
                        vendor_name = transliterate_name(vendor_name, lang)
                    if customer_name:
                        customer_name = transliterate_name(customer_name, lang)
                    if payment_mode:
                        payment_mode = translate_text(payment_mode, lang)
                    if order_status:
                        order_status = translate_text(order_status, lang)
                    if customer_order_status:
                        customer_order_status = translate_text(customer_order_status, lang)
                    if reject_reason:
                        reject_reason = translate_text(reject_reason, lang)

                details.append({
                    "notification_id": r[0],
                    "order_id": r[1],
                    "vendor_id": r[2],
                    "vendor_name": vendor_name,
                    "accepted_by": r[4],
                    "rejected_by": r[5],
                    "accepted_at": str(r[6]) if r[6] else None,
                    "rejected_at": str(r[7]) if r[7] else None,
                    "order_at": str(r[8]),
                    "reject_reason": reject_reason,
                    "customer_id": r[10],
                    "customer_name": customer_name,
                    "total_amount": float(r[12]) if r[12] else 0,
                    "payment_mode": payment_mode,
                    "order_status": order_status,
                    "customer_order_status": customer_order_status
                })

        return Response({
            "success": True,
            "data": {
                "summary": summary,
                "details": details
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch notification report",
            "details": str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@active_user_required
def admin_revenue_stats(request):
    """
    GET: Returns revenue and payment statistics.
    Optional query params:
        - from_date (YYYY-MM-DD)
        - to_date (YYYY-MM-DD)
        - payment_mode ('online' or 'offline')
    Returns:
        - total_revenue (within the date range, filtered by payment_mode)
        - last_month_revenue (30 days prior to to_date or today, filtered)
        - last_week_revenue (7 days prior, filtered)
        - total_offline_payment (within date range)
        - total_online_payment (within date range)
        - total_payment_count (number of completed orders within date range)
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    if not token_user:
        return Response({"success": False, "error": "Authentication required."},
                        status=status.HTTP_401_UNAUTHORIZED)

    admin_role = token_user.get('role_id')
    if str(admin_role) not in ['1', '2']:
        return Response({"success": False, "error": "Access denied. Admins only."},
                        status=status.HTTP_403_FORBIDDEN)

    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    payment_mode = request.query_params.get('payment_mode')
    if payment_mode and payment_mode not in ['online', 'offline']:
        return Response({"error": "payment_mode must be 'online' or 'offline'"}, status=400)

    try:
        with connection.cursor() as cursor:
            cursor.callproc('GetRevenueStats', [from_date, to_date, payment_mode])
            row = cursor.fetchone()

        return Response({
            "success": True,
            "data": {
                "total_revenue": float(row[0]),
                "last_month_revenue": float(row[1]),
                "last_week_revenue": float(row[2]),
                "total_offline_payment": float(row[3]),
                "total_online_payment": float(row[4]),
                "total_payment_count": row[5]
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "error": "Failed to fetch revenue stats",
            "details": str(e),
            "trace": traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# # service type API

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@active_user_required
def service_type_api(request):
    """
    Unified CRUD API for service_type
    GET: Fetch service types - optionally filter by type_id (query params)
    POST: Create a new service type
    PUT: Update an existing service type
    DELETE: Delete a service type
    
    Authentication Required: Valid JWT token (Admin only for write operations)
    """
    from .auth import get_user_from_token
    token_user = get_user_from_token(request)
    
    if not token_user:
        return Response(
            {
                "success": False,
                "error": "Authentication required. Please provide valid token."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    logged_in_role_id = token_user.get('role_id')
    lang = request.query_params.get('lang', 'en')
    
    try:
        # ------------------- GET -------------------
        if request.method == 'GET':
            type_id = request.query_params.get('type_id')
            
            with connection.cursor() as cursor:
                if type_id:
                    # Fetch specific service type
                    cursor.execute("SELECT type_id, type_name FROM tbl_service_type WHERE type_id = %s", [type_id])
                    row = cursor.fetchone()
                    
                    if not row:
                        return Response(
                            {"error": "Service type not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                    
                    type_name = row[1]
                    if lang != 'en':
                        type_name = translate_text(type_name, lang)
                    
                    data = {
                        "type_id": row[0],
                        "type_name": type_name
                    }
                else:
                    # Fetch all service types
                    cursor.execute("SELECT type_id, type_name FROM tbl_service_type ORDER BY type_id")
                    rows = cursor.fetchall()
                    
                    data = []
                    for row in rows:
                        type_name = row[1]
                        if lang != 'en':
                            type_name = translate_text(type_name, lang)
                        
                        data.append({
                            "type_id": row[0],
                            "type_name": type_name
                        })
                
                return Response({
                    "success": True,
                    "message": "Service types fetched successfully",
                    "data": data
                }, status=status.HTTP_200_OK)
        
        # ------------------- POST -------------------
        elif request.method == 'POST':
            # Only admin (role_id 1 or 2) can create service types
            if str(logged_in_role_id) not in ['1', '2']:
                return Response(
                    {"error": "Access denied. Only admins can create service types."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            type_name = request.data.get('type_name')
            
            if not type_name:
                return Response(
                    {"error": "type_name is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with connection.cursor() as cursor:
                # Check if type_name already exists
                cursor.execute("SELECT type_id FROM tbl_service_type WHERE type_name = %s", [type_name])
                if cursor.fetchone():
                    return Response(
                        {"error": "Service type with this name already exists"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                cursor.execute("INSERT INTO tbl_service_type (type_name) VALUES (%s)", [type_name])
                cursor.execute("SELECT LAST_INSERT_ID()")
                new_id = cursor.fetchone()[0]
            
            return Response({
                "success": True,
                "message": "Service type created successfully",
                "data": {
                    "type_id": new_id,
                    "type_name": type_name
                }
            }, status=status.HTTP_201_CREATED)
        
        # ------------------- PUT -------------------
        elif request.method == 'PUT':
            # Only admin (role_id 1 or 2) can update service types
            if str(logged_in_role_id) not in ['1', '2']:
                return Response(
                    {"error": "Access denied. Only admins can update service types."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            type_id = request.data.get('type_id')
            type_name = request.data.get('type_name')
            
            if not type_id:
                return Response(
                    {"error": "type_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not type_name:
                return Response(
                    {"error": "type_name is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with connection.cursor() as cursor:
                # Check if service type exists
                cursor.execute("SELECT type_id FROM tbl_service_type WHERE type_id = %s", [type_id])
                if not cursor.fetchone():
                    return Response(
                        {"error": "Service type not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Check if another service type has the same name
                cursor.execute("SELECT type_id FROM tbl_service_type WHERE type_name = %s AND type_id != %s", [type_name, type_id])
                if cursor.fetchone():
                    return Response(
                        {"error": "Another service type with this name already exists"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                cursor.execute("UPDATE tbl_service_type SET type_name = %s WHERE type_id = %s", [type_name, type_id])
            
            return Response({
                "success": True,
                "message": "Service type updated successfully",
                "data": {
                    "type_id": type_id,
                    "type_name": type_name
                }
            }, status=status.HTTP_200_OK)
        
    
        # ------------------- DELETE -------------------
        elif request.method == 'DELETE':
            if str(logged_in_role_id) not in ['1', '2']:
                return Response(
                    {"error": "Access denied. Only admins can delete service types."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            type_id = request.query_params.get('type_id') or request.data.get('type_id')
            
            if not type_id:
                return Response(
                    {"error": "type_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with connection.cursor() as cursor:
                # Check if service type exists
                cursor.execute("SELECT type_id FROM tbl_service_type WHERE type_id = %s", [type_id])
                if not cursor.fetchone():
                    return Response(
                        {"error": "Service type not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Get all main services under this type
                cursor.execute("SELECT main_service_id FROM tbl_main_service WHERE type_id = %s", [type_id])
                main_service_ids = cursor.fetchall()
                
                deleted_count = {
                    "main_services": 0,
                    "subservices": 0,
                    "service_mappings": 0
                }
                
                for main_id_row in main_service_ids:
                    main_id = main_id_row[0]
                    
                    # Get all subservice IDs under this main service
                    cursor.execute("""
                        SELECT ss.subservice_id 
                        FROM tbl_subservice ss
                        INNER JOIN tbl_service s ON ss.subservice_id = s.subservice_id
                        WHERE s.main_service_id = %s
                    """, [main_id])
                    subservice_ids = cursor.fetchall()
                    
                    # Delete images for each subservice
                    for sub_id_row in subservice_ids:
                        sub_id = sub_id_row[0]
                        cursor.execute("SELECT sub_service_img FROM tbl_subservice WHERE subservice_id = %s", [sub_id])
                        img_row = cursor.fetchone()
                        if img_row and img_row[0]:
                            blob_name = img_row[0].split('/')[-1].split('?')[0]
                            storage_service.delete_image('SUBSERVICE', blob_name)
                        deleted_count["subservices"] += 1
                    
                    # Delete service mappings for this main service
                    cursor.execute("DELETE FROM tbl_service WHERE main_service_id = %s", [main_id])
                    deleted_count["service_mappings"] += cursor.rowcount
                    
                    # Delete main service image
                    cursor.execute("SELECT main_service_img FROM tbl_main_service WHERE main_service_id = %s", [main_id])
                    img_row = cursor.fetchone()
                    if img_row and img_row[0]:
                        blob_name = img_row[0].split('/')[-1].split('?')[0]
                        storage_service.delete_image('MAIN_SERVICE', blob_name)
                    
                    # Delete main service
                    cursor.execute("DELETE FROM tbl_main_service WHERE main_service_id = %s", [main_id])
                    deleted_count["main_services"] += 1
                
                # Delete the service type
                cursor.execute("DELETE FROM tbl_service_type WHERE type_id = %s", [type_id])
                
                return Response({
                    "success": True,
                    "message": f"Service type and all associated services deleted successfully",
                    "data": {
                        "deleted_type_id": type_id,
                        "deleted_main_services": deleted_count["main_services"],
                        "deleted_subservices": deleted_count["subservices"],
                        "deleted_service_mappings": deleted_count["service_mappings"]
                    }
                }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            "success": False,
            "error": "Operation failed",
            "details": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)