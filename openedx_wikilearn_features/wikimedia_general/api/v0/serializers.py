from rest_framework import serializers
from openedx_wikilearn_features.wikimedia_general.models import Topic


class TopicSerializer(serializers.ModelSerializer):
    """Serializer for Topic model"""
    
    class Meta:
        model = Topic
        fields = ['id', 'name', 'created', 'modified']
        read_only_fields = ['id', 'created', 'modified']
    
    def validate_name(self, value):
        """Ensure topic name is unique (case-insensitive)"""
        if Topic.objects.filter(name__iexact=value.strip()).exists():
            raise serializers.ValidationError("A topic with this name already exists.")
        return value.strip()
