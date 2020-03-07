''' puttin' books on shelves '''
from django.db import models

from fedireads.utils.models import FedireadsModel


class Shelf(FedireadsModel):
    name = models.CharField(max_length=100)
    identifier = models.CharField(max_length=100)
    user = models.ForeignKey('User', on_delete=models.PROTECT)
    editable = models.BooleanField(default=True)
    books = models.ManyToManyField(
        'Book',
        symmetrical=False,
        through='ShelfBook',
        through_fields=('shelf', 'book')
    )

    @property
    def absolute_id(self):
        ''' use shelf identifier as absolute id '''
        base_path = self.user.absolute_id
        model_name = type(self).__name__.lower()
        return '%s/%s/%s' % (base_path, model_name, self.identifier)

    class Meta:
        unique_together = ('user', 'identifier')


class ShelfBook(FedireadsModel):
    # many to many join table for books and shelves
    book = models.ForeignKey('Book', on_delete=models.PROTECT)
    shelf = models.ForeignKey('Shelf', on_delete=models.PROTECT)
    added_by = models.ForeignKey(
        'User',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )

    class Meta:
        unique_together = ('book', 'shelf')
