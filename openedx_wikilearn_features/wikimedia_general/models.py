from django.db import models

from model_utils.models import TimeStampedModel

class Topic(TimeStampedModel):
    """
    Model for storing the names of possible Topics that a course can have.
    """
    class Meta:
        app_label = "wikimedia_general"

    name = models.CharField(max_length=250)
    
    def __str__(self):
        return self.name
