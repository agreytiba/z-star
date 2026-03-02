from rest_framework import views, permissions, status
from rest_framework.response import Response
from ..models import FCMToken

class RegisterFCMTokenView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        device_type = request.data.get('device_type', 'android')
        
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_VALUE)

        FCMToken.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={'device_type': device_type}
        )
        
        return Response({'status': 'token registered'}, status=status.HTTP_200_OK)

    def delete(self, request):
        token = request.data.get('token')
        if token:
            FCMToken.objects.filter(token=token).delete()
        return Response({'status': 'token removed'}, status=status.HTTP_200_OK)
