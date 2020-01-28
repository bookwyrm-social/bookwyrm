def get_or_create_remote_user(actor):
    ''' wow, a foreigner '''
    try:
        user = models.User.objects.get(actor=actor)
    except models.User.DoesNotExist:
        # TODO: how do you actually correctly learn this?
        username = '%s@%s' % (actor.split('/')[-1], actor.split('/')[2])
        user = models.User.objects.create_user(
            username,
            '', '',
            actor=actor,
            local=False
        )
    return user

