''' using another bookwyrm instance as a source of book data '''
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from bookwyrm import activitypub, models
from .abstract_connector import AbstractConnector, SearchResult
from .abstract_connector import get_data


class Connector(AbstractConnector):
    ''' interact with other instances '''

    def update_from_mappings(self, obj, data, mappings):
        ''' serialize book data into a model '''
        if self.is_work_data(data):
            work_data = activitypub.Work(**data)
            return work_data.to_model(models.Work, instance=obj)
        edition_data = activitypub.Edition(**data)
        return edition_data.to_model(models.Edition, instance=obj)


    def get_remote_id_from_data(self, data):
        return data.get('id')


    def is_work_data(self, data):
        return data.get('type') == 'Work'


    def get_edition_from_work_data(self, data):
        ''' we're served a list of edition urls '''
        path = data['editions'][0]
        return get_data(path)


    def get_work_from_edition_date(self, data):
        return get_data(data['work'])


    def get_authors_from_data(self, data):
        ''' load author data '''
        for author_id in data.get('authors', []):
            try:
                yield models.Author.objects.get(origin_id=author_id)
            except models.Author.DoesNotExist:
                continue
            data = get_data(author_id)
            author_data = activitypub.Author(**data)
            yield author_data.to_model(models.Author)


    def get_cover_from_data(self, data):
        pass


    def parse_search_data(self, data):
        return data


    def format_search_result(self, search_result):
        return SearchResult(**search_result)


    def expand_book_data(self, book):
        work = book
        # go from the edition to the work, if necessary
        if isinstance(book, models.Edition):
            work = book.parent_work

        # it may be that we actually want to request this url
        editions_url = '%s/editions?page=true' % work.remote_id
        edition_options = get_data(editions_url)
        for edition_data in edition_options['orderedItems']:
            with transaction.atomic():
                edition = self.create_book(
                    edition_data['id'],
                    edition_data,
                    models.Edition
                )
                edition.parent_work = work
                edition.save()
            if not edition.authors.exists() and work.authors.exists():
                edition.authors.set(work.authors.all())
