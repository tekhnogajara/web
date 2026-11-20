import requests
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.shortcuts import render

API_URL = "{{ BASE_URL }}/api/register-login/"

def admin_login(request):
    if request.method == "POST":
        mobile = request.POST.get("mobile", "").strip()
        password = request.POST.get("password", "").strip()
        otp = request.POST.get("otp", "").strip()

        if not mobile:
            messages.error(request, "Enter mobile number")
            return render(request, "login.html")

        payload = {"contact_number": mobile}

        if password:
            payload["password"] = password
        elif otp:
            payload["otp"] = otp
        else:
            messages.error(request, "Enter password or OTP")
            return render(request, "login.html")

        response = requests.post(API_URL, data=payload)
        data = response.json()

        print("LOGIN API RESPONSE:", data)

        token = data.get("token") or data.get("access") or data.get("data", {}).get("token")
        print("TOKEN:", token)

        if data.get("success") and token:
            user_obj, _ = User.objects.get_or_create(username=mobile)
            auth_login(request, user_obj)

            # Store in Django session
            request.session["token"] = token
            request.session.modified = True

            # Send token to template
            return render(request, "dashboard.html", {"api_token": token})

        messages.error(request, data.get("message", "Login failed"))

    return render(request, "login.html")



def dashboard(request):
    return render(request, "dashboard.html")

def vendors(request):
    return render(request, "vendors.html")

def customers(request):
    return render(request, "customers.html")

    
def services(request):
    return render(request, "services.html")
        
def bookings(request):
    return render(request, "bookings.html")

def payments(request):
    return render(request, "payments.html")


def booking_details(request, order_id):
    return render(request, 'booking_details.html', {'order_id': order_id})


def vendor_detail(request, vendor_id):
    return render(request, 'vendor_detail.html')

def vendor_management(request):
    return render(request, 'vendor_management.html')

def customer_orders(request, user_id):
    return render(request, 'customer_orders.html', {'user_id': user_id})


def service_management(request):
    return render(request, 'service_management.html')


def category_management(request):
    return render(request, 'category_management.html') 


def settings(request):
    return render(request, 'settings.html')


def profile(request):
    return render(request, "profile.html")


def feedback_complaints(request):
    return render(request, 'feedback_complaints.html')


from django.contrib.auth import logout
from django.shortcuts import redirect

def admin_logout(request):
    if "api_token" in request.session:
        del request.session["api_token"]
    logout(request)
    return redirect("login")


