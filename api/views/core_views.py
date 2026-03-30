"""
Core business views – Salons, Services, Bookings, Products, Reviews,
Loyalty, Dashboard, Earnings.

Performance improvements:
  • select_related / prefetch_related on every queryset
  • Pagination applied globally via DEFAULT_PAGINATION_CLASS in settings
  • Caching on read-heavy, rarely-changing endpoints (salon lists, dashboard)
  • DB aggregations done in one query instead of N loops
  • Notification creation is async-safe (failures never break the main action)
  • Structured logging instead of print()
"""

import logging

from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from ..models import (
    Salon, SalonService, SalonStaff, Booking, Review, SalonGallery,
    Product, LoyaltyPoints, LoyaltyTransaction, Earning, StaffLedger,
    Notification,
)
from ..serializers.auth_serializers import (
    SalonSerializer, SalonServiceSerializer, BookingSerializer,
    LoyaltyPointsSerializer, LoyaltyTransactionSerializer, SalonStaffSerializer,
    ProductSerializer, EarningSerializer, StaffLedgerSerializer,
    ReviewSerializer, SalonGallerySerializer,
)

logger = logging.getLogger('api')


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _create_notification(user, title, body, notif_type, related_id=None):
    """Fire-and-forget notification helper – errors are logged, never raised."""
    try:
        Notification.objects.create(
            user=user,
            title=title,
            body=body,
            type=notif_type,
            related_id=related_id,
        )
    except Exception as exc:
        logger.error('Notification creation failed: %s', exc)


# ─── SALONS ──────────────────────────────────────────────────────────────────

class SalonViewSet(viewsets.ModelViewSet):
    queryset         = Salon.objects.all()
    serializer_class = SalonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends  = [filters.SearchFilter, filters.OrderingFilter]
    search_fields    = ['name', 'description', 'address']
    ordering_fields  = ['rating', 'created_at', 'name']
    ordering         = ['-rating']

    def get_queryset(self):
        user = self.request.user
        qs = Salon.objects.select_related('owner', 'owner__user').prefetch_related('services', 'staff')

        if user.is_authenticated and hasattr(user, 'profile'):
            if user.profile.role == 'salon_owner':
                return qs.filter(owner=user.profile)

        return qs.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        """Cache the public salon list for 2 minutes to absorb burst reads."""
        cache_key = f'salons_list_{request.query_params.urlencode()}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        if not request.user.is_authenticated:
            cache.set(cache_key, response.data, timeout=120)
        return response

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user.profile)
        cache.delete_pattern('salons_list_*') if hasattr(cache, 'delete_pattern') else cache.clear()

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        salon = self.get_object()
        reviews = (
            Review.objects
            .filter(salon=salon)
            .select_related('reviewer')
            .order_by('-created_at')
        )
        page = self.paginate_queryset(reviews)
        if page is not None:
            serializer = ReviewSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)


# ─── SERVICES ────────────────────────────────────────────────────────────────

class SalonServiceViewSet(viewsets.ModelViewSet):
    queryset         = SalonService.objects.select_related('salon', 'salon__owner')
    serializer_class = SalonServiceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends  = [filters.SearchFilter]
    search_fields    = ['name', 'category', 'subcategory']

    def get_queryset(self):
        user = self.request.user
        qs = SalonService.objects.select_related('salon', 'salon__owner')
        if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            return qs.filter(salon__owner=user.profile)
        return qs.filter(is_available=True)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            salon = serializer.validated_data.get('salon')
            if salon is None:
                salon = Salon.objects.filter(owner=user.profile).first()
                if salon is None:
                    raise ValidationError({'salon': 'Create a salon first before adding services.'})
                serializer.save(salon=salon)
                return
            if salon.owner_id != user.profile.id:
                raise PermissionDenied('You cannot add services to a salon you do not own.')
        serializer.save()


# ─── BOOKINGS ────────────────────────────────────────────────────────────────

