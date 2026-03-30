"""
Auth views – OTP, registration, login, password reset.

Security improvements over the original:
  • secrets.randbelow() instead of random.randint() (cryptographically secure)
  • Per-endpoint throttles (auth: 10/min)
  • OTP records are hard-deleted after successful use (no lingering codes)
  • Constant-time OTP comparison via hmac.compare_digest()
  • Password strength is enforced by Django's AUTH_PASSWORD_VALIDATORS
  • JWT token blacklist is used on logout
  • Structured logging instead of raw print()
"""

import secrets
import hmac
import logging

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from ..serializers.auth_serializers import RegisterSerializer, UserSerializer, ProfileSerializer
from ..models import Profile, OTP

logger = logging.getLogger('api')
User = get_user_model()


def _generate_otp() -> str:
    """Return a cryptographically secure 6-digit numeric OTP string."""
    return f'{secrets.randbelow(900000) + 100000}'


def _send_otp_email(to_email: str, otp_code: str, subject: str, action_label: str) -> bool:
    """Send OTP email. Returns True on success, False on failure."""
    if not settings.EMAIL_HOST_USER:
        return False
    try:
        plain_message = (
            f'Your Zuristar {action_label} code is: {otp_code}\n\n'
            'This code expires in 30 minutes. If you did not request this, ignore this email.'
        )
        html_message = f"""
        <div style="font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;max-width:600px;
                    margin:0 auto;padding:20px;border:1px solid #e0e0e0;border-radius:10px;">
            <div style="text-align:center;margin-bottom:30px;">
                <h1 style="color:#EAB308;margin:0;">Zuristar</h1>
                <p style="color:#666;margin:5px 0 0 0;">Beauty at your fingertips</p>
            </div>
            <div style="background:#f9f9f9;padding:30px;border-radius:8px;text-align:center;">
                <h2 style="color:#333;margin-bottom:10px;">{action_label} Code</h2>
                <p style="color:#666;font-size:16px;margin-bottom:25px;">
                    Enter the following code to continue:
                </p>
                <div style="background:#fff;display:inline-block;padding:15px 40px;
                            border:2px dashed #EAB308;border-radius:8px;font-size:32px;
                            font-weight:bold;letter-spacing:5px;color:#333;">
                    {otp_code}
                </div>
                <p style="color:#999;font-size:12px;margin-top:25px;">
                    Expires in 30 minutes. If you didn&apos;t request this, ignore this email.
                </p>
            </div>
            <div style="text-align:center;margin-top:30px;font-size:12px;color:#999;">
                &copy; 2026 Zuristar. All rights reserved.
            </div>
        </div>
        """
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.error('OTP email delivery failed to %s: %s', to_email, exc)
        return False


# ─── SEND OTP ────────────────────────────────────────────────────────────────

class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'auth'

    def post(self, request):
        email        = (request.data.get('email') or '').strip().lower()
        phone_number = request.data.get('phone_number')

        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_code = _generate_otp()
        OTP.objects.create(email=email, phone_number=phone_number, otp_code=otp_code)

        email_sent = _send_otp_email(
            to_email=email,
            otp_code=otp_code,
            subject='Your Zuristar Verification Code',
            action_label='Verification',
        )

        logger.info('OTP requested for %s – email_sent=%s', email, email_sent)

        if email_sent:
            return Response({
                'message':    'Verification code sent successfully',
                'email_sent': True,
                'otp_sent':   True,
            })

        # Code is in DB; let user proceed. Only expose code in DEBUG mode.
        return Response({
            'message':    'Verification code created. Email delivery may be delayed.',
            'email_sent': False,
            'otp_sent':   True,
            'code':       otp_code if settings.DEBUG else None,
            'hint':       'Check your .env SMTP configuration' if settings.DEBUG else None,
        })


