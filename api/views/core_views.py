from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from ..models import (
    Salon, SalonService, SalonStaff, Booking, Review, SalonGallery, 
    Product, LoyaltyPoints, LoyaltyTransaction, Earning, StaffLedger
)
from ..serializers.auth_serializers import (
    SalonSerializer, SalonServiceSerializer, BookingSerializer, 
    LoyaltyPointsSerializer, LoyaltyTransactionSerializer, SalonStaffSerializer,
    ProductSerializer, EarningSerializer, StaffLedgerSerializer,
    ReviewSerializer, SalonGallerySerializer
)
from rest_framework import serializers

class SalonViewSet(viewsets.ModelViewSet):
    queryset = Salon.objects.all()
    serializer_class = SalonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'address']

    def get_queryset(self):
        """
        Owners should only see salons they own.
        Customers/anonymous users should only see active salons.
        """
        user = self.request.user
        qs = Salon.objects.all()
        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'salon_owner':
                return qs.filter(owner=user.profile)
        return qs.filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user.profile)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        salon = self.get_object()
        reviews = Review.objects.filter(salon=salon).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

class SalonServiceViewSet(viewsets.ModelViewSet):
    queryset = SalonService.objects.all()
    serializer_class = SalonServiceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            return SalonService.objects.filter(salon__owner=user.profile)
        return SalonService.objects.filter(is_available=True)

    def perform_create(self, serializer):
        """
        Prevent owners from accidentally creating services under another owner's salon.
        Also enforce that an owner must have a salon before creating services.
        """
        user = self.request.user

        # Only enforce ownership rules for salon owners
        if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            salon = serializer.validated_data.get('salon')

            # If salon not provided, use owner's first salon (or fail if none)
            if salon is None:
                salon = Salon.objects.filter(owner=user.profile).first()
                if salon is None:
                    raise ValidationError({'salon': 'Create a salon first before adding services.'})
                serializer.save(salon=salon)
                return

            # If salon provided, ensure it belongs to this owner
            if salon.owner_id != user.profile.id:
                raise PermissionDenied('You cannot add services to a salon you do not own.')

        serializer.save()

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print(f"Booking Validation Errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'profile'):
            return Booking.objects.none()
        if user.profile.role == 'salon_owner':
            return Booking.objects.filter(salon__owner=user.profile)
        return Booking.objects.filter(user=user)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)
        
        # Create notifications with safety checks
        try:
            from ..models import Notification
            
            customer_name = getattr(self.request.user.profile, 'full_name', self.request.user.username) if hasattr(self.request.user, 'profile') else self.request.user.username
            
            # 1. Notify Owner
            if hasattr(booking.salon, 'owner') and booking.salon.owner.user:
                Notification.objects.create(
                    user=booking.salon.owner.user,
                    title="New Booking Request",
                    body=f"You have a new booking request from {customer_name} for {booking.service_type}.",
                    type="booking_request",
                    related_id=booking.id
                )
            
            # 2. Notify Customer (Confirmation of request)
            Notification.objects.create(
                user=self.request.user,
                title="Booking Sent",
                body=f"Your booking request for {booking.salon.name} has been sent and is awaiting approval.",
                type="booking_sent",
                related_id=booking.id
            )
        except Exception as e:
            # Notifications shouldn't break the booking creation
            print(f"Error creating notifications: {e}")

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        booking = serializer.save()
        new_status = booking.status
        
        if old_status != new_status:
            from ..models import Notification
            
            # If owner updates status, notify customer
            if self.request.user.profile.role == 'salon_owner':
                if new_status == 'confirmed':
                    title, body = "Booking Confirmed!", f"Your booking at {booking.salon.name} is confirmed for {booking.time_slot}."
                elif new_status == 'cancelled':
                    title, body = "Booking Cancelled", f"Your booking at {booking.salon.name} was unfortunately cancelled."
                elif new_status == 'completed':
                    title, body = "Service Completed", f"We hope you enjoyed your service at {booking.salon.name}! Please leave a review."
                else:
                    return

                Notification.objects.create(
                    user=booking.user,
                    title=title,
                    body=body,
                    type="booking_status_update",
                    related_id=booking.id
                )
            
            # If customer cancels, notify owner
            elif self.request.user == booking.user and new_status == 'cancelled':
                Notification.objects.create(
                    user=booking.salon.owner.user,
                    title="Booking Cancelled by Customer",
                    body=f"The booking for {booking.service_type} by {self.request.user.profile.full_name} has been cancelled.",
                    type="booking_cancelled",
                    related_id=booking.id
                )