class BookingViewSet(viewsets.ModelViewSet):
    queryset         = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends  = [filters.OrderingFilter]
    ordering_fields  = ['booking_date', 'created_at', 'status']
    ordering         = ['-booking_date']

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'profile'):
            return Booking.objects.none()

        base = Booking.objects.select_related(
            'user', 'salon', 'salon__owner', 'staff', 'staff__profile'
        )
        if user.profile.role == 'salon_owner':
            return base.filter(salon__owner=user.profile)
        return base.filter(user=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Booking validation errors: %s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)

        customer_name = (
            self.request.user.profile.full_name
            if hasattr(self.request.user, 'profile')
            else self.request.user.username
        )

        # Notify salon owner
        if hasattr(booking.salon, 'owner') and booking.salon.owner.user:
            _create_notification(
                user=booking.salon.owner.user,
                title='New Booking Request',
                body=f'New booking from {customer_name} for {booking.service_type}.',
                notif_type='booking_request',
                related_id=booking.id,
            )

        # Confirm to customer
        _create_notification(
            user=self.request.user,
            title='Booking Sent',
            body=f'Your booking at {booking.salon.name} is awaiting approval.',
            notif_type='booking_sent',
            related_id=booking.id,
        )

    def perform_update(self, serializer):
        instance   = self.get_object()
        old_status = instance.status
        booking    = serializer.save()
        new_status = booking.status

        if old_status == new_status:
            return

        user = self.request.user
        if hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            messages = {
                'confirmed': ('Booking Confirmed!', f'Your booking at {booking.salon.name} for {booking.time_slot} is confirmed.'),
                'cancelled':  ('Booking Cancelled', f'Your booking at {booking.salon.name} was cancelled.'),
                'completed':  ('Service Completed', f'Enjoyed your service at {booking.salon.name}? Leave a review!'),
            }
            if new_status in messages:
                title, body = messages[new_status]
                _create_notification(booking.user, title, body, 'booking_status_update', booking.id)

        elif user == booking.user and new_status == 'cancelled':
            _create_notification(
                booking.salon.owner.user,
                'Booking Cancelled by Customer',
                f'{user.profile.full_name if hasattr(user, "profile") else user.email} cancelled {booking.service_type}.',
                'booking_cancelled',
                booking.id,
            )


# ─── STAFF ───────────────────────────────────────────────────────────────────

class SalonStaffViewSet(viewsets.ModelViewSet):
    queryset         = SalonStaff.objects.select_related('salon', 'salon__owner', 'profile', 'profile__user')
    serializer_class = SalonStaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = SalonStaff.objects.select_related('salon', 'profile', 'profile__user')
        if hasattr(user, 'profile') and user.profile.role == 'salon_owner':
            return qs.filter(salon__owner=user.profile)
        return qs.filter(is_active=True)

    def perform_create(self, serializer):
        from ..models import User as UserModel, Profile, Salon

        profile_id    = self.request.data.get('profile')
        salon_id      = self.request.data.get('salon')
        salon_instance = None

        if salon_id:
            salon_instance = Salon.objects.filter(id=salon_id).first()
        elif hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'salon_owner':
            salon_instance = self.request.user.profile.owned_salons.first()

        profile_instance = None
        if not profile_id:
            name  = self.request.data.get('name')
            email = self.request.data.get('email_invite')
            if email:
                user, _ = UserModel.objects.get_or_create(
                    email=email,
                    defaults={'username': email},
                )
                profile_instance, _ = Profile.objects.get_or_create(
                    user=user,
                    defaults={'full_name': name, 'role': 'staff'},
                )
        else:
            profile_instance = Profile.objects.filter(id=profile_id).first()

        save_kwargs = {}
        if profile_instance:
            save_kwargs['profile'] = profile_instance
        if salon_instance:
            save_kwargs['salon'] = salon_instance
        serializer.save(**save_kwargs)

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        staff = self.get_object()
        entries = StaffLedger.objects.filter(staff=staff).order_by('-created_at')
        page = self.paginate_queryset(entries)
        if page is not None:
            return self.get_paginated_response(StaffLedgerSerializer(page, many=True).data)
        return Response(StaffLedgerSerializer(entries, many=True).data)


# ─── EARNINGS ────────────────────────────────────────────────────────────────

class EarningViewSet(viewsets.ModelViewSet):
    queryset         = Earning.objects.all()
    serializer_class = EarningSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering         = ['-date']

    def get_queryset(self):
        return Earning.objects.filter(owner=self.request.user.profile).order_by('-date')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        user = request.user
        if not hasattr(user, 'profile'):
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        today       = timezone.now().date()
        week_start  = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        def _agg(qs):
            return float(qs.aggregate(total=Sum('amount'))['total'] or 0)

        base = Earning.objects.filter(owner=user.profile)
        return Response({
            'today':     _agg(base.filter(date=today)),
            'thisWeek':  _agg(base.filter(date__gte=week_start)),
            'thisMonth': _agg(base.filter(date__gte=month_start)),
        })


# ─── PRODUCTS ────────────────────────────────────────────────────────────────

