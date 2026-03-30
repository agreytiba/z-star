import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db.backends.mysql.features import DatabaseFeatures
# Turn off RETURNING support for older MariaDB versions
DatabaseFeatures.can_return_columns_from_insert = property(lambda self: False)
DatabaseFeatures.can_return_rows_from_bulk_insert = property(lambda self: False)

from django.contrib.auth import get_user_model
from api.models import Profile

User = get_user_model()
email = 'admin@zuristar.co.tz'
password = 'Zuri@Admin1234:!'

# Check for existing admins other than the target one
existing_admins = Profile.objects.filter(role='admin').exclude(user__email=email)
if existing_admins.exists():
    print(f"Error: Another admin already exists ({existing_admins.first().user.email}).")
    print("Only one admin is allowed. Please demote the existing admin first.")
    exit(1)

user = User.objects.filter(email=email).first()
if not user:
    # Ensure no other user is a superuser
    if User.objects.filter(is_superuser=True).exists():
         print("Error: A superuser already exists. Only one admin/superuser is allowed.")
         exit(1)
    user = User(email=email)
    
user.set_password(password)
user.is_staff = True
user.is_superuser = True
user.save()

profile = Profile.objects.filter(user=user).first()
if not profile:
    profile = Profile(user=user, role='admin', full_name='ZuriStar Admin')
    profile.save()
else:
    profile.role = 'admin'
    profile.full_name = 'ZuriStar Admin'
    profile.save()

print(f"Admin credentials generated:\nEmail: {email}\nPassword: {password}")
