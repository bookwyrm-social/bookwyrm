from django.contrib.auth.decorators import login_required

@login_required
def account_page(request):
    return 'hi'

def webfinger(request):
    return 'hello'

def api(request):
    return 'hey'
