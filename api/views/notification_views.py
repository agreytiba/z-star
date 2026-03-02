from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Notification
from rest_framework import serializers

class AppNotificationSerializer(serializers.ModelSerializer):
    isRead = serializers.BooleanField(source='is_read')
    relatedId = serializers.UUIDField(source='related_id', required=False, allow_null=True)
    
    class Meta:
        model = Notification
        fields = ['id', 'user', 'title', 'body', 'type', 'relatedId', 'isRead', 'created_at']

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = AppNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'marked all as read'})
