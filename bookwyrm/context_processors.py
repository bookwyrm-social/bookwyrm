''' customize the info available in context for rendering templates '''
from bookwyrm import models

def site_settings(request):
    ''' include the custom info about the site '''
    return {
        'site': models.SiteSettings.objects.first()
    }
