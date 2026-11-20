# # services/otp_service.py

# import os
# import requests
# import random
# import time
# import re
# import urllib.parse
# from datetime import datetime, timedelta
# from dotenv import load_dotenv
# import logging
# from random import randint

# # Set up logging
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# # Load environment variables
# load_dotenv()


# # =======================
# # SMS OTP Service
# # =======================
# class OtpService:
#     """Original SMS OTP Service"""

#     def __init__(self):
#         self.otp_store = {}  # {mobile: {"otp": "...", "timestamp": ...}}

#     def generate_otp(self):
#         """Generate a 6-digit OTP as string"""
#         return str(randint(100000, 999999))

#     def validate_mobile_number(self, mobile):
#         """Validate Indian mobile number"""
#         return re.match(r'^[6-9]\d{9}$', str(mobile)) is not None

#     def sendOtp(self, mobile):
#         """Send OTP via SMS API"""
#         if not self.validate_mobile_number(mobile):
#             return {"success": False, "message": "Invalid mobile number"}

#         otp = self.generate_otp()
#         message = f"आपला ओटीपी क्रमांक आहे: {otp} कृपया हा ओटीपी पुढील प्रक्रियेसाठी वापरा. - SHRI NILKANTHESHWAR"
#         encoded_message = urllib.parse.quote(message)

#         url = (
#             f"http://bulksms.saakshisoftware.com/api/mt/SendSMS?"
#             f"user=TECHNOLOGIA&password=70837513&senderid=SNILKN&channel=Trans&DCS=8"
#             f"&flashsms=0&number={mobile}&text={encoded_message}&route=04"
#             f"&DLTTemplateId=1707174402543957427&PEID=1701172491385434035"
#         )

#         try:
#             response = requests.get(url, timeout=10)
#             response.raise_for_status()
#             # Some APIs return plain text, handle gracefully
#             data = response.json() if "application/json" in response.headers.get("Content-Type", "") else {"ErrorCode": "000"}
#             if data.get("ErrorCode") == "000":
#                 self.otp_store[mobile] = {"otp": otp, "timestamp": time.time()}
#                 return {"success": True, "message": "OTP sent successfully via SMS"}
#             else:
#                 return {"success": False, "message": "Failed to send OTP via SMS API"}
#         except Exception as e:
#             logger.error(f"SMS API error: {str(e)}")
#             return {"success": False, "message": f"SMS API error: {str(e)}"}

#     def verifyOtp(self, mobile, otp):
#         """Verify OTP"""
#         stored = self.otp_store.get(mobile)
#         if not stored:
#             return {"success": False, "message": "OTP not found or expired"}

#         if time.time() - stored["timestamp"] > 5 * 60:
#             del self.otp_store[mobile]
#             return {"success": False, "message": "OTP expired"}

#         if stored["otp"] == str(otp).strip():
#             del self.otp_store[mobile]
#             return {"success": True, "message": "OTP verified successfully"}

#         return {"success": False, "message": "Invalid OTP"}


# # =======================
# # WhatsApp OTP Service
# # =======================
# class WhatsAppOtpService:
#     """WhatsApp OTP via Green-API"""

#     def __init__(self):
#         self.instance_id = os.getenv("GREEN_API_ID")
#         self.api_token = os.getenv("GREEN_API_TOKEN")
#         self.base_url = os.getenv("GREEN_API_BASE", "https://api.green-api.com")

#         if not all([self.instance_id, self.api_token]):
#             logger.warning("Green-API credentials not found. WhatsApp OTP will be simulated.")
#             self.valid_config = False
#         else:
#             self.valid_config = True
#             logger.info(f"WhatsApp OTP Service initialized with instance: {self.instance_id}")

#         self.otp_store = {}

#     def _format_phone(self, number):
#         """Format Indian phone number to 91XXXXXXXXXX"""
#         if not number:
#             return None
#         number = str(number).strip()
#         number = ''.join(filter(str.isdigit, number))
#         if number.startswith('+91'):
#             number = number[3:]
#         elif number.startswith('91') and len(number) > 10:
#             number = number[2:]
#         elif number.startswith('0'):
#             number = number[1:]
#         if len(number) == 10:
#             return f"91{number}"
#         elif len(number) == 12 and number.startswith('91'):
#             return number
#         return None

#     def generate_otp(self, length=6):
#         return ''.join(str(random.randint(0, 9)) for _ in range(length))

#     def sendOtp(self, mobile_number):
#         """Send OTP via WhatsApp"""
#         try:
#             phone = self._format_phone(mobile_number)
#             if not phone:
#                 return {"success": False, "message": "Invalid Indian mobile number"}

#             otp = self.generate_otp()
#             message = f"Your verification code is {otp}. Valid for 5 minutes. Do not share with anyone. - Gajara"

