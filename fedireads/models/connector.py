''' manages interfaces with external sources of book data '''
from django.db import models
from fedireads.connectors.settings import CONNECTORS

from .base_model import FedireadsModel


ConnectorFiles = models.TextChoices('ConnectorFiles', CONNECTORS)
class Connector(FedireadsModel):
    ''' book data source connectors '''
    identifier = models.CharField(max_length=255, unique=True)
    priority = models.IntegerField(default=2)
    name = models.CharField(max_length=255, null=True)
    local = models.BooleanField(default=False)
    connector_file = models.CharField(
        max_length=255,
        choices=ConnectorFiles.choices
    )
    api_key = models.CharField(max_length=255, null=True)

    base_url = models.CharField(max_length=255)
    books_url = models.CharField(max_length=255)
    covers_url = models.CharField(max_length=255)
    search_url = models.CharField(max_length=255, null=True)

    politeness_delay = models.IntegerField(null=True) #seconds
    max_query_count = models.IntegerField(null=True)
    # how many queries executed in a unit of time, like a day
    query_count = models.IntegerField(default=0)
    # when to reset the query count back to 0 (ie, after 1 day)
    query_count_expiry = models.DateTimeField(auto_now_add=True)

    class Meta:
        ''' check that there's code to actually use this connector '''
        constraints = [
            models.CheckConstraint(
                check=models.Q(connector_file__in=ConnectorFiles),
                name='connector_file_valid'
            )
        ]
