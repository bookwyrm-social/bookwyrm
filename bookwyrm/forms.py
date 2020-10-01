''' using django model forms '''
import datetime
from collections import defaultdict

from django import forms
from django.forms import ModelForm, PasswordInput, widgets
from django.forms.widgets import Textarea

from bookwyrm import models


class CustomForm(ModelForm):
    ''' add css classes to the forms '''
    def __init__(self, *args, **kwargs):
        css_classes = defaultdict(lambda: '')
        css_classes['text'] = 'input'
        css_classes['password'] = 'input'
        css_classes['email'] = 'input'
        css_classes['number'] = 'input'
        css_classes['checkbox'] = 'checkbox'
        css_classes['textarea'] = 'textarea'
        super(CustomForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if hasattr(visible.field.widget, 'input_type'):
                input_type = visible.field.widget.input_type
            if isinstance(visible.field.widget, Textarea):
                input_type = 'textarea'
            visible.field.widget.attrs['class'] = css_classes[input_type]

class LoginForm(CustomForm):
    class Meta:
        model = models.User
        fields = ['username', 'password']
        help_texts = {f: None for f in fields}
        widgets = {
            'password': PasswordInput(),
        }


class RegisterForm(CustomForm):
    class Meta:
        model = models.User
        fields = ['username', 'email', 'password']
        help_texts = {f: None for f in fields}
        widgets = {
            'password': PasswordInput()
        }


class RatingForm(CustomForm):
    class Meta:
        model = models.Review
        fields = ['rating']


class ReviewForm(CustomForm):
    class Meta:
        model = models.Review
        fields = ['name', 'content']
        help_texts = {f: None for f in fields}
        labels = {
            'name': 'Title',
            'content': 'Review',
        }


class CommentForm(CustomForm):
    class Meta:
        model = models.Comment
        fields = ['content']
        help_texts = {f: None for f in fields}
        labels = {
            'content': 'Comment',
        }


class QuotationForm(CustomForm):
    class Meta:
        model = models.Quotation
        fields = ['quote', 'content']
        help_texts = {f: None for f in fields}
        labels = {
            'quote': 'Quote',
            'content': 'Comment',
        }


class ReplyForm(CustomForm):
    class Meta:
        model = models.Status
        fields = ['content']
        help_texts = {f: None for f in fields}
        labels = {'content': 'Comment'}


class EditUserForm(CustomForm):
    class Meta:
        model = models.User
        fields = ['avatar', 'name', 'summary', 'manually_approves_followers']
        help_texts = {f: None for f in fields}


class TagForm(CustomForm):
    class Meta:
        model = models.Tag
        fields = ['name']
        help_texts = {f: None for f in fields}
        labels = {'name': 'Add a tag'}


class CoverForm(CustomForm):
    class Meta:
        model = models.Book
        fields = ['cover']
        help_texts = {f: None for f in fields}


class EditionForm(CustomForm):
    class Meta:
        model = models.Edition
        exclude = [
            'remote_id',
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

class CreateInviteForm(CustomForm):
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
