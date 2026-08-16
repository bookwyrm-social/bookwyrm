"""test override fixtures"""

import fakeredis
import pytest
from unittest import mock


@pytest.fixture(scope="session", autouse=True)
def fake_redis():
    """use fake redis server to avoid problems testing anything use to_model()"""
    with mock.patch(
        "bookwyrm.activitypub.base_activity.r", fakeredis.FakeRedis()
    ) as _fakeredis:
        yield _fakeredis