#             if not self.valid_config:
#                 logger.info(f"SIMULATED WhatsApp OTP for {phone}: {otp}")
#                 self.otp_store[phone] = {
#                     "otp": otp,
#                     "created": datetime.utcnow(),
#                     "expires": datetime.utcnow() + timedelta(minutes=5)
#                 }
#                 return {"success": True, "message": "OTP sent successfully via WhatsApp"}

#             url = f"{self.base_url}/waInstance{self.instance_id}/sendMessage/{self.api_token}"
#             payload = {"chatId": f"{phone}@c.us", "message": message}

#             response = requests.post(url, json=payload, timeout=15)
#             response.raise_for_status()
#             data = response.json()

#             if data.get("idMessage"):
#                 self.otp_store[phone] = {
#                     "otp": otp,
#                     "created": datetime.utcnow(),
#                     "expires": datetime.utcnow() + timedelta(minutes=5)
#                 }
#                 return {"success": True, "message": "OTP sent successfully via WhatsApp"}
#             else:
#                 return {"success": False, "message": "Failed to send WhatsApp message"}
#         except Exception as e:
#             logger.error(f"WhatsApp OTP error: {str(e)}")
#             return {"success": False, "message": f"WhatsApp OTP error: {str(e)}"}

#     def verifyOtp(self, mobile_number, user_otp):
#         phone = self._format_phone(mobile_number)
#         if not phone:
#             return {"success": False, "message": "Invalid mobile number"}

#         stored = self.otp_store.get(phone)
#         if not stored:
#             return {"success": False, "message": "No OTP found. Please request a new one."}

#         if datetime.utcnow() > stored["expires"]:
#             del self.otp_store[phone]
#             return {"success": False, "message": "OTP has expired"}

#         if stored["otp"] == str(user_otp).strip():
#             del self.otp_store[phone]
#             return {"success": True, "message": "OTP verified successfully"}

#         return {"success": False, "message": "Invalid OTP"}


# # =======================
# # Unified OTP Service
# # =======================
# class UnifiedOtpService:
#     """Sends OTP via WhatsApp and SMS simultaneously"""

#     def __init__(self):
#         self.sms_service = OtpService()
#         self.wa_service = WhatsAppOtpService()

#     def sendOtp(self, mobile_number):
#         """Send OTP via WhatsApp and SMS"""
#         results = {}
#         # WhatsApp
#         wa_result = self.wa_service.sendOtp(mobile_number)
#         results["whatsapp"] = wa_result

#         # SMS
#         sms_result = self.sms_service.sendOtp(mobile_number)
#         results["sms"] = sms_result

#         # Overall success
#         success = wa_result["success"] or sms_result["success"]
#         return {
#             "success": success,
#             "message": "OTP sent via at least one channel",
#             "details": results
#         }

#     def verifyOtp(self, mobile_number, otp):
#         """Verify OTP from either channel"""
#         wa_verify = self.wa_service.verifyOtp(mobile_number, otp)
#         if wa_verify["success"]:
#             return {"success": True, "message": "OTP verified via WhatsApp"}

#         sms_verify = self.sms_service.verifyOtp(mobile_number, otp)
#         if sms_verify["success"]:
#             return {"success": True, "message": "OTP verified via SMS"}

#         return {"success": False, "message": "Invalid or expired OTP"}


# # =======================
# # Create singleton instance
# # =======================
# otp_service = UnifiedOtpService()




# services/otp_service.py

import os
import requests
import random
import time
import re
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from random import randint

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()


