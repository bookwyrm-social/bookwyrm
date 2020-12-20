''' views for actions you can take in the application '''
from io import BytesIO, TextIOWrapper
from uuid import uuid4
from PIL import Image

import dateutil.parser
from dateutil.parser import ParserError

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookwyrm import books_manager
from bookwyrm.broadcast import broadcast
from bookwyrm import forms, models, outgoing
from bookwyrm import goodreads_import
from bookwyrm.emailing import password_reset_email
from bookwyrm.settings import DOMAIN
from bookwyrm.views import get_user_from_username


@require_POST
def user_login(request):
    ''' authenticate user login '''
    login_form = forms.LoginForm(request.POST)

    username = login_form.data['username']
    username = '%s@%s' % (username, DOMAIN)
    password = login_form.data['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        # successful login
        login(request, user)
        user.last_active_date = timezone.now()
        return redirect(request.GET.get('next', '/'))

    login_form.non_field_errors = 'Username or password are incorrect'
    register_form = forms.RegisterForm()
    data = {
        'login_form': login_form,
        'register_form': register_form
    }
    return TemplateResponse(request, 'login.html', data)


@require_POST
def register(request):
    ''' join the server '''
    if not models.SiteSettings.get().allow_registration:
        invite_code = request.POST.get('invite_code')

        if not invite_code:
            raise PermissionDenied

        invite = get_object_or_404(models.SiteInvite, code=invite_code)
    else:
        invite = None

    form = forms.RegisterForm(request.POST)
    errors = False
    if not form.is_valid():
        errors = True

    username = form.data['username'].strip()
    email = form.data['email']
    password = form.data['password']

    # check username and email uniqueness
    if models.User.objects.filter(localname=username).first():
        form.add_error('username', 'User with this username already exists')
        errors = True

    if errors:
        data = {
            'login_form': forms.LoginForm(),
            'register_form': form
        }
        return TemplateResponse(request, 'login.html', data)

    user = models.User.objects.create_user(
        username, email, password, local=True)
    if invite:
        invite.times_used += 1
        invite.save()

    login(request, user)
    return redirect('/')


@login_required
@require_GET
def user_logout(request):
    ''' done with this place! outa here! '''
    logout(request)
    return redirect('/')


@require_POST
def password_reset_request(request):
    ''' create a password reset token '''
    email = request.POST.get('email')
    try:
        user = models.User.objects.get(email=email)
    except models.User.DoesNotExist:
        return redirect('/password-reset')

    # remove any existing password reset cods for this user
    models.PasswordReset.objects.filter(user=user).all().delete()

    # create a new reset code
    code = models.PasswordReset.objects.create(user=user)
    password_reset_email(code)
    data = {'message': 'Password reset link sent to %s' % email}
    return TemplateResponse(request, 'password_reset_request.html', data)


@require_POST
def password_reset(request):
    ''' allow a user to change their password through an emailed token '''
    try:
        reset_code = models.PasswordReset.objects.get(
            code=request.POST.get('reset-code')
        )
    except models.PasswordReset.DoesNotExist:
        data = {'errors': ['Invalid password reset link']}
        return TemplateResponse(request, 'password_reset.html', data)

    user = reset_code.user

    new_password = request.POST.get('password')
    confirm_password = request.POST.get('confirm-password')

    if new_password != confirm_password:
        data = {'errors': ['Passwords do not match']}
        return TemplateResponse(request, 'password_reset.html', data)

    user.set_password(new_password)
    user.save()
    login(request, user)
    reset_code.delete()
    return redirect('/')


@login_required
@require_POST
def password_change(request):
    ''' allow a user to change their password '''
    new_password = request.POST.get('password')
    confirm_password = request.POST.get('confirm-password')

    if new_password != confirm_password:
        return redirect('/user-edit')

    request.user.set_password(new_password)
    request.user.save()
    login(request, request.user)
    return redirect('/user-edit')


@login_required
@require_POST
def edit_profile(request):
    ''' les get fancy with images '''
    form = forms.EditUserForm(request.POST, request.FILES)
    if not form.is_valid():
        data = {
            'form': form,
            'user': request.user,
        }
        return TemplateResponse(request, 'edit_user.html', data)

    request.user.name = form.data['name']
    request.user.email = form.data['email']
    if 'avatar' in form.files:
        # crop and resize avatar upload
        image = Image.open(form.files['avatar'])
        target_size = 120
        width, height = image.size
        thumbnail_scale = height / (width / target_size) if height > width \
            else width / (height / target_size)
        image.thumbnail([thumbnail_scale, thumbnail_scale])
        width, height = image.size

        width_diff = width - target_size
        height_diff = height - target_size
        cropped = image.crop((
            int(width_diff / 2),
            int(height_diff / 2),
            int(width - (width_diff / 2)),
            int(height - (height_diff / 2))
        ))
        output = BytesIO()
        cropped.save(output, format=image.format)
        ContentFile(output.getvalue())

        # set the name to a hash
        extension = form.files['avatar'].name.split('.')[-1]
        filename = '%s.%s' % (uuid4(), extension)
        request.user.avatar.save(
            filename,
            ContentFile(output.getvalue())
        )

    request.user.summary = form.data['summary']
    request.user.manually_approves_followers = \
        form.cleaned_data['manually_approves_followers']
    request.user.save()

    outgoing.handle_update_user(request.user)
    return redirect('/user/%s' % request.user.localname)


@require_POST
def resolve_book(request):
    ''' figure out the local path to a book from a remote_id '''
    remote_id = request.POST.get('remote_id')
    connector = books_manager.get_or_create_connector(remote_id)
    book = connector.get_or_create_book(remote_id)
    if book.connector:
        books_manager.load_more_data.delay(book.id)

    return redirect('/book/%d' % book.id)


@login_required
@permission_required('bookwyrm.edit_book', raise_exception=True)
@require_POST
def edit_book(request, book_id):
    ''' edit a book cool '''
    book = get_object_or_404(models.Edition, id=book_id)

    form = forms.EditionForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        data = {
            'title': 'Edit Book',
            'book': book,
            'form': form
        }
        return TemplateResponse(request, 'edit_book.html', data)
    form.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.id)


