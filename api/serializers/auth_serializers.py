from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import (
    Profile, Salon, SalonService, SalonStaff, Booking, Review, 
    LoyaltyPoints, LoyaltyTransaction, Product, Earning, StaffLedger, SalonGallery
)

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['full_name', 'role', 'avatar_url', 'is_email_verified', 'phone_number', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.full_name', read_only=True)
    role = serializers.CharField(source='profile.role', read_only=True)
    avatar_url = serializers.CharField(source='profile.avatar_url', read_only=True)
    phone_number = serializers.CharField(source='profile.phone_number', read_only=True)
    is_email_verified = serializers.BooleanField(source='profile.is_email_verified', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'avatar_url', 'phone_number', 'is_email_verified']

class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True)
    role = serializers.CharField(write_only=True, default='customer')
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'role']

    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        role = validated_data.pop('role')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['email'],
            password=password
        )
        
        Profile.objects.create(
            user=user,
            full_name=full_name,
            role=role
        )
        
        return user

class SalonServiceSerializer(serializers.ModelSerializer):
    durationMinutes = serializers.IntegerField(source='duration_minutes', read_only=True)
    serviceGroup = serializers.CharField(source='service_group', read_only=True)
    
    class Meta:
        model = SalonService
        fields = [
            'id', 'salon', 'name', 'description', 'price', 
            'duration_minutes', 'durationMinutes', 
            'category', 'subcategory', 'service_group', 'serviceGroup', 
            'session_count', 'is_available', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def to_internal_value(self, data):
        # Support camelCase in input by mapping to snake_case
        if 'durationMinutes' in data and 'duration_minutes' not in data:
            data['duration_minutes'] = data.pop('durationMinutes')
        if 'serviceGroup' in data and 'service_group' not in data:
            data['service_group'] = data.pop('serviceGroup')
        if 'is_enabled' in data and 'is_available' not in data:
            data['is_available'] = data.pop('is_enabled')
        return super().to_internal_value(data)

class SalonSerializer(serializers.ModelSerializer):
    owner_id = serializers.CharField(source='owner.id', read_only=True)
    phone_number = serializers.CharField(source='phone', required=False, allow_blank=True)
    working_hours = serializers.JSONField(source='opening_hours', required=False, allow_null=True)
    services = SalonServiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Salon
        fields = [
            'id', 'owner_id', 'name', 'description', 'address', 'latitude', 'longitude', 
            'rating', 'review_count', 'images', 'phone_number', 'email', 'website', 
            'working_hours', 'available_time_slots', 'is_verified', 'tier', 
            'subscription_plan', 'is_active', 'is_mobile_service', 'is_in_salon', 
            'gender_specific', 'created_at', 'services'
        ]

    def to_internal_value(self, data):
        # Map phone_number to phone for input
        if 'phone_number' in data and 'phone' not in data:
            data['phone'] = data.pop('phone_number')
        # Map working_hours to opening_hours for input
        if 'working_hours' in data and 'opening_hours' not in data:
            data['opening_hours'] = data.pop('working_hours')
        return super().to_internal_value(data)

class BookingSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    salon_id = serializers.PrimaryKeyRelatedField(
        source='salon',
        queryset=Salon.objects.all()
    )
    salon_name = serializers.SerializerMethodField(read_only=True)
    owner_id = serializers.SerializerMethodField(read_only=True)
    staff_id = serializers.PrimaryKeyRelatedField(
        source='staff',
        queryset=SalonStaff.objects.all(),
        required=False,
        allow_null=True
    )
    staff_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'user_id', 'salon_id', 'salon_name', 'service_type', 'service_description',
            'booking_date', 'time_slot', 'price', 'status', 'is_instant_booking', 'notes',
            'calendar_event_id', 'reminder_set', 'owner_id', 'staff_id', 'staff_name',
            'additional_staff_ids', 'duration_minutes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_salon_name(self, obj):
        return obj.salon.name

    def get_owner_id(self, obj):
        return obj.salon.owner.id

    def get_staff_name(self, obj):
        return obj.staff.profile.full_name if obj.staff else None

    def to_internal_value(self, data):
        # Support both 'salon' and 'salon_id' in input
        if 'salon' in data and 'salon_id' not in data:
            data['salon_id'] = data.get('salon')
        if 'staff' in data and 'staff_id' not in data:
            data['staff_id'] = data.get('staff')
        return super().to_internal_value(data)

class SalonStaffSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email_invite = serializers.SerializerMethodField()
    avatar_url = serializers.CharField(source='profile.avatar_url', read_only=True)
    
    class Meta:
        model = SalonStaff
        fields = ['id', 'salon', 'name', 'email_invite', 'avatar_url', 'role', 'skills', 'schedule', 'commission_rate', 'is_active', 'created_at']
        extra_kwargs = {
            'salon': {'required': False} # handle salon assignment manually
        }

    def get_name(self, obj):
        return obj.profile.full_name if obj.profile_id else None

    def get_email_invite(self, obj):
        return obj.profile.user.email if obj.profile_id and hasattr(obj.profile, 'user') else None

class LoyaltyPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyPoints
        fields = '__all__'

class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTransaction
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    salon_id = serializers.PrimaryKeyRelatedField(
        source='salon',
        queryset=Salon.objects.all()
    )
    
    class Meta:
        model = Product
        fields = ['id', 'salon_id', 'name', 'description', 'price', 'stock_quantity', 'category', 'image_url', 'is_enabled', 'created_at']

    def to_internal_value(self, data):
        # Map salon_id for input
        if 'salon_id' in data and 'salon' not in data:
            data['salon'] = data.pop('salon_id')
        return super().to_internal_value(data)

class EarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Earning
        fields = '__all__'

class StaffLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffLedger
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.profile.full_name', read_only=True)
    reviewer_avatar = serializers.CharField(source='reviewer.profile.avatar_url', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'booking', 'salon', 'reviewer', 'reviewer_name', 
            'reviewer_avatar', 'rating', 'comment', 'owner_response', 
            'staff_response', 'created_at'
        ]
        read_only_fields = ['id', 'reviewer', 'reviewer_name', 'reviewer_avatar', 'created_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Ensure reviewer_name fallback if no profile exists
        if not representation.get('reviewer_name'):
            representation['reviewer_name'] = instance.reviewer.username
        return representation

class SalonGallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SalonGallery
        fields = '__all__'