# =======================
# SMS OTP Service
# =======================
class OtpService:
    """Original SMS OTP Service"""

    def __init__(self):
        self.otp_store = {}  # {mobile: {"otp": "...", "timestamp": ...}}

    def generate_otp(self):
        """Generate a 6-digit OTP as string"""
        return str(randint(100000, 999999))

    def validate_mobile_number(self, mobile):
        """Validate Indian mobile number"""
        return re.match(r'^[6-9]\d{9}$', str(mobile)) is not None

    def sendOtp(self, mobile):
        """Send OTP via SMS API"""
        if not self.validate_mobile_number(mobile):
            return {"success": False, "message": "Invalid mobile number"}

        otp = self.generate_otp()
        message = f"आपला ओटीपी क्रमांक आहे: {otp} कृपया हा ओटीपी पुढील प्रक्रियेसाठी वापरा. - SHRI NILKANTHESHWAR"
        encoded_message = urllib.parse.quote(message)

        url = (
            f"http://bulksms.saakshisoftware.com/api/mt/SendSMS?"
            f"user=TECHNOLOGIA&password=70837513&senderid=SNILKN&channel=Trans&DCS=8"
            f"&flashsms=0&number={mobile}&text={encoded_message}&route=04"
            f"&DLTTemplateId=1707174402543957427&PEID=1701172491385434035"
        )

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            # Some APIs return plain text, handle gracefully
            data = response.json() if "application/json" in response.headers.get("Content-Type", "") else {"ErrorCode": "000"}
            if data.get("ErrorCode") == "000":
                self.otp_store[mobile] = {"otp": otp, "timestamp": time.time()}
                return {"success": True, "message": "OTP sent successfully via SMS"}
            else:
                return {"success": False, "message": "Failed to send OTP via SMS API"}
        except Exception as e:
            logger.error(f"SMS API error: {str(e)}")
            return {"success": False, "message": f"SMS API error: {str(e)}"}

    def verifyOtp(self, mobile, otp):
        """Verify OTP"""
        stored = self.otp_store.get(mobile)
        if not stored:
            return {"success": False, "message": "OTP not found or expired"}

        if time.time() - stored["timestamp"] > 5 * 60:
            del self.otp_store[mobile]
            return {"success": False, "message": "OTP expired"}

        if stored["otp"] == str(otp).strip():
            del self.otp_store[mobile]
            return {"success": True, "message": "OTP verified successfully"}

        return {"success": False, "message": "Invalid OTP"}
    
    def sendDeclineNotification(self, mobile, decline_reason):
        """
        Send decline notification SMS to vendor
        :param mobile: Vendor's mobile number
        :param decline_reason: Reason for application decline
        """
        if not self.validate_mobile_number(mobile):
            return {"success": False, "message": "Invalid mobile number"}
        
        # Create message in Marathi (you can also add Hindi/English versions)
        message = f"तुमचा अर्ज नामंजूर करण्यात आला आहे. कारण: {decline_reason}. कृपया योग्य कागदपत्रांसह पुन्हा नोंदणी करा."
        encoded_message = urllib.parse.quote(message)
        
        url = (
            f"http://bulksms.saakshisoftware.com/api/mt/SendSMS?"
            f"user=TECHNOLOGIA&password=70837513&senderid=SNILKN&channel=Trans&DCS=8"
            f"&flashsms=0&number={mobile}&text={encoded_message}&route=04"
            f"&DLTTemplateId=1707174402543957427&PEID=1701172491385434035"
        )
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json() if "application/json" in response.headers.get("Content-Type", "") else {"ErrorCode": "000"}
            if data.get("ErrorCode") == "000":
                logger.info(f"Decline notification sent to {mobile}")
                return {"success": True, "message": "Decline notification sent successfully"}
            else:
                logger.error(f"Failed to send decline notification to {mobile}: {data}")
                return {"success": False, "message": "Failed to send decline notification"}
        except Exception as e:
            logger.error(f"Decline notification SMS error: {str(e)}")
            return {"success": False, "message": f"SMS error: {str(e)}"}