@login_required
@require_POST
@transaction.atomic
def switch_edition(request):
    ''' switch your copy of a book to a different edition '''
    edition_id = request.POST.get('edition')
    new_edition = get_object_or_404(models.Edition, id=edition_id)
    shelfbooks = models.ShelfBook.objects.filter(
        book__parent_work=new_edition.parent_work,
        shelf__user=request.user
    )
    for shelfbook in shelfbooks.all():
        broadcast(request.user, shelfbook.to_remove_activity(request.user))

        shelfbook.book = new_edition
        shelfbook.save()

        broadcast(request.user, shelfbook.to_add_activity(request.user))

    readthroughs = models.ReadThrough.objects.filter(
        book__parent_work=new_edition.parent_work,
        user=request.user
    )
    for readthrough in readthroughs.all():
        readthrough.book = new_edition
        readthrough.save()

    return redirect('/book/%d' % new_edition.id)


@login_required
@require_POST
def upload_cover(request, book_id):
    ''' upload a new cover '''
    book = get_object_or_404(models.Edition, id=book_id)

    form = forms.CoverForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        return redirect('/book/%d' % book.id)

    book.cover = form.files['cover']
    book.sync_cover = False
    book.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.id)


@login_required
@require_POST
@permission_required('bookwyrm.edit_book', raise_exception=True)
def add_description(request, book_id):
    ''' upload a new cover '''
    if not request.method == 'POST':
        return redirect('/')

    book = get_object_or_404(models.Edition, id=book_id)

    description = request.POST.get('description')

    book.description = description
    book.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.id)


@login_required
@require_POST
def create_shelf(request):
    ''' user generated shelves '''
    form = forms.ShelfForm(request.POST)
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))

    shelf = form.save()
    return redirect('/user/%s/shelf/%s' % \
            (request.user.localname, shelf.identifier))


@login_required
@require_POST
def edit_shelf(request, shelf_id):
    ''' user generated shelves '''
    shelf = get_object_or_404(models.Shelf, id=shelf_id)
    if request.user != shelf.user:
        return HttpResponseBadRequest()

    form = forms.ShelfForm(request.POST, instance=shelf)
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))
    shelf = form.save()
    return redirect('/user/%s/shelf/%s' % \
            (request.user.localname, shelf.identifier))


@login_required
@require_POST
def delete_shelf(request, shelf_id):
    ''' user generated shelves '''
    shelf = get_object_or_404(models.Shelf, id=shelf_id)
    if request.user != shelf.user or not shelf.editable:
        return HttpResponseBadRequest()

    shelf.delete()
    return redirect('/user/%s/shelves' % request.user.localname)