class SalonStaffViewSet(viewsets.ModelViewSet):
    queryset = SalonStaff.objects.all()
    serializer_class = SalonStaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Owners can see all staff in their salons
        if hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            return SalonStaff.objects.filter(salon__owner=user.profile)
        # Others can only see active staff
        return SalonStaff.objects.filter(is_active=True)

    def perform_create(self, serializer):
        from ..models import User, Profile, Salon
        profile_id = self.request.data.get('profile')
        salon_id = self.request.data.get('salon')
        
        # If no salon provided in data, try to use owner's default salon
        salon_instance = None
        if salon_id:
            salon_instance = Salon.objects.get(id=salon_id)
        elif hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'salon_owner':
            salon_instance = self.request.user.profile.owned_salons.first()

        profile_instance = None
        if not profile_id:
            name = self.request.data.get('name')
            email = self.request.data.get('email_invite')
            if email:
                user, created = User.objects.get_or_create(email=email, defaults={'username': email})
                profile_instance, p_created = Profile.objects.get_or_create(user=user, defaults={'full_name': name, 'role': 'staff'})
        else:
            profile_instance = Profile.objects.get(id=profile_id)
            
        # Ensure we have a profile and salon before saving
        save_kwargs = {}
        if profile_instance:
            save_kwargs['profile'] = profile_instance
        if salon_instance:
            save_kwargs['salon'] = salon_instance
            
        serializer.save(**save_kwargs)

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        staff = self.get_object()
        ledger_entries = StaffLedger.objects.filter(staff=staff).order_by('-created_at')
        serializer = StaffLedgerSerializer(ledger_entries, many=True)
        return Response(serializer.data)

class EarningViewSet(viewsets.ModelViewSet):
    queryset = Earning.objects.all()
    serializer_class = EarningSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Earning.objects.filter(owner=self.request.user.profile).order_by('-date')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        
        user = request.user
        if not hasattr(user, 'profile'):
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
            
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        today_total = Earning.objects.filter(owner=user.profile, date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        week_total = Earning.objects.filter(owner=user.profile, date__gte=week_start).aggregate(Sum('amount'))['amount__sum'] or 0
        month_total = Earning.objects.filter(owner=user.profile, date__gte=month_start).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'today': float(today_total),
            'thisWeek': float(week_total),
            'thisMonth': float(month_total),
            'dailyBreakdown': {}, # Placeholder for future chart data
            'weeklyBreakdown': {},
        })

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Product.objects.filter(is_enabled=True)

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)

class LoyaltyViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def info(self, request):
        loyalty, created = LoyaltyPoints.objects.get_or_create(user=request.user)
        serializer = LoyaltyPointsSerializer(loyalty)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def transactions(self, request):
        transactions = LoyaltyTransaction.objects.filter(user=request.user).order_by('-created_at')
        serializer = LoyaltyTransactionSerializer(transactions, many=True)
        return Response(serializer.data)

class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role != 'salon_owner':
            return Response({'error': 'Only owners can access dashboard summary'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get owner's salon
        salon = Salon.objects.filter(owner=user.profile).first()
        if not salon:
            return Response({
                'todayBookingsCount': 0,
                'averageRating': 0.0,
                'upcomingBookings': [],
                'revenueSummary': {'thisMonth': 0, 'thisWeek': 0, 'today': 0, 'dailyBreakdown': {}, 'weeklyBreakdown': {}}
            })

        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Avg
        
        now = timezone.now()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        # Today's bookings
        today_bookings_count = Booking.objects.filter(salon=salon, booking_date__date=today).count()
        
        # Upcoming bookings
        upcoming_bookings = Booking.objects.filter(
            salon=salon, 
            booking_date__gte=now
        ).order_by('booking_date')[:5]
        
        # Average rating
        avg_rating = Review.objects.filter(salon=salon).aggregate(Avg('rating'))['rating__avg'] or 0.0
        
        # Revenue summary
        today_revenue = Earning.objects.filter(owner=user.profile, date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        week_revenue = Earning.objects.filter(owner=user.profile, date__gte=week_start).aggregate(Sum('amount'))['amount__sum'] or 0
        month_revenue = Earning.objects.filter(owner=user.profile, date__gte=month_start).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'todayBookingsCount': today_bookings_count,
            'averageRating': float(avg_rating),
            'upcomingBookings': BookingSerializer(upcoming_bookings, many=True).data,
            'revenueSummary': {
                'today': float(today_revenue),
                'thisWeek': float(week_revenue),
                'thisMonth': float(month_revenue),
                'dailyBreakdown': {}, # Could be implemented for charts
                'weeklyBreakdown': {},
            }
        })
    @action(detail=False, methods=['get'])
    def customer_summary(self, request):
        user = request.user
        
        # Loyalty Info
        from ..models import LoyaltyPoints, Booking, Notification
        loyalty, _ = LoyaltyPoints.objects.get_or_create(user=user)
        
        # Next upcoming booking
        from django.utils import timezone
        next_booking = Booking.objects.filter(
            user=user, 
            booking_date__gte=timezone.now(),
            status__in=['confirmed', 'pending']
        ).order_by('booking_date').first()
        
        # Recent bookings (for "Book Again")
        recent_bookings = Booking.objects.filter(
            user=user,
            status='completed'
        ).order_by('-booking_date')[:3]
        
        # Unread notifications
        unread_notifications_count = Notification.objects.filter(user=user, is_read=False).count()
        
        return Response({
            'loyalty': {
                'points': loyalty.points,
                'tier': loyalty.tier
            },
            'nextBooking': BookingSerializer(next_booking).data if next_booking else None,
            'recentBookings': BookingSerializer(recent_bookings, many=True).data,
            'unreadNotificationsCount': unread_notifications_count,
            'userName': user.profile.full_name if hasattr(user, 'profile') else user.username,
        })
