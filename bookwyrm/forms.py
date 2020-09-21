''' usin django model forms '''
import datetime

from django.core.exceptions import ValidationError
from django.forms import ModelForm, PasswordInput, widgets
from django import forms

from bookwyrm import models


class LoginForm(ModelForm):
    class Meta:
        model = models.User
        fields = ['username', 'password']
        help_texts = {f: None for f in fields}
        widgets = {
            'password': PasswordInput(),
        }


class RegisterForm(ModelForm):
    class Meta:
        model = models.User
        fields = ['username', 'email', 'password']
        help_texts = {f: None for f in fields}
        widgets = {
            'password': PasswordInput()
        }


class RatingForm(ModelForm):
    class Meta:
        model = models.Review
        fields = ['rating']


class ReviewForm(ModelForm):
    class Meta:
        model = models.Review
        fields = ['name', 'content']
        help_texts = {f: None for f in fields}
        labels = {
            'name': 'Title',
            'content': 'Review',
        }


class CommentForm(ModelForm):
    class Meta:
        model = models.Comment
        fields = ['content']
        help_texts = {f: None for f in fields}
        labels = {
            'content': 'Comment',
        }


class QuotationForm(ModelForm):
    class Meta:
        model = models.Quotation
        fields = ['quote', 'content']
        help_texts = {f: None for f in fields}
        labels = {
            'quote': 'Quote',
            'content': 'Comment',
        }


class ReplyForm(ModelForm):
    class Meta:
        model = models.Status
        fields = ['content']
        help_texts = {f: None for f in fields}
        labels = {'content': 'Comment'}


class EditUserForm(ModelForm):
    class Meta:
        model = models.User
        fields = ['avatar', 'name', 'summary', 'manually_approves_followers']
        help_texts = {f: None for f in fields}


class TagForm(ModelForm):
    class Meta:
        model = models.Tag
        fields = ['name']
        help_texts = {f: None for f in fields}
        labels = {'name': 'Add a tag'}


class CoverForm(ModelForm):
    class Meta:
        model = models.Book
        fields = ['cover']
        help_texts = {f: None for f in fields}


class EditionForm(ModelForm):
    class Meta:
        model = models.Edition
        exclude = [
            'created_date',
            'updated_date',
            'last_sync_date',

            'authors',# TODO
            'parent_work',
            'shelves',
            'misc_identifiers',

            'subjects',# TODO
            'subject_places',# TODO

            'connector',
        ]


class ImportForm(forms.Form):
    csv_file = forms.FileField()

class ExpiryWidget(widgets.Select):
    def value_from_datadict(self, data, files, name):
        selected_string = super().value_from_datadict(data, files, name)

        if selected_string == 'day':
            interval = datetime.timedelta(days=1)
        elif selected_string == 'week':
            interval = datetime.timedelta(days=7)
        elif selected_string == 'month':
            interval = datetime.timedelta(days=31) # Close enough?
        elif selected_string == 'forever':
            return None
        else:
            return selected_string # "This will raise

        return datetime.datetime.now() + interval

class CreateInviteForm(ModelForm):
    class Meta:
        model = models.SiteInvite
        exclude = ['code', 'user', 'times_used']
        widgets = {
            'expiry': ExpiryWidget(choices=[
                ('day', 'One Day'),
                ('week', 'One Week'),
                ('month', 'One Month'),
                ('forever', 'Does Not Expire')]),
            'use_limit': widgets.Select(
                choices=[(i, "%d uses" % (i,)) for i in [1, 5, 10, 25, 50, 100]]
                + [(None, 'Unlimited')])
        }
