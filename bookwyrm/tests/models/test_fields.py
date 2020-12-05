''' testing models '''
from collections import namedtuple

from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from bookwyrm.models import fields

class ActivitypubFields(TestCase):
    def test_validate_remote_id(self):
        self.assertIsNone(fields.validate_remote_id(
            'http://www.example.com'
        ))
        self.assertIsNone(fields.validate_remote_id(
            'https://www.example.com'
        ))
        self.assertIsNone(fields.validate_remote_id(
            'http://example.com/dlfjg-23/x'
        ))
        self.assertRaises(
            ValidationError, fields.validate_remote_id,
            'http:/example.com/dlfjg-23/x'
        )
        self.assertRaises(
            ValidationError, fields.validate_remote_id,
            'www.example.com/dlfjg-23/x'
        )
        self.assertRaises(
            ValidationError, fields.validate_remote_id,
            'http://www.example.com/dlfjg 23/x'
        )

    def test_activitypub_field_mixin(self):
        instance = fields.ActivitypubFieldMixin()
        self.assertEqual(instance.field_to_activity('fish'), 'fish')
        self.assertEqual(instance.field_from_activity('fish'), 'fish')

        instance = fields.ActivitypubFieldMixin(
            activitypub_wrapper='endpoints', activitypub_field='outbox'
        )
        self.assertEqual(
            instance.field_to_activity('fish'),
            {'outbox': 'fish'}
        )
        self.assertEqual(
            instance.field_from_activity({'outbox': 'fish'}),
            'fish'
        )
        self.assertEqual(instance.get_activitypub_field(), 'endpoints')

        instance = fields.ActivitypubFieldMixin()
        instance.name = 'snake_case_name'
        self.assertEqual(instance.get_activitypub_field(), 'snakeCaseName')

    def test_remote_id_field(self):
        instance = fields.RemoteIdField()
        self.assertEqual(instance.max_length, 255)

        with self.assertRaises(ValidationError):
            instance.run_validators('http://www.example.com/dlfjg 23/x')

    def test_username_field(self):
        instance = fields.UsernameField()
        self.assertEqual(instance.activitypub_field, 'preferredUsername')
        self.assertEqual(instance.max_length, 150)
        self.assertEqual(instance.unique, True)
        with self.assertRaises(ValidationError):
            instance.run_validators('one two')
            instance.run_validators('a*&')
            instance.run_validators('trailingwhite ')
        self.assertIsNone(instance.run_validators('aksdhf'))

        self.assertEqual(instance.field_to_activity('test@example.com'), 'test')

    def test_foreign_key(self):
        instance = fields.ForeignKey('User', on_delete=models.CASCADE)
        Serializable = namedtuple('Serializable', ('to_activity', 'remote_id'))
        item = Serializable(lambda: {'a': 'b'}, 'https://e.b/c')
        self.assertEqual(instance.field_to_activity(item), 'https://e.b/c')

    def test_one_to_one_field(self):
        instance = fields.OneToOneField('User', on_delete=models.CASCADE)
        Serializable = namedtuple('Serializable', ('to_activity', 'remote_id'))
        item = Serializable(lambda: {'a': 'b'}, 'https://e.b/c')
        self.assertEqual(instance.field_to_activity(item), {'a': 'b'})

    def test_many_to_many_field(self):
        instance = fields.ManyToManyField('User')

        Serializable = namedtuple('Serializable', ('to_activity', 'remote_id'))
        Queryset = namedtuple('Queryset', ('all', 'instance'))
        item = Serializable(lambda: {'a': 'b'}, 'https://e.b/c')
        another_item = Serializable(lambda: {}, 'example.com')

        items = Queryset(lambda: [item], another_item)

        self.assertEqual(instance.field_to_activity(items), ['https://e.b/c'])

        instance = fields.ManyToManyField('User', link_only=True)
        instance.name = 'snake_case'
        self.assertEqual(
            instance.field_to_activity(items),
            'example.com/snake_case'
        )
