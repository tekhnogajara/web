from django.urls import path
from . import views

urlpatterns = [
    
    path('', views.admin_login, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('vendors/', views.vendors, name='vendors'),
    path('customers/', views.customers, name='customers'),
    path('services/', views.services, name='services'),
    path('bookings/', views.bookings, name='bookings'),
    path('payments/', views.payments, name='payments'),
    path('booking-details/<int:order_id>/', views.booking_details, name='booking_details'),
    path('vendor-management/', views.vendor_management, name='vendor_management'),
    path('vendor-detail/<int:vendor_id>/', views.vendor_detail, name='vendor_detail'),
    path('customer-orders/<int:user_id>/', views.customer_orders, name='customer_orders'),
    path('service-management/', views.service_management, name='service_management'),
    path('category-management/', views.category_management, name='category_management'),
    path('settings/', views.settings, name='settings'),
    path('feedback-complaints/', views.feedback_complaints, name='feedback_complaints'),
    path('profile/', views.profile, name='profile'),
    
    # urls.py
    path("logout/", views.admin_logout, name="logout"),
]