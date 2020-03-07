''' base model with default fields '''
from django.db import models

from fedireads.settings import DOMAIN

# TODO maybe this should be in /models?
class FedireadsModel(models.Model):
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    @property
    def absolute_id(self):
        ''' constructs the absolute reference to any db object '''
        base_path = 'https://%s' % DOMAIN
        if hasattr(self, 'user'):
            base_path = self.user.absolute_id
        model_name = type(self).__name__.lower()
        return '%s/%s/%d' % (base_path, model_name, self.id)

    class Meta:
        abstract = True

