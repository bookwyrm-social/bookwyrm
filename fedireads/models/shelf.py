''' puttin' books on shelves '''
from django.db import models

from .base_model import FedireadsModel


class Shelf(FedireadsModel):
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    editable = models.BooleanField(default=True)
    books = models.ManyToManyField(
        'Edition',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('shelf', 'book')
    )

    def get_remote_id(self):
        ''' shelf identifier instead of id '''
        base_path = self.user.remote_id
        return '%s/shelf/%s' % (base_path, self.identifier)

    class Meta:
        unique_together = ('user', 'identifier')


class ShelfBook(FedireadsModel):
    # many to many join table for books and shelves
    book = models.ForeignKey('Edition', on_delete=models.PROTECT)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)
    added_by = models.ForeignKey(
        'User',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )

    class Meta:
        unique_together = ('book', 'shelf')
