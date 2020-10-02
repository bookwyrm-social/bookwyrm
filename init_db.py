''' starter data '''
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from bookwyrm.models import Connector, User
from bookwyrm.settings import DOMAIN


groups = ['admin', 'moderator', 'editor']
for group in groups:
    Group.objects.create(name=group)

permissions = [{
        'codename': 'edit_instance_settings',
        'name': 'change the instance info',
        'groups': ['admin',]
    }, {
        'codename': 'set_user_group',
        'name': 'change what group a user is in',
        'groups': ['admin', 'moderator']
    }, {
        'codename': 'control_federation',
        'name': 'control who to federate with',
        'groups': ['admin', 'moderator']
    }, {
        'codename': 'create_invites',
        'name': 'issue invitations to join',
        'groups': ['admin', 'moderator']
    }, {
        'codename': 'moderate_user',
        'name': 'deactivate or silence a user',
        'groups': ['admin', 'moderator']
    }, {
        'codename': 'moderate_post',
        'name': 'delete other users\' posts',
        'groups': ['admin', 'moderator']
    }, {
        'codename': 'edit_book',
        'name': 'edit book info',
        'groups': ['admin', 'moderator', 'editor']
    }]

content_type = ContentType.objects.get_for_model(User)
for permission in permissions:
    permission_obj = Permission.objects.create(
        codename=permission['codename'],
        name=permission['name'],
        content_type=content_type,
    )
    # add the permission to the appropriate groups
    for group_name in permission['groups']:
        Group.objects.get(name=group_name).permissions.add(permission_obj)

# while the groups and permissions shouldn't be changed because the code
# depends on them, what permissions go with what groups should be editable



Connector.objects.create(
    identifier=DOMAIN,
    name='Local',
    local=True,
    connector_file='self_connector',
    base_url='https://%s' % DOMAIN,
    books_url='https://%s/book' % DOMAIN,
    covers_url='https://%s/images/covers' % DOMAIN,
    search_url='https://%s/search?q=' % DOMAIN,
    priority=1,
)

Connector.objects.create(
    identifier='openlibrary.org',
    name='OpenLibrary',
    connector_file='openlibrary',
    base_url='https://openlibrary.org',
    books_url='https://openlibrary.org',
    covers_url='https://covers.openlibrary.org',
    search_url='https://openlibrary.org/search?q=',
)
