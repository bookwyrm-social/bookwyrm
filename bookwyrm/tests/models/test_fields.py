''' testing models '''
from io import BytesIO
from collections import namedtuple
import json
import pathlib
import re
from unittest.mock import patch

from PIL import Image
import responses

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.test import TestCase
from django.utils import timezone

from bookwyrm.models import fields, User

class ActivitypubFields(TestCase):
    ''' overwrites standard model feilds to work with activitypub '''
    def test_validate_remote_id(self):
        ''' should look like a url '''
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
        ''' generic mixin with super basic to and from functionality '''
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
        ''' just sets some defaults on charfield '''
        instance = fields.RemoteIdField()
        self.assertEqual(instance.max_length, 255)

        with self.assertRaises(ValidationError):
            instance.run_validators('http://www.example.com/dlfjg 23/x')

    def test_username_field(self):
        ''' again, just setting defaults on username field '''
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
        ''' should be able to format a related model '''
        instance = fields.ForeignKey('User', on_delete=models.CASCADE)
        Serializable = namedtuple('Serializable', ('to_activity', 'remote_id'))
        item = Serializable(lambda: {'a': 'b'}, 'https://e.b/c')
        # returns the remote_id field of the related object
        self.assertEqual(instance.field_to_activity(item), 'https://e.b/c')

    @responses.activate
    def test_foreign_key_from_activity(self):
        ''' this is the important stuff '''
        instance = fields.ForeignKey(User, on_delete=models.CASCADE)

        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/ap_user.json'
        )
        userdata = json.loads(datafile.read_bytes())
        # don't try to load the user icon
        del userdata['icon']

        # test receiving an unknown remote id and loading data
        responses.add(
            responses.GET,
            'https://example.com/user/mouse',
            json=userdata,
            status=200)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            value = instance.field_from_activity(
                'https://example.com/user/mouse')

        # test recieving activity json
        value = instance.field_from_activity(userdata)
        self.assertIsInstance(value, User)
        self.assertEqual(value.remote_id, 'https://example.com/user/mouse')
        self.assertEqual(value.name, 'MOUSE?? MOUSE!!')
        # et cetera but we're not testing serializing user json

        # test receiving a remote id of an object in the db
        user = User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        value = instance.field_from_activity(user.remote_id)
        self.assertEqual(value, user)


    def test_one_to_one_field(self):
        ''' a gussied up foreign key '''
        instance = fields.OneToOneField('User', on_delete=models.CASCADE)
        Serializable = namedtuple('Serializable', ('to_activity', 'remote_id'))
        item = Serializable(lambda: {'a': 'b'}, 'https://e.b/c')
        self.assertEqual(instance.field_to_activity(item), {'a': 'b'})

    def test_many_to_many_field(self):
        ''' lists! '''
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

    @responses.activate
    def test_many_to_many_field_from_activity(self):
        ''' resolve related fields for a list, takes a list of remote ids '''
        instance = fields.ManyToManyField(User)
        datafile = pathlib.Path(__file__).parent.joinpath(
            '../data/ap_user.json'
        )
        userdata = json.loads(datafile.read_bytes())
        # don't try to load the user icon
        del userdata['icon']

        # test receiving an unknown remote id and loading data
        responses.add(
            responses.GET,
            'https://example.com/user/mouse',
            json=userdata,
            status=200)
        with patch('bookwyrm.models.user.set_remote_server.delay'):
            value = instance.field_from_activity(
                ['https://example.com/user/mouse', 'bleh']
            )
        self.assertIsInstance(value, list)
        self.assertEqual(len(value), 1)
        self.assertIsInstance(value[0], User)

    def test_tag_field(self):
        ''' a special type of many to many field '''
        instance = fields.TagField('User')

        Serializable = namedtuple(
            'Serializable',
            ('to_activity', 'remote_id', 'name_field', 'name')
        )
        Queryset = namedtuple('Queryset', ('all', 'instance'))
        item = Serializable(
            lambda: {'a': 'b'}, 'https://e.b/c', 'name', 'Name')
        another_item = Serializable(
            lambda: {}, 'example.com', '', '')
        items = Queryset(lambda: [item], another_item)

        result = instance.field_to_activity(items)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].href, 'https://e.b/c')
        self.assertEqual(result[0].name, 'Name')
        self.assertEqual(result[0].type, 'Serializable')


    def test_tag_field_from_activity(self):
        ''' loadin' a list of items from Links '''
        # TODO


    @responses.activate
    def test_image_field(self):
        ''' storing images '''
        user = User.objects.create_user(
            'mouse', 'mouse@mouse.mouse', 'mouseword', local=True)
        image_file = pathlib.Path(__file__).parent.joinpath(
            '../../static/images/default_avi.jpg')
        image = Image.open(image_file)
        output = BytesIO()
        image.save(output, format=image.format)
        user.avatar.save(
            'test.jpg',
            ContentFile(output.getvalue())
        )

        output = fields.image_serializer(user.avatar)
        self.assertIsNotNone(
            re.match(
                r'.*\.jpg',
                output.url,
            )
        )
        self.assertEqual(output.type, 'Image')

        instance = fields.ImageField()

        self.assertEqual(instance.field_to_activity(user.avatar), output)

        responses.add(
            responses.GET,
            'http://www.example.com/image.jpg',
            body=user.avatar.file.read(),
            status=200)
        loaded_image = instance.field_from_activity(
            'http://www.example.com/image.jpg')
        self.assertIsInstance(loaded_image, list)
        self.assertIsInstance(loaded_image[1], ContentFile)


    def test_datetime_field(self):
        ''' this one is pretty simple, it just has to use isoformat '''
        instance = fields.DateTimeField()
        now = timezone.now()
        self.assertEqual(instance.field_to_activity(now), now.isoformat())
        self.assertEqual(
            instance.field_from_activity(now.isoformat()), now
        )
        self.assertEqual(instance.field_from_activity('bip'), None)


    def test_array_field(self):
        ''' idk why it makes them strings but probably for a good reason '''
        instance = fields.ArrayField(fields.IntegerField)
        self.assertEqual(instance.field_to_activity([0, 1]), ['0', '1'])
