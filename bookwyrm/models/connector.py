''' manages interfaces with external sources of book data '''
from django.db import models
from bookwyrm.connectors.settings import CONNECTORS

from .base_model import BookWyrmModel


ConnectorFiles = models.TextChoices('ConnectorFiles', CONNECTORS)
class Connector(BookWyrmModel):
    ''' book data source connectors '''
    identifier = models.CharField(max_length=255, unique=True)
    priority = models.IntegerField(default=2)
    name = models.CharField(max_length=255, null=True, blank=True)
    local = models.BooleanField(default=False)
    connector_file = models.CharField(
        max_length=255,
        choices=ConnectorFiles.choices
    )
    api_key = models.CharField(max_length=255, null=True, blank=True)

    base_url = models.CharField(max_length=255)
    books_url = models.CharField(max_length=255)
    covers_url = models.CharField(max_length=255)
    search_url = models.CharField(max_length=255, null=True, blank=True)

    politeness_delay = models.IntegerField(null=True, blank=True) #seconds
    max_query_count = models.IntegerField(null=True, blank=True)
    # how many queries executed in a unit of time, like a day
    query_count = models.IntegerField(default=0)
    # when to reset the query count back to 0 (ie, after 1 day)
    query_count_expiry = models.DateTimeField(auto_now_add=True, blank=True)

    class Meta:
        ''' check that there's code to actually use this connector '''
        constraints = [
            models.CheckConstraint(
                check=models.Q(connector_file__in=ConnectorFiles),
                name='connector_file_valid'
            )
        ]

    def __str__(self):
        return "{} ({})".format(
            self.identifier,
            self.id,
        )
