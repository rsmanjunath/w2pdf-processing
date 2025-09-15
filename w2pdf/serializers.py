from rest_framework import serializers

class W2PDFUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
