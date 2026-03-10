from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from ..serializers.auth_serializers import RegisterSerializer, UserSerializer, ProfileSerializer
from ..models import Profile, OTP
import random
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        phone_number = request.data.get('phone_number') # Optional now
        
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate 6-digit verification code
        otp_code = str(random.randint(100000, 999999))
        
        # Save verification record to database
        OTP.objects.create(email=email, phone_number=phone_number, otp_code=otp_code)
        
        email_sent = False
        
        # 1. Send Verification Code via Email
        if settings.EMAIL_HOST_USER:
            try:
                subject = 'Your Zuristar Verification Code'
                message = f'Your verification code for Zuristar is: {otp_code}\n\nThis code will expire in 30 minutes.'
                html_message = f"""
                <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #EAB308; margin: 0;">Zuristar</h1>
                        <p style="color: #666; margin: 5px 0 0 0;">Beauty at your fingertips</p>
                    </div>
                    <div style="background-color: #f9f9f9; padding: 30px; border-radius: 8px; text-align: center;">
                        <h2 style="color: #333; margin-bottom: 10px;">Verification Code</h2>
                        <p style="color: #666; font-size: 16px; margin-bottom: 25px;">Enter the following code to verify your account:</p>
                        <div style="background-color: #fff; display: inline-block; padding: 15px 40px; border: 2px dashed #EAB308; border-radius: 8px; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #333;">
                            {otp_code}
                        </div>
                        <p style="color: #999; font-size: 12px; margin-top: 25px;">This code will expire in 30 minutes. If you didn't request this code, please ignore this email.</p>
                    </div>
                    <div style="text-align: center; margin-top: 30px; font-size: 12px; color: #999;">
                        &copy; 2026 Zuristar. All rights reserved.
                    </div>
                </div>
                """
                # Note: Braces in the HTML like style="..." will conflict with f-string if not escaped,
                # but since we are using f-string, we only need to double the braces if they are NOT intended for f-string.
                # However, for simplicity and safety with CSS, we'll use a direct string replacement if it gets complex.
                # Here we just used the f-string variable {otp_code}.
                
                # Let's verify the CSS braces are okay. CSS in style="..." doesn't use {}. 
                # Braces are only in <style> tags which we aren't using here.
                # Inline styles use style="property: value;". So {otp_code} is safe.
                
                
                send_mail(
                    subject, 
                    message, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [email], 
                    html_message=html_message,
                    fail_silently=False
                )
                email_sent = True
            except Exception as e:
                print(f"Email Send Error: {e}")

        # Final Response
        if email_sent:
            return Response({
                'message': 'Verification code sent successfully',
                'email_sent': email_sent,
                'sms_sent': False,
                'otp_sent': True
            })
        else:
            # OTP is still saved to DB even if email failed.
            # Return 200 so the app can proceed — in debug mode expose the code
            # so the developer can manually verify. Never do this in production.
            return Response({
                'message': 'Verification code created. Email delivery may be delayed.',
                'email_sent': False,
                'sms_sent': False,
                'otp_sent': True,  # OTP record exists — let the user verify
                'code': otp_code if settings.DEBUG else None,
                'hint': "Check your .env SMTP configuration"
            }, status=status.HTTP_200_OK)

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp_code')
        full_name = request.data.get('full_name')
        role = request.data.get('role', 'customer')
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')
        gender = request.data.get('gender')
        
        if not email or not otp_code:
            return Response({'error': 'Email and Verification Code are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if code is valid and not expired (e.g., last 30 minutes)
        thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
        otp_record = OTP.objects.filter(
            email=email, 
            otp_code=otp_code,
            is_verified=False,
            created_at__gte=thirty_minutes_ago
        ).last()
        
        if not otp_record:
            return Response({'error': 'Invalid or expired verification code'}, status=status.HTTP_400_BAD_REQUEST)
        
        otp_record.is_verified = True
        otp_record.save()
        
        # Find or create user
        username = email.split('@')[0]
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'username': username, 'is_active': True}
        )
        
        if password:
            user.set_password(password)
            user.save()
        
        # Get or create profile
        profile, profile_created = Profile.objects.get_or_create(user=user)
        
        # Update profile fields
        if full_name:
            profile.full_name = full_name
        elif profile_created and not profile.full_name:
            profile.full_name = username
            
        profile.role = role
        
        if gender:
            profile.gender = gender
        
        if phone_number:
            profile.phone_number = phone_number
            
        profile.is_email_verified = True
        profile.save()
            
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        user = authenticate(username=email, password=password)
        
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

