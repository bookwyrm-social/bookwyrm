from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import path, re_path
from revproxy.views import ProxyView

class FlowerProxyView(UserPassesTestMixin, ProxyView):
    upstream = 'http://{}:{}'.format('localhost', 8888)
    url_prefix = 'flower'
    rewrite = (
        (r'^/{}$'.format(url_prefix), r'/{}/'.format(url_prefix)),
     )

    def test_func(self):
        return self.request.user.is_superuser

    @classmethod
    def as_url(cls):
        return re_path(r'^(?P<path>{}.*)$'.format(cls.url_prefix), cls.as_view(), name='flower')
