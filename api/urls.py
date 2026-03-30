from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views.auth_views import (
    RegisterView, LoginView, LogoutView, UserProfileView,
    SendOTPView, VerifyOTPView, ForgotPasswordView, ResetPasswordView,
)
from .views.core_views import (
    SalonViewSet, SalonServiceViewSet, BookingViewSet, ProductViewSet,
    ReviewViewSet, LoyaltyViewSet, SalonStaffViewSet, DashboardViewSet, EarningViewSet,
)
from .views.staff_views import StaffViewSet
from .views.notification_views import NotificationViewSet
from .views.media_views import ImageUploadView
from .views.fcm_views import RegisterFCMTokenView
from .views.admin_views import AdminViewSet

router = DefaultRouter()
router.register(r'salons',       SalonViewSet)
router.register(r'services',     SalonServiceViewSet)
router.register(r'bookings',     BookingViewSet)
router.register(r'products',     ProductViewSet)
router.register(r'reviews',      ReviewViewSet)
router.register(r'loyalty',      LoyaltyViewSet,    basename='loyalty')
router.register(r'dashboard',    DashboardViewSet,  basename='dashboard')
router.register(r'revenue',      EarningViewSet,    basename='revenue')
router.register(r'staff',        SalonStaffViewSet)
router.register(r'staff-portal', StaffViewSet,      basename='staff-portal')
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'admin',        AdminViewSet,      basename='admin')

urlpatterns = [
    path('', include(router.urls)),

    # Auth
    path('auth/register/',        RegisterView.as_view(),       name='register'),
    path('auth/login/',           LoginView.as_view(),          name='login'),
    path('auth/logout/',          LogoutView.as_view(),         name='logout'),
    path('auth/send-otp/',        SendOTPView.as_view(),        name='send_otp'),
    path('auth/verify-otp/',      VerifyOTPView.as_view(),      name='verify_otp'),
    path('auth/profile/',         UserProfileView.as_view(),    name='profile'),
    path('auth/token/refresh/',   TokenRefreshView.as_view(),   name='token_refresh'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('auth/reset-password/',  ResetPasswordView.as_view(),  name='reset_password'),

    # Media & notifications
    path('media/upload/',              ImageUploadView.as_view(),    name='image_upload'),
    path('notifications/register-token/', RegisterFCMTokenView.as_view(), name='fcm_register'),
]
