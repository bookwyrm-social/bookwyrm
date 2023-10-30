"""BookWyrm implementation of django-file-resubmit

The majority of this code is originally from django-file-resubmit:
https://github.com/un1t/django-file-resubmit,
with some minor updates

Copyright (C) 2011 by Ilya Shalyapin, ishalyapin@gmail.com

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""

from io import BytesIO
import os
import uuid

from django import forms

from django.contrib.admin.widgets import AdminFileWidget as BaseWidget
from django.core.cache import caches
from django.core.files.uploadedfile import InMemoryUploadedFile

from django.forms import ClearableFileInput
from django.forms.widgets import FILE_INPUT_CONTRADICTION
from django.utils.safestring import mark_safe


get_cache = lambda cache_name: caches[cache_name]


class FileCache:
    """Use for temporarily caching image files in forms"""

    def __init__(self):
        self.backend = get_backend()

    def set(self, key, upload):
        """set the state"""
        upload.file.seek(0)
        state = {
            "name": upload.name,
            "size": upload.size,
            "content_type": upload.content_type,
            "charset": upload.charset,
            "content": upload.file.read(),
        }
        upload.file.seek(0)
        self.backend.set(key, state)

    def get(self, key, field_name):
        """get the state"""
        upload = None
        state = self.backend.get(key)
        if state:
            file = BytesIO()
            file.write(state["content"])
            upload = InMemoryUploadedFile(
                file=file,
                field_name=field_name,
                name=state["name"],
                content_type=state["content_type"],
                size=state["size"],
                charset=state["charset"],
            )
            upload.file.seek(0)
        return upload

    def delete(self, key):
        """delete the cached file"""
        self.backend.delete(key)


class ResubmitBaseWidget(ClearableFileInput):
    """Base widget class for file_resubmit"""

    def __init__(self, attrs=None, field_type=None):
        super().__init__(attrs=attrs)
        self.cache_key = ""
        self.field_type = field_type
        self.input_name = None

    def value_from_datadict(self, data, files, name):
        """get the value of the file"""
        upload = super().value_from_datadict(data, files, name)
        if upload == FILE_INPUT_CONTRADICTION:
            return upload

        self.input_name = f"{name}_cache_key"
        self.cache_key = data.get(self.input_name, "")

        if name in files:
            self.cache_key = random_key()[:10]
            upload = files[name]
            FileCache().set(self.cache_key, upload)
        elif self.cache_key:
            restored = FileCache().get(self.cache_key, name)
            if restored:
                upload = restored
                files[name] = upload
        return upload

    def output_extra_data(self, value=None):
        """output the name of the file if there already is one"""
        output = ""
        if value and self.cache_key:
            output += " " + filename_from_value(value)
        if self.cache_key:
            output += forms.HiddenInput().render(
                self.input_name,
                self.cache_key,
                {},
            )
        return output


class AdminResubmitImageWidget(ResubmitBaseWidget, BaseWidget):
    """class for saving original image upload in two-stage forms"""

    def render(self, name, value, attrs=None, renderer=None):
        if self.cache_key:
            output = self.output_extra_data(value)
        else:
            output = super().render(name, value, attrs)
            output += self.output_extra_data(value)
        return mark_safe(output)


def get_backend():
    """get the file cache"""
    return get_cache("file_resubmit")


def random_key():
    """get a random UUID"""
    return uuid.uuid4().hex


def filename_from_value(value):
    """get the file name"""
    return os.path.split(value.name)[-1] if value else ""