@login_required
@require_POST
def shelve(request):
    ''' put a  on a user's shelf '''
    book = books_manager.get_edition(request.POST['book'])

    desired_shelf = models.Shelf.objects.filter(
        identifier=request.POST['shelf'],
        user=request.user
    ).first()

    if request.POST.get('reshelve', True):
        try:
            current_shelf = models.Shelf.objects.get(
                user=request.user,
                edition=book
            )
            outgoing.handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    outgoing.handle_shelve(request.user, book, desired_shelf)

    # post about "want to read" shelves
    if desired_shelf.identifier == 'to-read':
        outgoing.handle_reading_status(
            request.user,
            desired_shelf,
            book,
            privacy='public'
        )

    return redirect('/')


@login_required
@require_POST
def unshelve(request):
    ''' put a  on a user's shelf '''
    book = models.Edition.objects.get(id=request.POST['book'])
    current_shelf = models.Shelf.objects.get(id=request.POST['shelf'])

    outgoing.handle_unshelve(request.user, book, current_shelf)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def start_reading(request, book_id):
    ''' begin reading a book '''
    book = books_manager.get_edition(book_id)
    shelf = models.Shelf.objects.filter(
        identifier='reading',
        user=request.user
    ).first()

    # create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough.start_date:
        readthrough.save()

    # shelve the book
    if request.POST.get('reshelve', True):
        try:
            current_shelf = models.Shelf.objects.get(
                user=request.user,
                edition=book
            )
            outgoing.handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    outgoing.handle_shelve(request.user, book, shelf)

    # post about it (if you want)
    if request.POST.get('post-status'):
        privacy = request.POST.get('privacy')
        outgoing.handle_reading_status(request.user, shelf, book, privacy)

    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def finish_reading(request, book_id):
    ''' a user completed a book, yay '''
    book = books_manager.get_edition(book_id)
    shelf = models.Shelf.objects.filter(
        identifier='read',
        user=request.user
    ).first()

    # update or create a readthrough
    readthrough = update_readthrough(request, book=book)
    if readthrough.start_date or readthrough.finish_date:
        readthrough.save()

    # shelve the book
    if request.POST.get('reshelve', True):
        try:
            current_shelf = models.Shelf.objects.get(
                user=request.user,
                edition=book
            )
            outgoing.handle_unshelve(request.user, book, current_shelf)
        except models.Shelf.DoesNotExist:
            # this just means it isn't currently on the user's shelves
            pass
    outgoing.handle_shelve(request.user, book, shelf)

    # post about it (if you want)
    if request.POST.get('post-status'):
        privacy = request.POST.get('privacy')
        outgoing.handle_reading_status(request.user, shelf, book, privacy)

    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def edit_readthrough(request):
    ''' can't use the form because the dates are too finnicky '''
    readthrough = update_readthrough(request, create=False)
    if not readthrough:
        return HttpResponseNotFound()

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()
    readthrough.save()

    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def delete_readthrough(request):
    ''' remove a readthrough '''
    readthrough = get_object_or_404(
        models.ReadThrough, id=request.POST.get('id'))

    # don't let people edit other people's data
    if request.user != readthrough.user:
        return HttpResponseBadRequest()

    readthrough.delete()
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def rate(request):
    ''' just a star rating for a book '''
    form = forms.RatingForm(request.POST)
    return handle_status(request, form)


@login_required
@require_POST
def review(request):
    ''' create a book review '''
    form = forms.ReviewForm(request.POST)
    return handle_status(request, form)


@login_required
@require_POST
def quotate(request):
    ''' create a book quotation '''
    form = forms.QuotationForm(request.POST)
    return handle_status(request, form)


@login_required
@require_POST
def comment(request):
    ''' create a book comment '''
    form = forms.CommentForm(request.POST)
    return handle_status(request, form)


@login_required
@require_POST
def reply(request):
    ''' respond to a book review '''
    form = forms.ReplyForm(request.POST)
    return handle_status(request, form)


def handle_status(request, form):
    ''' all the "create a status" functions are the same '''
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))

    outgoing.handle_status(request.user, form)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def tag(request):
    ''' tag a book '''
    # I'm not using a form here because sometimes "name" is sent as a hidden
    # field which doesn't validate
    name = request.POST.get('name')
    book_id = request.POST.get('book')
    book = get_object_or_404(models.Edition, id=book_id)
    tag_obj, created = models.Tag.objects.get_or_create(
        name=name,
    )
    user_tag = models.UserTag.objects.get_or_create(
        user=request.user,
        book=book,
        tag=tag_obj,
    )

    if created:
        outgoing.handle_tag(request.user, user_tag)
    return redirect('/book/%s' % book_id)


@login_required
@require_POST
def untag(request):
    ''' untag a book '''
    name = request.POST.get('name')
    book_id = request.POST.get('book')

    outgoing.handle_untag(request.user, book_id, name)
    return redirect('/book/%s' % book_id)