class ProductViewSet(viewsets.ModelViewSet):
    queryset         = Product.objects.select_related('salon').filter(is_enabled=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends  = [filters.SearchFilter]
    search_fields    = ['name', 'category']


# ─── REVIEWS ─────────────────────────────────────────────────────────────────

class IsReviewerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.reviewer == request.user


class ReviewViewSet(viewsets.ModelViewSet):
    queryset         = Review.objects.select_related('salon', 'reviewer', 'booking')
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsReviewerOrReadOnly]
    ordering         = ['-created_at']

    def perform_create(self, serializer):
        review = serializer.save(reviewer=self.request.user)
        self._update_salon_stats(review.salon)

    def perform_update(self, serializer):
        review = serializer.save()
        self._update_salon_stats(review.salon)

    def perform_destroy(self, instance):
        salon = instance.salon
        instance.delete()
        self._update_salon_stats(salon)

    def _update_salon_stats(self, salon):
        stats = Review.objects.filter(salon=salon).aggregate(
            avg_rating=Avg('rating'),
            review_cnt=Count('id'),
        )
        salon.rating       = stats['avg_rating'] or 0.0
        salon.review_count = stats['review_cnt']
        salon.save(update_fields=['rating', 'review_count'])

    @action(detail=True, methods=['post', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def respond(self, request, pk=None):
        review = self.get_object()
        user   = request.user

        is_owner         = review.salon.owner.user == user
        is_assigned_staff = (
            review.booking
            and review.booking.staff
            and review.booking.staff.profile.user == user
        )

        if not (is_owner or is_assigned_staff):
            raise PermissionDenied('Only the salon owner or assigned staff can respond.')

        response_text = (
            request.data.get('response')
            or request.data.get('staff_response')
            or request.data.get('owner_response')
        )
        if not response_text:
            return Response({'error': 'Response text is required'}, status=status.HTTP_400_BAD_REQUEST)

        if is_owner:
            review.owner_response = response_text
        if is_assigned_staff:
            review.staff_response = response_text
        review.save(update_fields=['owner_response', 'staff_response'])

        return Response(ReviewSerializer(review).data)


# ─── LOYALTY ─────────────────────────────────────────────────────────────────

class LoyaltyViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def info(self, request):
        loyalty, _ = LoyaltyPoints.objects.get_or_create(user=request.user)
        return Response(LoyaltyPointsSerializer(loyalty).data)

    @action(detail=False, methods=['get'])
    def transactions(self, request):
        txns = (
            LoyaltyTransaction.objects
            .filter(user=request.user)
            .order_by('-created_at')
        )
        page = self.paginate_queryset(txns) if hasattr(self, 'paginate_queryset') else None
        if page is not None:
            return self.get_paginated_response(LoyaltyTransactionSerializer(page, many=True).data)
        return Response(LoyaltyTransactionSerializer(txns, many=True).data)


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        user = request.user
        if not hasattr(user, 'profile') or user.profile.role != 'salon_owner':
            return Response(
                {'error': 'Only salon owners can access the dashboard summary'},
                status=status.HTTP_403_FORBIDDEN,
            )

        cache_key = f'dashboard_summary_{user.id}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        salon = (
            Salon.objects
            .filter(owner=user.profile)
            .prefetch_related('bookings', 'reviews')
            .first()
        )
        if not salon:
            empty = {
                'todayBookingsCount': 0,
                'averageRating':      0.0,
                'upcomingBookings':   [],
                'revenueSummary':     {'today': 0, 'thisWeek': 0, 'thisMonth': 0},
            }
            return Response(empty)

        now         = timezone.now()
        today       = now.date()
        week_start  = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        # All aggregations in as few queries as possible
        today_count = Booking.objects.filter(salon=salon, booking_date__date=today).count()
        avg_rating  = Review.objects.filter(salon=salon).aggregate(r=Avg('rating'))['r'] or 0.0
        upcoming    = (
            Booking.objects
            .filter(salon=salon, booking_date__gte=now)
            .select_related('user')
            .order_by('booking_date')[:5]
        )

        def _rev(qs_filter):
            return float(
                Earning.objects.filter(owner=user.profile, **qs_filter)
                .aggregate(t=Sum('amount'))['t'] or 0
            )

        data = {
            'todayBookingsCount': today_count,
            'averageRating':      round(float(avg_rating), 2),
            'upcomingBookings':   BookingSerializer(upcoming, many=True).data,
            'revenueSummary': {
                'today':     _rev({'date': today}),
                'thisWeek':  _rev({'date__gte': week_start}),
                'thisMonth': _rev({'date__gte': month_start}),
            },
        }
        cache.set(cache_key, data, timeout=60)  # 1-minute cache
        return Response(data)

    @action(detail=False, methods=['get'])
    def customer_summary(self, request):
        user = request.user

        loyalty, _ = LoyaltyPoints.objects.get_or_create(user=user)
        now = timezone.now()

        next_booking = (
            Booking.objects
            .filter(user=user, booking_date__gte=now, status__in=['confirmed', 'pending'])
            .select_related('salon')
            .order_by('booking_date')
            .first()
        )
        recent_bookings = (
            Booking.objects
            .filter(user=user, status='completed')
            .select_related('salon')
            .order_by('-booking_date')[:3]
        )
        unread_count = Notification.objects.filter(user=user, is_read=False).count()

        return Response({
            'loyalty': {
                'points': loyalty.points,
                'tier':   loyalty.tier,
            },
            'nextBooking':              BookingSerializer(next_booking).data if next_booking else None,
            'recentBookings':           BookingSerializer(recent_bookings, many=True).data,
            'unreadNotificationsCount': unread_count,
            'userName':                 user.profile.full_name if hasattr(user, 'profile') else user.username,
        })
