from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

class OTP(models.Model):
    email = models.EmailField(null=True, blank=True, db_index=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    pin_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.email or self.phone_number} - {self.otp_code}"

    class Meta:
        indexes = [
            models.Index(fields=['email', 'is_verified', 'created_at']),
        ]

class Profile(models.Model):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('salon_owner', 'Salon Owner'),
        ('staff', 'Staff'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    avatar_url = models.TextField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.email

    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['role', 'created_at']),
        ]

class Salon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='owned_salons')
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    rating = models.FloatField(default=0.0)
    review_count = models.IntegerField(default=0)
    images = models.JSONField(default=list, blank=True) # List of image URLs
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    opening_hours = models.JSONField(null=True, blank=True)
    available_time_slots = models.JSONField(default=list, blank=True)
    is_verified = models.BooleanField(default=False)
    tier = models.CharField(max_length=20, default='demo')
    subscription_plan = models.CharField(max_length=20, default='free')
    is_active = models.BooleanField(default=True)
    is_mobile_service = models.BooleanField(default=False)
    is_in_salon = models.BooleanField(default=True)
    gender_specific = models.CharField(max_length=20, default='unisex')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['is_active', 'rating']),
            models.Index(fields=['is_active', 'is_verified']),
        ]

class SalonService(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    duration_minutes = models.IntegerField(default=60)
    category = models.CharField(max_length=100, null=True, blank=True)
    subcategory = models.CharField(max_length=100, null=True, blank=True)
    service_group = models.CharField(max_length=100, null=True, blank=True)
    session_count = models.IntegerField(default=1)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class SalonStaff(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='staff')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='staff_memberships')
    role = models.CharField(max_length=50, default='stylist')
    skills = models.JSONField(null=True, blank=True)
    schedule = models.JSONField(null=True, blank=True) # For availability checks
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('salon', 'profile')

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='bookings')
    service_type = models.CharField(max_length=255, default='Standard Service')
    service_description = models.TextField(null=True, blank=True)
    booking_date = models.DateTimeField()
    time_slot = models.CharField(max_length=100, default='10:00 AM')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_instant_booking = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
    staff = models.ForeignKey(SalonStaff, on_delete=models.SET_NULL, null=True, blank=True)
    additional_staff_ids = models.JSONField(default=list, blank=True)
    duration_minutes = models.IntegerField(default=60)
    reminder_set = models.BooleanField(default=False)
    calendar_event_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['salon', 'booking_date']),
            models.Index(fields=['salon', 'status']),
            models.Index(fields=['booking_date']),
        ]

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock_quantity = models.IntegerField(default=0)
    category = models.CharField(max_length=100, null=True, blank=True)
    image_url = models.TextField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Earning(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='earnings')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date = models.DateField()
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class StaffLedger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff = models.ForeignKey(SalonStaff, on_delete=models.CASCADE, related_name='ledger_entries')
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    entry_type = models.CharField(max_length=50) # payment, commission, etc.
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(null=True, blank=True)
    owner_response = models.TextField(null=True, blank=True)
    staff_response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SalonGallery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='gallery')
    image_url = models.TextField()
    caption = models.TextField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField()
    type = models.CharField(max_length=100)
    related_id = models.UUIDField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
        ]

class LoyaltyPoints(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_info')
    points = models.IntegerField(default=0)
    tier = models.CharField(max_length=20, default='bronze')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class LoyaltyTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loyalty_transactions')
    amount = models.IntegerField()
    description = models.TextField()
    transaction_type = models.CharField(max_length=50) # e.g. booking, review
    created_at = models.DateTimeField(auto_now_add=True)
from django.db import models
from django.conf import settings

class FCMToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=50) # android, ios
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'token')


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_staff = models.IntegerField(default=5)
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(default='false')
    label = models.CharField(max_length=255, default='')
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.key


class DisputeMessage(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='dispute_messages', null=True, blank=True)
    sender_role = models.CharField(max_length=50, default='admin')  # admin, customer, salon
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dispute on Booking {self.booking_id} - {self.sender_role}"