# =======================
# WhatsApp OTP Service
# =======================
class WhatsAppOtpService:
    """WhatsApp OTP via Green-API"""

    def __init__(self):
        self.instance_id = os.getenv("GREEN_API_ID")
        self.api_token = os.getenv("GREEN_API_TOKEN")
        self.base_url = os.getenv("GREEN_API_BASE", "https://api.green-api.com")

        if not all([self.instance_id, self.api_token]):
            logger.warning("Green-API credentials not found. WhatsApp OTP will be simulated.")
            self.valid_config = False
        else:
            self.valid_config = True
            logger.info(f"WhatsApp OTP Service initialized with instance: {self.instance_id}")

        self.otp_store = {}

    def _format_phone(self, number):
        """Format Indian phone number to 91XXXXXXXXXX"""
        if not number:
            return None
        number = str(number).strip()
        number = ''.join(filter(str.isdigit, number))
        if number.startswith('+91'):
            number = number[3:]
        elif number.startswith('91') and len(number) > 10:
            number = number[2:]
        elif number.startswith('0'):
            number = number[1:]
        if len(number) == 10:
            return f"91{number}"
        elif len(number) == 12 and number.startswith('91'):
            return number
        return None

    def generate_otp(self, length=6):
        return ''.join(str(random.randint(0, 9)) for _ in range(length))

    def sendOtp(self, mobile_number):
        """Send OTP via WhatsApp"""
        try:
            phone = self._format_phone(mobile_number)
            if not phone:
                return {"success": False, "message": "Invalid Indian mobile number"}

            otp = self.generate_otp()
            message = f"Your verification code is {otp}. Valid for 5 minutes. Do not share with anyone. - Gajara"

            if not self.valid_config:
                logger.info(f"SIMULATED WhatsApp OTP for {phone}: {otp}")
                self.otp_store[phone] = {
                    "otp": otp,
                    "created": datetime.utcnow(),
                    "expires": datetime.utcnow() + timedelta(minutes=5)
                }
                return {"success": True, "message": "OTP sent successfully via WhatsApp"}

            url = f"{self.base_url}/waInstance{self.instance_id}/sendMessage/{self.api_token}"
            payload = {"chatId": f"{phone}@c.us", "message": message}

            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("idMessage"):
                self.otp_store[phone] = {
                    "otp": otp,
                    "created": datetime.utcnow(),
                    "expires": datetime.utcnow() + timedelta(minutes=5)
                }
                return {"success": True, "message": "OTP sent successfully via WhatsApp"}
            else:
                return {"success": False, "message": "Failed to send WhatsApp message"}
        except Exception as e:
            logger.error(f"WhatsApp OTP error: {str(e)}")
            return {"success": False, "message": f"WhatsApp OTP error: {str(e)}"}

    def verifyOtp(self, mobile_number, user_otp):
        phone = self._format_phone(mobile_number)
        if not phone:
            return {"success": False, "message": "Invalid mobile number"}

        stored = self.otp_store.get(phone)
        if not stored:
            return {"success": False, "message": "No OTP found. Please request a new one."}

        if datetime.utcnow() > stored["expires"]:
            del self.otp_store[phone]
            return {"success": False, "message": "OTP has expired"}

        if stored["otp"] == str(user_otp).strip():
            del self.otp_store[phone]
            return {"success": True, "message": "OTP verified successfully"}

        return {"success": False, "message": "Invalid OTP"}
    
    def sendDeclineNotification(self, mobile_number, decline_reason):
        """
        Send decline notification via WhatsApp to vendor
        """
        try:
            phone = self._format_phone(mobile_number)
            if not phone:
                return {"success": False, "message": "Invalid mobile number"}

            message = f"Your application has been declined. Reason: {decline_reason}. Please re-register with correct documents. - Gajara"

            if not self.valid_config:
                logger.info(f"SIMULATED WhatsApp decline notification to {phone}: {message}")
                return {"success": True, "message": "Decline notification sent via WhatsApp (simulated)"}

            url = f"{self.base_url}/waInstance{self.instance_id}/sendMessage/{self.api_token}"
            payload = {"chatId": f"{phone}@c.us", "message": message}

            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get("idMessage"):
                logger.info(f"Decline notification sent via WhatsApp to {phone}")
                return {"success": True, "message": "Decline notification sent via WhatsApp"}
            else:
                return {"success": False, "message": "Failed to send decline notification"}
        except Exception as e:
            logger.error(f"WhatsApp decline notification error: {str(e)}")
            return {"success": False, "message": f"WhatsApp error: {str(e)}"}


# =======================
# Unified OTP Service
# =======================
class UnifiedOtpService:
    """Sends OTP via WhatsApp and SMS simultaneously"""

    def __init__(self):
        self.sms_service = OtpService()
        self.wa_service = WhatsAppOtpService()

    def sendOtp(self, mobile_number):
        """Send OTP via WhatsApp and SMS"""
        results = {}
        # WhatsApp
        wa_result = self.wa_service.sendOtp(mobile_number)
        results["whatsapp"] = wa_result

        # SMS
        sms_result = self.sms_service.sendOtp(mobile_number)
        results["sms"] = sms_result

        # Overall success
        success = wa_result["success"] or sms_result["success"]
        return {
            "success": success,
            "message": "OTP sent via at least one channel",
            "details": results
        }

    def verifyOtp(self, mobile_number, otp):
        """Verify OTP from either channel"""
        wa_verify = self.wa_service.verifyOtp(mobile_number, otp)
        if wa_verify["success"]:
            return {"success": True, "message": "OTP verified via WhatsApp"}

        sms_verify = self.sms_service.verifyOtp(mobile_number, otp)
        if sms_verify["success"]:
            return {"success": True, "message": "OTP verified via SMS"}

        return {"success": False, "message": "Invalid or expired OTP"}
    
    def sendDeclineNotification(self, mobile_number, decline_reason):
        """
        Send decline notification to vendor via both WhatsApp and SMS
        """
        results = {}
        
        # Send via SMS
        sms_result = self.sms_service.sendDeclineNotification(mobile_number, decline_reason)
        results["sms"] = sms_result
        
        # Send via WhatsApp
        wa_result = self.wa_service.sendDeclineNotification(mobile_number, decline_reason)
        results["whatsapp"] = wa_result
        
        # Overall success (if either channel works)
        success = sms_result["success"] or wa_result["success"]
        
        return {
            "success": success,
            "message": "Decline notification sent via at least one channel",
            "details": results
        }


# =======================
# Create singleton instance
# =======================
otp_service = UnifiedOtpService()