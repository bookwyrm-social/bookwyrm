''' base model with default fields '''
from django.db import models

from fedireads.settings import DOMAIN

class FedireadsModel(models.Model):
    ''' fields and functions for every model '''
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    @property
    def absolute_id(self):
        ''' constructs the absolute reference to any db object '''
        if self.remote_id:
            return self.remote_id

        base_path = 'https://%s' % DOMAIN
        if hasattr(self, 'user'):
            base_path = self.user.absolute_id
        model_name = type(self).__name__.lower()
        return '%s/%s/%d' % (base_path, model_name, self.id)

    class Meta:
        abstract = True
