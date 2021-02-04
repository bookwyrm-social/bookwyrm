''' lists of objects '''
from django.core.paginator import Paginator

from bookwyrm import activitypub
from bookwyrm.settings import PAGE_LENGTH
from . import ActivitypubMixin, ObjectMixin, generate_activity


class OrderedCollectionPageMixin(ObjectMixin):
    ''' just the paginator utilities, so you don't HAVE to
        override ActivitypubMixin's to_activity (ie, for outbox) '''
    @property
    def collection_remote_id(self):
        ''' this can be overriden if there's a special remote id, ie outbox '''
        return self.remote_id


    def to_ordered_collection(self, queryset, \
            remote_id=None, page=False, collection_only=False, **kwargs):
        ''' an ordered collection of whatevers '''
        if not queryset.ordered:
            raise RuntimeError('queryset must be ordered')

        remote_id = remote_id or self.remote_id
        if page:
            return to_ordered_collection_page(
                queryset, remote_id, **kwargs)

        if collection_only or not hasattr(self, 'activity_serializer'):
            serializer = activitypub.OrderedCollection
            activity = {}
        else:
            serializer = self.activity_serializer
            # a dict from the model fields
            activity = generate_activity(self)

        if remote_id:
            activity['id'] = remote_id

        paginated = Paginator(queryset, PAGE_LENGTH)
        # add computed fields specific to orderd collections
        activity['totalItems'] = paginated.count
        activity['first'] = '%s?page=1' % remote_id
        activity['last'] = '%s?page=%d' % (remote_id, paginated.num_pages)

        return serializer(**activity).serialize()


# pylint: disable=unused-argument
def to_ordered_collection_page(
        queryset, remote_id, id_only=False, page=1, **kwargs):
    ''' serialize and pagiante a queryset '''
    paginated = Paginator(queryset, PAGE_LENGTH)

    activity_page = paginated.page(page)
    if id_only:
        items = [s.remote_id for s in activity_page.object_list]
    else:
        items = [s.to_activity() for s in activity_page.object_list]

    prev_page = next_page = None
    if activity_page.has_next():
        next_page = '%s?page=%d' % (remote_id, activity_page.next_page_number())
    if activity_page.has_previous():
        prev_page = '%s?page=%d' % \
                (remote_id, activity_page.previous_page_number())
    return activitypub.OrderedCollectionPage(
        id='%s?page=%s' % (remote_id, page),
        partOf=remote_id,
        orderedItems=items,
        next=next_page,
        prev=prev_page
    ).serialize()


class OrderedCollectionMixin(OrderedCollectionPageMixin):
    ''' extends activitypub models to work as ordered collections '''
    @property
    def collection_queryset(self):
        ''' usually an ordered collection model aggregates a different model '''
        raise NotImplementedError('Model must define collection_queryset')

    activity_serializer = activitypub.OrderedCollection

    def to_activity(self, **kwargs):
        ''' an ordered collection of the specified model queryset  '''
        return self.to_ordered_collection(self.collection_queryset, **kwargs)


class CollectionItemMixin(ActivitypubMixin):
    ''' for items that are part of an (Ordered)Collection '''
    activity_serializer = activitypub.Add
    object_field = collection_field = None

    def to_add_activity(self):
        ''' AP for shelving a book'''
        object_field = getattr(self, self.object_field)
        collection_field = getattr(self, self.collection_field)
        return activitypub.Add(
            id='%s#add' % self.remote_id,
            actor=self.user.remote_id,
            object=object_field.to_activity(),
            target=collection_field.remote_id
        ).serialize()

    def to_remove_activity(self):
        ''' AP for un-shelving a book'''
        object_field = getattr(self, self.object_field)
        collection_field = getattr(self, self.collection_field)
        return activitypub.Remove(
            id='%s#remove' % self.remote_id,
            actor=self.user.remote_id,
            object=object_field.to_activity(),
            target=collection_field.remote_id
        ).serialize()
