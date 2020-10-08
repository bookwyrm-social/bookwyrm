''' views for actions you can take in the application '''
from io import BytesIO, TextIOWrapper
from PIL import Image

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.core.files.base import ContentFile
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.core.exceptions import PermissionDenied

from bookwyrm import books_manager
from bookwyrm import forms, models, outgoing
from bookwyrm import goodreads_import
from bookwyrm.emailing import password_reset_email
from bookwyrm.settings import DOMAIN
from bookwyrm.views import get_user_from_username


def user_login(request):
    ''' authenticate user login '''
    if request.method == 'GET':
        return redirect('/login')

    login_form = forms.LoginForm(request.POST)
    register_form = forms.RegisterForm()
    if not login_form.is_valid():
        data = {
            'site_settings': models.SiteSettings.get(),
            'login_form': login_form,
            'register_form': register_form
        }
        return TemplateResponse(request, 'login.html', data)

    username = login_form.data['username']
    username = '%s@%s' % (username, DOMAIN)
    password = login_form.data['password']
    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return redirect(request.GET.get('next', '/'))

    login_form.non_field_errors = 'Username or password are incorrect'
    data = {
        'site_settings': models.SiteSettings.get(),
        'login_form': login_form,
        'register_form': register_form
    }
    return TemplateResponse(request, 'login.html', data)


def register(request):
    ''' join the server '''
    if request.method == 'GET':
        return redirect('/login')

    if not models.SiteSettings.get().allow_registration:
        invite_code = request.POST.get('invite_code')

        if not invite_code:
            raise PermissionDenied

        try:
            invite = models.SiteInvite.objects.get(code=invite_code)
        except models.SiteInvite.DoesNotExist:
            raise PermissionDenied
    else:
        invite = None

    form = forms.RegisterForm(request.POST)
    errors = False
    if not form.is_valid():
        errors = True

    username = form.data['username']
    email = form.data['email']
    password = form.data['password']

    # check username and email uniqueness
    if models.User.objects.filter(localname=username).first():
        form.add_error('username', 'User with this username already exists')
        errors = True

    if errors:
        data = {
            'site_settings': models.SiteSettings.get(),
            'login_form': forms.LoginForm(),
            'register_form': form
        }
        return TemplateResponse(request, 'login.html', data)

    user = models.User.objects.create_user(username, email, password)
    if invite:
        invite.times_used += 1
        invite.save()

    login(request, user)
    return redirect('/')


@login_required
def user_logout(request):
    ''' done with this place! outa here! '''
    logout(request)
    return redirect('/')


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
def edit_profile(request):
    ''' les get fancy with images '''
    if not request.method == 'POST':
        return redirect('/user/%s' % request.user.localname)

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
        request.user.avatar.save(
            form.files['avatar'].name,
            ContentFile(output.getvalue())
        )

    request.user.summary = form.data['summary']
    request.user.manually_approves_followers = \
        form.cleaned_data['manually_approves_followers']
    request.user.save()

    outgoing.handle_update_user(request.user)
    return redirect('/user/%s' % request.user.localname)


def resolve_book(request):
    ''' figure out the local path to a book from a remote_id '''
    remote_id = request.POST.get('remote_id')
    book = books_manager.get_or_create_book(remote_id)
    return redirect('/book/%d' % book.id)


@login_required
@permission_required('bookwyrm.edit_book', raise_exception=True)
def edit_book(request, book_id):
    ''' edit a book cool '''
    if not request.method == 'POST':
        return redirect('/book/%s' % book_id)

    try:
        book = models.Edition.objects.get(id=book_id)
    except models.Edition.DoesNotExist:
        return HttpResponseNotFound()

    form = forms.EditionForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))
    form.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.id)


@login_required
def upload_cover(request, book_id):
    ''' upload a new cover '''
    # TODO: alternate covers?
    if not request.method == 'POST':
        return redirect('/book/%s' % request.user.localname)

    try:
        book = models.Edition.objects.get(id=book_id)
    except models.Edition.DoesNotExist:
        return HttpResponseNotFound()

    form = forms.CoverForm(request.POST, request.FILES, instance=book)
    if not form.is_valid():
        return redirect(request.headers.get('Referer', '/'))

    book.cover = form.files['cover']
    book.sync_cover = False
    book.save()

    outgoing.handle_update_book(request.user, book)
    return redirect('/book/%s' % book.id)


@login_required
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
    return redirect('/')


