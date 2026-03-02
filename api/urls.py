from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.auth_views import RegisterView, LoginView, UserProfileView, SendOTPView, VerifyOTPView
from .views.core_views import SalonViewSet, SalonServiceViewSet, BookingViewSet, ProductViewSet, ReviewViewSet, LoyaltyViewSet, SalonStaffViewSet, DashboardViewSet, EarningViewSet
from .views.staff_views import StaffViewSet
from .views.notification_views import NotificationViewSet
from .views.media_views import ImageUploadView
from .views.fcm_views import RegisterFCMTokenView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'salons', SalonViewSet)
router.register(r'services', SalonServiceViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'products', ProductViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'loyalty', LoyaltyViewSet, basename='loyalty')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'revenue', EarningViewSet, basename='revenue')
router.register(r'staff', SalonStaffViewSet)
router.register(r'staff-portal', StaffViewSet, basename='staff-portal')
router.register(r'notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/send-otp/', SendOTPView.as_view(), name='send_otp'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('media/upload/', ImageUploadView.as_view(), name='image_upload'),
    path('notifications/register-token/', RegisterFCMTokenView.as_view(), name='fcm_register'),
]
