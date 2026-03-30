from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils import timezone
from ..models import (
    Profile, Salon, Booking, Earning, Review,
    SubscriptionPlan, SystemSetting, DisputeMessage
)

User = get_user_model()


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and hasattr(request.user, 'profile')
            and request.user.profile.role == 'admin'
        )


class AdminViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    # ─── DASHBOARD ────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        customers_count = Profile.objects.filter(role='customer').count()
        salons_count = Salon.objects.count()
        total_revenue = Earning.objects.aggregate(Sum('amount'))['amount__sum'] or 0
        disputes_count = DisputeMessage.objects.filter(is_resolved=False).count()

        recent_salons = Salon.objects.order_by('-created_at')[:5]
        recent_salons_data = [
            {'name': s.name, 'created_at': s.created_at}
            for s in recent_salons
        ]

        return Response({
            'customers': customers_count,
            'salons': salons_count,
            'revenue': float(total_revenue),
            'disputes': disputes_count,
            'recent_salons': recent_salons_data,
        })

    # ─── CUSTOMERS ────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def customers(self, request):
        profiles = Profile.objects.filter(role='customer').select_related('user')
        data = []
        for p in profiles:
            bookings_count = Booking.objects.filter(user=p.user).count()
            total_spent = Booking.objects.filter(
                user=p.user, status='completed'
            ).aggregate(Sum('price'))['price__sum'] or 0
            data.append({
                'id': p.user.id,
                'email': p.user.email,
                'full_name': p.full_name,
                'phone_number': p.phone_number,
                'status': 'active' if p.user.is_active else 'suspended',
                'created_at': p.created_at,
                'bookings_count': bookings_count,
                'total_spent': float(total_spent),
            })
        return Response(data)

    @action(detail=True, methods=['post'])
    def toggle_customer_status(self, request, pk=None):
        try:
            profile = Profile.objects.get(user__id=pk)
            user = profile.user
            user.is_active = not user.is_active
            user.save()
            return Response({'status': 'active' if user.is_active else 'suspended'})
        except Profile.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=404)

    # ─── SALONS ───────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def salons(self, request):
        salons = Salon.objects.all().select_related('owner', 'owner__user')
        data = []
        for s in salons:
            bookings_count = Booking.objects.filter(salon=s).count()
            data.append({
                'id': s.id,
                'name': s.name,
                'owner_name': s.owner.full_name if s.owner else 'Unknown',
                'owner_email': s.owner.user.email if s.owner and s.owner.user else 'Unknown',
                'status': 'active' if s.is_active else 'inactive',
                'is_verified': s.is_verified,
                'created_at': s.created_at,
                'bookings_count': bookings_count,
                'rating': s.rating,
                'address': s.address or '',
                'phone': s.phone or '',
            })
        return Response(data)

    @action(detail=True, methods=['post'])
    def salon_action(self, request, pk=None):
        try:
            salon = Salon.objects.get(id=pk)
            act = request.data.get('action')
            if act == 'verify':
                salon.is_verified = True
            elif act == 'reject':
                salon.is_verified = False
            elif act == 'ban':
                salon.is_active = False
            elif act == 'unban':
                salon.is_active = True
            salon.save()
            return Response({
                'id': salon.id,
                'is_active': salon.is_active,
                'is_verified': salon.is_verified,
            })
        except Salon.DoesNotExist:
            return Response({'error': 'Salon not found'}, status=404)

    # ─── ANALYTICS ────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        total_revenue = Earning.objects.aggregate(Sum('amount'))['amount__sum'] or 0
        new_users = Profile.objects.filter(role='customer').count()
        total_bookings = Booking.objects.count()

        top_salons = Salon.objects.annotate(
            booking_count=Count('bookings')
        ).order_by('-booking_count')[:5]

        top_salons_data = [
            {'id': s.id, 'name': s.name, 'rating': s.rating, 'booking_count': s.booking_count}
            for s in top_salons
        ]

        # Monthly revenue for chart (last 7 days)
        from django.db.models.functions import TruncDate
        revenue_trend = []
        for i in range(6, -1, -1):
            day = timezone.now().date() - timezone.timedelta(days=i)
            amount = Earning.objects.filter(date=day).aggregate(Sum('amount'))['amount__sum'] or 0
            revenue_trend.append({'name': day.strftime('%a'), 'revenue': float(amount)})

        return Response({
            'total_revenue': float(total_revenue),
            'new_users': new_users,
            'total_bookings': total_bookings,
            'top_salons': top_salons_data,
            'revenue_trend': revenue_trend,
        })

    # ─── PASSWORD ─────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'])
    def update_password(self, request):
        password = request.data.get('password')
        if not password or len(password) < 6:
            return Response({'error': 'Password must be at least 6 characters'}, status=400)
        user = request.user
        user.set_password(password)
        user.save()
        return Response({'message': 'Password updated successfully'})

    # ─── DISPUTES ─────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def disputes(self, request):
        """Return bookings that have dispute messages."""
        disputes_qs = DisputeMessage.objects.select_related(
            'booking', 'booking__user', 'booking__salon'
        ).order_by('-created_at')

        seen_bookings = {}
        for dm in disputes_qs:
            bid = dm.booking_id
            if bid not in seen_bookings:
                b = dm.booking
                seen_bookings[bid] = {
                    'id': dm.id,
                    'booking_id': bid,
                    'title': f"Dispute: {b.service_type}" if b else "Dispute",
                    'description': dm.message,
                    'customer': b.user.email if b else 'Unknown',
                    'salon': b.salon.name if b else 'Unknown',
                    'status': 'closed' if dm.is_resolved else 'open',
                    'priority': 'high' if not dm.is_resolved else 'low',
                    'created_at': dm.created_at,
                }

        # Also include bookings with no dispute messages but flagged by customer
        # For standalone disputes with no booking context
        standalone = DisputeMessage.objects.filter(booking__isnull=True).order_by('-created_at')
        for dm in standalone:
            seen_bookings[f'standalone_{dm.id}'] = {
                'id': dm.id,
                'booking_id': None,
                'title': 'General Dispute',
                'description': dm.message,
                'customer': 'Unknown',
                'salon': 'Unknown',
                'status': 'closed' if dm.is_resolved else 'open',
                'priority': 'medium',
                'created_at': dm.created_at,
            }

        return Response(list(seen_bookings.values()))

    @action(detail=True, methods=['post'])
    def resolve_dispute(self, request, pk=None):
        try:
            dm = DisputeMessage.objects.get(id=pk)
            dm.is_resolved = True
            dm.save()
            # Mark all messages in this booking as resolved
            if dm.booking:
                DisputeMessage.objects.filter(booking=dm.booking).update(is_resolved=True)
            return Response({'status': 'resolved'})
        except DisputeMessage.DoesNotExist:
            return Response({'error': 'Dispute not found'}, status=404)

    @action(detail=True, methods=['post'])
    def send_dispute_message(self, request, pk=None):
        """pk = booking_id or dispute_id. Send a message on a dispute."""
        message = request.data.get('message', '').strip()
        if not message:
            return Response({'error': 'Message is required'}, status=400)

        booking_id = request.data.get('booking_id')
        booking = None
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                pass

        dm = DisputeMessage.objects.create(
            booking=booking,
            sender_role='admin',
            message=message,
            is_resolved=False,
        )
        return Response({
            'id': dm.id,
            'message': dm.message,
            'sender_role': dm.sender_role,
            'created_at': dm.created_at,
        })

    @action(detail=True, methods=['get'])
    def dispute_messages(self, request, pk=None):
        """Get all messages for a booking's dispute thread."""
        messages = DisputeMessage.objects.filter(booking_id=pk).order_by('created_at')
        data = [
            {
                'id': m.id,
                'message': m.message,
                'sender_role': m.sender_role,
                'is_resolved': m.is_resolved,
                'created_at': m.created_at,
            }
            for m in messages
        ]
        return Response(data)

    # ─── SUBSCRIPTIONS ────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def subscription_plans(self, request):
        plans = SubscriptionPlan.objects.all()
        data = [
            {
                'id': p.id,
                'name': p.name,
                'price': str(p.price),
                'commission': str(p.commission),
                'max_staff': p.max_staff,
                'features': p.features,
                'is_active': p.is_active,
            }
            for p in plans
        ]
        return Response(data)

    @action(detail=False, methods=['post'])
    def create_plan(self, request):
        data = request.data
        plan = SubscriptionPlan.objects.create(
            name=data.get('name', 'New Plan'),
            price=data.get('price', 0),
            commission=data.get('commission', 0),
            max_staff=data.get('max_staff', 5),
            features=data.get('features', []),
        )
        return Response({'id': plan.id, 'name': plan.name}, status=201)

    @action(detail=True, methods=['post'])
    def update_plan(self, request, pk=None):
        try:
            plan = SubscriptionPlan.objects.get(id=pk)
            data = request.data
            plan.name = data.get('name', plan.name)
            plan.price = data.get('price', plan.price)
            plan.commission = data.get('commission', plan.commission)
            plan.max_staff = data.get('max_staff', plan.max_staff)
            plan.features = data.get('features', plan.features)
            plan.save()
            return Response({'status': 'updated', 'id': plan.id})
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=404)

    @action(detail=True, methods=['post'])
    def delete_plan(self, request, pk=None):
        try:
            plan = SubscriptionPlan.objects.get(id=pk)
            plan.delete()
            return Response({'status': 'deleted'})
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=404)

    # ─── SYSTEM SETTINGS ──────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def system_settings(self, request):
        defaults = [
            {'key': 'instant_booking', 'label': 'Instant Booking Mode', 'value': 'true'},
            {'key': 'push_notifications', 'label': 'Push Notifications', 'value': 'true'},
            {'key': 'loyalty_program', 'label': 'Loyalty Program Engine', 'value': 'true'},
            {'key': 'gift_cards', 'label': 'Gift Cards & Vouchers', 'value': 'false'},
            {'key': 'ai_recommendations', 'label': 'AI Stylist Recommendation', 'value': 'false'},
            {'key': 'review_moderation', 'label': 'Review Moderation (Manual)', 'value': 'true'},
            {'key': '2fa_enforcement', 'label': '2FA Enforcement', 'value': 'true'},
            {'key': 'ip_whitelisting', 'label': 'IP Whitelisting', 'value': 'false'},
        ]
        for d in defaults:
            SystemSetting.objects.get_or_create(key=d['key'], defaults={'label': d['label'], 'value': d['value']})

        settings_qs = SystemSetting.objects.all()
        data = [{'key': s.key, 'label': s.label, 'value': s.value == 'true'} for s in settings_qs]
        return Response(data)

    @action(detail=False, methods=['post'])
    def toggle_system_setting(self, request):
        key = request.data.get('key')
        if not key:
            return Response({'error': 'key is required'}, status=400)
        try:
            setting = SystemSetting.objects.get(key=key)
            setting.value = 'false' if setting.value == 'true' else 'true'
            setting.save()
            return Response({'key': setting.key, 'value': setting.value == 'true'})
        except SystemSetting.DoesNotExist:
            return Response({'error': 'Setting not found'}, status=404)

    @action(detail=False, methods=['get'])
    def system_stats(self, request):
        total_users = User.objects.count()
        total_bookings = Booking.objects.count()
        return Response({
            'status': 'operational',
            'total_users': total_users,
            'total_bookings': total_bookings,
            'db_connections': total_users + total_bookings,  # approximate
        })
