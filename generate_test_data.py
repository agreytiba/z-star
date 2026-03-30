import os
import django
from datetime import datetime, timedelta
from django.utils import timezone
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db.backends.mysql.features import DatabaseFeatures

# Turn off RETURNING support for older MariaDB versions
DatabaseFeatures.can_return_columns_from_insert = property(lambda self: False)
DatabaseFeatures.can_return_rows_from_bulk_insert = property(lambda self: False)

from django.contrib.auth import get_user_model
from api.models import Profile, Salon, Booking, Earning, Review

User = get_user_model()

print("Generating Test Data...")

# 1. Create Customers
customers = []
for i in range(1, 6):
    email = f"customer{i}@test.com"
    user = User.objects.filter(email=email).first()
    if not user:
        user = User(email=email, username=email)
        user.set_password("password123")
        user.save()
        
    profile = Profile.objects.filter(user=user).first()
    if not profile:
        profile = Profile(user=user, role='customer', full_name=f"Customer {i} Name", phone_number=f"+25570000000{i}")
        profile.save()
    customers.append(user)

print("Created 5 Customers")

# 2. Create Salon Owners and Salons
owners = []
salons = []
for i in range(1, 4):
    email = f"owner{i}@test.com"
    user = User.objects.filter(email=email).first()
    if not user:
        user = User(email=email, username=email)
        user.set_password("password123")
        user.save()
        
    profile = Profile.objects.filter(user=user).first()
    if not profile:
        profile = Profile(user=user, role='salon_owner', full_name=f"Owner {i} Name", phone_number=f"+25571111111{i}")
        profile.save()
    owners.append(profile)

    salon = Salon.objects.filter(owner=profile).first()
    if not salon:
        salon = Salon(
            owner=profile,
            name=f"Test Salon {i}",
            address=f"Test Address {i}, Dar es Salaam",
            phone=f"+25572222222{i}",
            email=f"contact@testsalon{i}.com",
            is_verified=(i % 2 == 0),
            is_active=True,
            rating=random.uniform(3.5, 5.0),
            review_count=random.randint(10, 50)
        )
        salon.save()
    salons.append(salon)

print("Created 3 Salon Owners and Salons")

# 3. Create Bookings and Earnings
now = timezone.now()
services = ['Haircut', 'Massage', 'Manicure', 'Pedicure', 'Braiding']

for salon in salons:
    for _ in range(5):  # 5 bookings per salon
        customer = random.choice(customers)
        status = random.choice(['completed', 'pending', 'cancelled'])
        price = random.uniform(20000, 150000)
        service = random.choice(services)
        
        booking_date = now - timedelta(days=random.randint(1, 30))
        
        booking = Booking(
            user=customer,
            salon=salon,
            service_type=service,
            booking_date=booking_date,
            price=price,
            status=status
        )
        booking.save()
        
        if status == 'completed':
            Earning.objects.create(
                owner=salon.owner,
                booking=booking,
                amount=price,
                date=booking_date.date(),
                description=f"Earning from {service}"
            )
            
            Review.objects.create(
                booking=booking,
                salon=salon,
                reviewer=customer,
                rating=random.randint(3, 5),
                comment=f"Great {service}!"
            )

print("Created Bookings, Earnings, and Reviews")
print("Test data generation complete!")
