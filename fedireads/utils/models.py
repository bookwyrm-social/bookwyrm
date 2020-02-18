from django.db import models

from fedireads.settings import DOMAIN


class FedireadsModel(models.Model):
    content = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)

    @property
    def absolute_id(self):
        ''' constructs the absolute reference to any db object '''
        base_path = 'https://%s' % DOMAIN
        if self.user:
            base_path = self.user.absolute_id
        model_name = type(self).__name__
        return '%s/%s/%d' % (base_path, model_name, self.id)

    class Meta:
        abstract = True