@login_required
def rate(request):
    ''' just a star rating for a book '''
    form = forms.RatingForm(request.POST)
    book_id = request.POST.get('book')
    # TODO: better failure behavior
    if not form.is_valid():
        return redirect('/book/%s' % book_id)

    rating = form.cleaned_data.get('rating')
    # throws a value error if the book is not found

    outgoing.handle_rate(request.user, book_id, rating)
    return redirect('/book/%s' % book_id)


@login_required
def review(request):
    ''' create a book review '''
    form = forms.ReviewForm(request.POST)
    book_id = request.POST.get('book')
    if not form.is_valid():
        return redirect('/book/%s' % book_id)

    # TODO: validation, htmlification
    name = form.cleaned_data.get('name')
    content = form.cleaned_data.get('content')
    rating = form.data.get('rating', None)
    try:
        rating = int(rating)
    except ValueError:
        rating = None

    outgoing.handle_review(request.user, book_id, name, content, rating)
    return redirect('/book/%s' % book_id)


@login_required
def quotate(request):
    ''' create a book quotation '''
    form = forms.QuotationForm(request.POST)
    book_id = request.POST.get('book')
    if not form.is_valid():
        return redirect('/book/%s' % book_id)

    quote = form.cleaned_data.get('quote')
    content = form.cleaned_data.get('content')

    outgoing.handle_quotation(request.user, book_id, content, quote)
    return redirect('/book/%s' % book_id)


@login_required
def comment(request):
    ''' create a book comment '''
    form = forms.CommentForm(request.POST)
    book_id = request.POST.get('book')
    # TODO: better failure behavior
    if not form.is_valid():
        return redirect('/book/%s' % book_id)

    # TODO: validation, htmlification
    content = form.data.get('content')

    outgoing.handle_comment(request.user, book_id, content)
    return redirect('/book/%s' % book_id)


@login_required
def tag(request):
    ''' tag a book '''
    # I'm not using a form here because sometimes "name" is sent as a hidden
    # field which doesn't validate
    name = request.POST.get('name')
    book_id = request.POST.get('book')
    remote_id = 'https://%s/book/%s' % (DOMAIN, book_id)

    outgoing.handle_tag(request.user, remote_id, name)
    return redirect('/book/%s' % book_id)


@login_required
def untag(request):
    ''' untag a book '''
    name = request.POST.get('name')
    book_id = request.POST.get('book')

    outgoing.handle_untag(request.user, book_id, name)
    return redirect('/book/%s' % book_id)


@login_required
def reply(request):
    ''' respond to a book review '''
    form = forms.ReplyForm(request.POST)
    # this is a bit of a formality, the form is just one text field
    if not form.is_valid():
        return redirect('/')
    parent_id = request.POST['parent']
    parent = models.Status.objects.get(id=parent_id)
    outgoing.handle_reply(request.user, parent, form.data['content'])
    return redirect('/')


@login_required
def favorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_favorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
def unfavorite(request, status_id):
    ''' like a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_unfavorite(request.user, status)
    return redirect(request.headers.get('Referer', '/'))

@login_required
def boost(request, status_id):
    ''' boost a status '''
    status = models.Status.objects.get(id=status_id)
    outgoing.handle_boost(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
def delete_status(request):
    ''' delete and tombstone a status '''
    status_id = request.POST.get('status')
    if not status_id:
        return HttpResponseBadRequest()
    try:
        status = models.Status.objects.get(id=status_id)
    except models.Status.DoesNotExist:
        return HttpResponseBadRequest()

    # don't let people delete other people's statuses
    if status.user != request.user:
        return HttpResponseBadRequest()

    # perform deletion
    outgoing.handle_delete_status(request.user, status)
    return redirect(request.headers.get('Referer', '/'))


@login_required
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
        outgoing.handle_accept(requester, request.user, follow_request)

    return redirect('/user/%s' % request.user.localname)


@login_required
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

    outgoing.handle_reject(requester, request.user, follow_request)
    return redirect('/user/%s' % request.user.localname)


@login_required
def import_data(request):
    ''' ingest a goodreads csv '''
    form = forms.ImportForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            job = goodreads_import.create_job(
                request.user,
                TextIOWrapper(
                    request.FILES['csv_file'],
                    encoding=request.encoding)
            )
        except (UnicodeDecodeError, ValueError):
            return HttpResponseBadRequest('Not a valid csv file')
        goodreads_import.start_import(job)
        return redirect('/import_status/%d' % (job.id,))
    return HttpResponseBadRequest()


@login_required
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
