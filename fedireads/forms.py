''' usin django model forms '''
from django.forms import ModelForm, PasswordInput
from django import forms

from fedireads import models


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
            'password': PasswordInput(),
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

            'authors',
            'parent_work',
            'shelves',
            'misc_identifiers',

            'subjects',# TODO
            'subject_places',# TODO

            'source_url',
            'connector',
        ]


class ImportForm(forms.Form):
    csv_file = forms.FileField()
