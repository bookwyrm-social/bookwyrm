""" access the activity stores stored in redis """
from abc import ABC, abstractmethod
import redis

from bookwyrm import settings

r = redis.from_url(settings.REDIS_ACTIVITY_URL)


class RedisStore(ABC):
    """sets of ranked, related objects, like statuses for a user's feed"""

    max_length = settings.MAX_STREAM_LENGTH

    def get_value(self, obj):
        """the object and rank"""
        return {obj.id: self.get_rank(obj)}

    def add_object_to_stores(self, obj, stores, execute=True):
        """add an object to a given set of stores"""
        value = self.get_value(obj)
        # we want to do this as a bulk operation, hence "pipeline"
        pipeline = r.pipeline()
        for store in stores:
            # add the status to the feed
            pipeline.zadd(store, value)
            # trim the store
            if self.max_length:
                pipeline.zremrangebyrank(store, 0, -1 * self.max_length)
        if not execute:
            return pipeline
        # and go!
        return pipeline.execute()

    # pylint: disable=no-self-use
    def remove_object_from_stores(self, obj, stores):
        """remove an object from all stores"""
        # if the stores are provided, the object can just be an id
        if stores and isinstance(obj, int):
            obj_id = obj
        else:
            obj_id = obj.id
        pipeline = r.pipeline()
        for store in stores:
            pipeline.zrem(store, -1, obj_id)
        pipeline.execute()

    def bulk_add_objects_to_store(self, objs, store):
        """add a list of objects to a given store"""
        pipeline = r.pipeline()
        for obj in objs[: self.max_length]:
            pipeline.zadd(store, self.get_value(obj))
        if objs and self.max_length:
            pipeline.zremrangebyrank(store, 0, -1 * self.max_length)
        pipeline.execute()

    def bulk_remove_objects_from_store(self, objs, store):
        """remove a list of objects from a given store"""
        pipeline = r.pipeline()
        for obj in objs[: self.max_length]:
            pipeline.zrem(store, -1, obj.id)
        pipeline.execute()

    def get_store(self, store, **kwargs):  # pylint: disable=no-self-use
        """load the values in a store"""
        return r.zrevrange(store, 0, -1, **kwargs)

    def populate_store(self, store):
        """go from zero to a store"""
        pipeline = r.pipeline()
        queryset = self.get_objects_for_store(store)

        for obj in queryset[: self.max_length]:
            pipeline.zadd(store, self.get_value(obj))

        # only trim the store if objects were added
        if queryset.exists() and self.max_length:
            pipeline.zremrangebyrank(store, 0, -1 * self.max_length)
        pipeline.execute()

    @abstractmethod
    def get_objects_for_store(self, store):
        """a queryset of what should go in a store, used for populating it"""

    @abstractmethod
    def get_rank(self, obj):
        """how to rank an object"""
