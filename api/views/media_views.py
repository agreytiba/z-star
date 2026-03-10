from rest_framework import views, permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
import os
from django.conf import settings
from django.core.files.storage import default_storage

class ImageUploadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        file_obj = request.data.get('file')
        category = request.data.get('category', 'general')
        
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure only a single file is handled (not a list)
        if isinstance(file_obj, list):
            file_obj = file_obj[0]

        path = default_storage.save(f'{category}/{file_obj.name}', file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + path)
        
        return Response({'url': url}, status=status.HTTP_201_CREATED)
