from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import SalonStaff, Booking, StaffLedger, Review, Profile
from ..serializers.auth_serializers import (
    BookingSerializer, SalonStaffSerializer, StaffLedgerSerializer, ReviewSerializer
)

class StaffViewSet(viewsets.ModelViewSet):
    queryset = SalonStaff.objects.all()
    serializer_class = SalonStaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SalonStaff.objects.filter(profile__user=self.request.user)

    @action(detail=False, methods=['get'])
    def current(self, request):
        staff = SalonStaff.objects.filter(profile__user=request.user).first()
        if not staff:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SalonStaffSerializer(staff).data)

    @action(detail=False, methods=['get'])
    def bookings(self, request):
        staff = SalonStaff.objects.filter(profile__user=request.user).first()
        if not staff:
            return Response([])
        bookings = Booking.objects.filter(staff=staff).order_by('booking_date')
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def earnings(self, request):
        staff = SalonStaff.objects.filter(profile__user=request.user).first()
        if not staff:
            return Response([])
        ledger = StaffLedger.objects.filter(staff=staff).order_by('-created_at')
        serializer = StaffLedgerSerializer(ledger, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def reviews(self, request):
        staff = SalonStaff.objects.filter(profile__user=request.user).first()
        if not staff:
            return Response([])
        reviews = Review.objects.filter(booking__staff=staff).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)
