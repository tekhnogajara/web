from django.urls import path
from . import views


urlpatterns = [
    # register - login - logout
    path('register-login/', views.register_or_login_user, name='register_or_login_user'),
    path('user_logout/', views.user_logout, name='user_logout'),
    path('init-azure/', views.init_azure_containers, name='init_azure'),

    # Servises
    path('combined_service/', views.combined_service_api, name='combined_service_api'),

    # cart
    path('cart_add/', views.cart_add, name='cart_add'),
    path('cart_view/', views.cart_view, name='cart_view'),
    path('cart_remove/', views.cart_remove, name='cart_remove'),
    path('cart_checkout/', views.cart_checkout, name='cart_checkout'),

    # Users APIS
    path('manage_user_details/', views.manage_user, name='manage_user'),
    path('user_wise_service/', views.user_service_api, name='user_service_api'),
    path('feedback/', views.feedback_api, name='feedback_api'),

    # Vendor APIs
    path('vendor/notifications_pending/', views.vendor_pending_notifications, name='vendor_pending_notifications'),
    path('vendor/orders_history/', views.vendor_order_history, name='vendor_order_history'),
    path('vendor/order_accept/', views.vendor_accept_order, name='vendor_accept_order'),
    path('vendor/confirm_order/', views.vendor_confirm_order, name='vendor_confirm_order'),
    path('vendor/order_reject/', views.vendor_reject_order, name='vendor_reject_order'),
    path('vendor/order_complete/', views.vendor_complete_order, name='vendor_complete_order'),
    path('vendor/orders/<int:order_id>/', views.vendor_order_details, name='vendor_order_details'),

    # Admin APIs
    path('admin/user_detals/', views.user_detals, name='user_detals'),
    path('admin/vendor_details/', views.vendor_details, name='vendor_details'),
    path('admin/order_details/', views.order_details, name='order_details'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/vendor_notification_report/', views.vendor_notification_report, name='vendor_notification_report'),
    path('admin/revenue_stats/', views.admin_revenue_stats, name='admin_revenue_stats'),


    # Service Types
    path('service_types/', views.service_type_api, name='service_type_api'),

]
