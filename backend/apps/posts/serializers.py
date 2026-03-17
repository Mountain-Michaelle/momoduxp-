from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'status')

    def validate_scheduled_for(self, value):
        # Add logic to ensure date is in the future
        return value