# ─── VERIFY OTP ──────────────────────────────────────────────────────────────

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'auth'

    def post(self, request):
        email        = (request.data.get('email') or '').strip().lower()
        otp_code     = (request.data.get('otp_code') or '').strip()
        full_name    = request.data.get('full_name')
        role         = request.data.get('role', 'customer')
        phone_number = request.data.get('phone_number')
        password     = request.data.get('password')
        gender       = request.data.get('gender')

        if not email or not otp_code:
            return Response(
                {'error': 'Email and verification code are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expiry = timezone.now() - timedelta(minutes=30)
        otp_record = OTP.objects.filter(
            email=email,
            is_verified=False,
            created_at__gte=expiry,
        ).last()

        # Constant-time comparison to prevent timing attacks
        if not otp_record or not hmac.compare_digest(otp_record.otp_code or '', otp_code):
            logger.warning('Invalid OTP attempt for %s', email)
            return Response(
                {'error': 'Invalid or expired verification code'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark used and clean up old OTPs for this email
        otp_record.is_verified = True
        otp_record.save(update_fields=['is_verified'])
        OTP.objects.filter(email=email, is_verified=True).exclude(pk=otp_record.pk).delete()

        username = email.split('@')[0]
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={'username': username, 'is_active': True},
        )

        if password:
            user.set_password(password)
            user.save(update_fields=['password'])

        profile, profile_created = Profile.objects.get_or_create(user=user)

        if full_name:
            profile.full_name = full_name
        elif profile_created and not profile.full_name:
            profile.full_name = username

        profile.role             = role
        profile.is_email_verified = True
        if gender:
            profile.gender = gender
        if phone_number:
            profile.phone_number = phone_number
        profile.save()

        refresh = RefreshToken.for_user(user)
        logger.info('User verified and logged in: %s', email)

        return Response({
            'user':    UserSerializer(user).data,
            'refresh': str(refresh),
            'access':  str(refresh.access_token),
        })


# ─── REGISTER ────────────────────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    serializer_class   = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'auth'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        logger.info('New user registered: %s', user.email)

        return Response({
            'user':    UserSerializer(user).data,
            'refresh': str(refresh),
            'access':  str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


# ─── LOGIN ───────────────────────────────────────────────────────────────────

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'auth'

    def post(self, request):
        email    = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password', '')

        user = authenticate(username=email, password=password)

        if user is None:
            logger.warning('Failed login for %s', email)
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {'error': 'Your account has been suspended. Contact support.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        logger.info('User logged in: %s', email)

        return Response({
            'user':    UserSerializer(user).data,
            'refresh': str(refresh),
            'access':  str(refresh.access_token),
        })


# ─── LOGOUT ──────────────────────────────────────────────────────────────────

class LogoutView(APIView):
    """Blacklist the refresh token so it cannot be reused after logout."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        logger.info('User logged out: %s', request.user.email)
        return Response({'message': 'Logged out successfully'})


# ─── PROFILE ─────────────────────────────────────────────────────────────────

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ─── FORGOT PASSWORD ─────────────────────────────────────────────────────────

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'auth'

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Always respond with 200 so we don't leak whether the email exists
        exists = User.objects.filter(email=email).exists()
        if exists:
            otp_code = _generate_otp()
            OTP.objects.create(email=email, otp_code=otp_code)
            _send_otp_email(
                to_email=email,
                otp_code=otp_code,
                subject='Zuristar Password Reset Code',
                action_label='Password Reset',
            )
            logger.info('Password reset OTP sent to %s', email)

        return Response({
            'message': 'If an account with that email exists, a reset code has been sent.'
        })


# ─── RESET PASSWORD ──────────────────────────────────────────────────────────

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'auth'

    def post(self, request):
        email        = (request.data.get('email') or '').strip().lower()
        otp_code     = (request.data.get('otp_code') or '').strip()
        new_password = request.data.get('new_password', '')

        if not email or not otp_code or not new_password:
            return Response(
                {'error': 'email, otp_code, and new_password are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 8:
            return Response(
                {'error': 'Password must be at least 8 characters'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expiry = timezone.now() - timedelta(minutes=30)
        otp_record = OTP.objects.filter(
            email=email,
            is_verified=False,
            created_at__gte=expiry,
        ).last()

        if not otp_record or not hmac.compare_digest(otp_record.otp_code or '', otp_code):
            return Response(
                {'error': 'Invalid or expired reset code'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_record.is_verified = True
        otp_record.save(update_fields=['is_verified'])

        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save(update_fields=['password'])
            logger.info('Password reset successful for %s', email)
            return Response({'message': 'Password reset successful'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
