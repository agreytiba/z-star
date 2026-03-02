import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import User, Profile, OTP

def delete_all_users():
    print("Deleting all users, profiles and OTP records...")
    
    # Delete OTP records first
    otp_count = OTP.objects.all().delete()[0]
    print(f"Deleted {otp_count} OTP records.")
    
    # Profiles are deleted via CASCADE when users are deleted, but let's be explicit if needed
    # Actually User.objects.all().delete() should handle profiles if on_delete=CASCADE is set correctly
    
    user_count = User.objects.all().delete()[0]
    print(f"Deleted {user_count} users (and their profiles).")

if __name__ == "__main__":
    delete_all_users()
