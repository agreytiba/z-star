from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
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

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'profile'):
            return Booking.objects.none()
        if user.profile.role == 'salon_owner':
            return Booking.objects.filter(salon__owner=user.profile)
        return Booking.objects.filter(user=user)

    def perform_create(self, serializer):
        # Additional logic for loyalty points could go here or in a signal
        serializer.save(user=self.request.user)

class SalonStaffViewSet(viewsets.ModelViewSet):
    queryset = SalonStaff.objects.all()
    serializer_class = SalonStaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Owners can see all staff in their salons
        if user.profile.role == 'salon_owner':
            return SalonStaff.objects.filter(salon__owner=user.profile)
        # Others can only see active staff
        return SalonStaff.objects.filter(is_active=True)

    def perform_create(self, serializer):
        from ..models import User, Profile
        # If profile isn't provided as ID, check for name/email
        profile_id = self.request.data.get('profile')
        if not profile_id:
            name = self.request.data.get('name')
            email = self.request.data.get('email_invite')
            if email:
                user, created = User.objects.get_or_create(email=email, defaults={'username': email})
                profile, p_created = Profile.objects.get_or_create(user=user, defaults={'full_name': name, 'role': 'staff'})
                serializer.save(profile=profile)
            else:
                # Handle error or use a default profile logic
                serializer.save()
        else:
            serializer.save()

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
        
        user = request.user
        today = timezone.now().date()
        
        # In a real app, you'd calculate week/month start
        
        today_total = Earning.objects.filter(owner=user.profile, date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'today': float(today_total),
            'thisWeek': float(today_total), # placeholder
            'thisMonth': float(today_total), # placeholder
            'dailyBreakdown': {},
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
        if user.profile.role != 'salon_owner':
            return Response({'error': 'Only owners can access dashboard summary'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get owner's salon
        salon = Salon.objects.filter(owner=user.profile).first()
        if not salon:
            return Response({
                'todayBookingsCount': 0,
                'averageRating': 0.0,
                'upcomingBookings': [],
                'revenueSummary': {'thisMonth': 0, 'thisWeek': 0, 'today': 0}
            })

        # Today's bookings
        from django.utils import timezone
        today = timezone.now().date()
        today_bookings = Booking.objects.filter(salon=salon, booking_date__date=today)
        
        # Upcoming bookings
        upcoming_bookings = Booking.objects.filter(salon=salon, booking_date__gte=timezone.now()).order_by('booking_date')[:5]
        
        # Revenue (conceptual)
        # In a real app, you'd aggregate from Earning model
        from ..models import Earning
        from django.db.models import Sum
        
        today_revenue = Earning.objects.filter(owner=user.profile, date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # ... more complex aggregation for week/month if needed
        
        return Response({
            'todayBookingsCount': today_bookings.count(),
            'averageRating': float(salon.rating),
            'upcomingBookings': BookingSerializer(upcoming_bookings, many=True).data,
            'revenueSummary': {
                'today': float(today_revenue),
                'thisWeek': float(today_revenue), # placeholder
                'thisMonth': float(today_revenue), # placeholder
            }
        })