@login_required
@require_POST
def favorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_favorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def unfavorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_unfavorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def boost(request, status_id):
    ''' boost a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_boost(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def unboost(request, status_id):
    ''' boost a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_unboost(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def delete_status(request, status_id):
    ''' delete and tombstone a status '''
    status = get_object_or_404(models.Status, id=status_id)

    # don't let people delete other people's statuses
    if status.user != request.user:
        return HttpResponseBadRequest()

    # perform deletion
    outgoing.handle_delete_status(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
@require_POST
def follow(request):
    ''' follow another user, here or abroad '''
    username = request.POST['user']
    try:
        to_follow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_follow(request.user, to_follow)
    user_slug = to_follow.localname if to_follow.localname \
        else to_follow.username
    return redirect('/user/%s' % user_slug)


@login_required
@require_POST
def unfollow(request):
    ''' unfollow a user '''
    username = request.POST['user']
    try:
        to_unfollow = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_unfollow(request.user, to_unfollow)
    user_slug = to_unfollow.localname if to_unfollow.localname \
        else to_unfollow.username
    return redirect('/user/%s' % user_slug)


@login_required
def clear_notifications(request):
    ''' permanently delete notification for user '''
    request.user.notification_set.filter(read=True).delete()
    return redirect('/notifications')


@login_required
@require_POST
def accept_follow_request(request):
    ''' a user accepts a follow request '''
    username = request.POST['user']
    try:
        requester = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        # Request already dealt with.
        pass
    else:
        outgoing.handle_accept(follow_request)

    return redirect('/user/%s' % request.user.localname)


@login_required
@require_POST
def delete_follow_request(request):
    ''' a user rejects a follow request '''
    username = request.POST['user']
    try:
        requester = get_user_from_username(username)
    except models.User.DoesNotExist:
        return HttpResponseBadRequest()

    try:
        follow_request = models.UserFollowRequest.objects.get(
            user_subject=requester,
            user_object=request.user
        )
    except models.UserFollowRequest.DoesNotExist:
        return HttpResponseBadRequest()

    outgoing.handle_reject(follow_request)
    return redirect('/user/%s' % request.user.localname)


@login_required
@require_POST
def import_data(request):
    ''' ingest a goodreads csv '''
    form = forms.ImportForm(request.POST, request.FILES)
    if form.is_valid():
        include_reviews = request.POST.get('include_reviews') == 'on'
        privacy = request.POST.get('privacy')
        try:
            job = goodreads_import.create_job(
                request.user,
                TextIOWrapper(
                    request.FILES['csv_file'],
                    encoding=request.encoding),
                include_reviews,
                privacy,
            )
        except (UnicodeDecodeError, ValueError):
            return HttpResponseBadRequest('Not a valid csv file')
        goodreads_import.start_import(job)
        return redirect('/import-status/%d' % job.id)
    return HttpResponseBadRequest()


@login_required
@require_POST
def retry_import(request):
    ''' ingest a goodreads csv '''
    job = get_object_or_404(models.ImportJob, id=request.POST.get('import_job'))
    items = []
    for item in request.POST.getlist('import_item'):
        items.append(get_object_or_404(models.ImportItem, id=item))

    job = goodreads_import.create_retry_job(
        request.user,
        job,
        items,
    )
    goodreads_import.start_import(job)
    return redirect('/import-status/%d' % job.id)


@login_required
@require_POST
@permission_required('bookwyrm.create_invites', raise_exception=True)
def create_invite(request):
    ''' creates a user invite database entry '''
    form = forms.CreateInviteForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("ERRORS : %s" % (form.errors,))

    invite = form.save(commit=False)
    invite.user = request.user
    invite.save()

    return redirect('/invite')


def update_readthrough(request, book=None, create=True):
    ''' updates but does not save dates on a readthrough '''
    try:
        read_id = request.POST.get('id')
        if not read_id:
            raise models.ReadThrough.DoesNotExist
        readthrough = models.ReadThrough.objects.get(id=read_id)
    except models.ReadThrough.DoesNotExist:
        if not create or not book:
            return None
        readthrough = models.ReadThrough(
            user=request.user,
            book=book,
        )

    start_date = request.POST.get('start_date')
    if start_date:
        try:
            start_date = dateutil.parser.parse(start_date)
            readthrough.start_date = start_date
        except ParserError:
            pass

    finish_date = request.POST.get('finish_date')
    if finish_date:
        try:
            finish_date = dateutil.parser.parse(finish_date)
            readthrough.finish_date = finish_date
        except ParserError:
            pass

    return readthrough
