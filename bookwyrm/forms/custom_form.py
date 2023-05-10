""" Overrides django's default form class """
from collections import defaultdict
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.forms.widgets import Textarea


class StyledForm(ModelForm):
    """add css classes to the forms"""

    def __init__(self, *args, **kwargs):
        css_classes = defaultdict(lambda: "")
        css_classes["text"] = "input"
        css_classes["password"] = "input"
        css_classes["email"] = "input"
        css_classes["number"] = "input"
        css_classes["checkbox"] = "checkbox"
        css_classes["textarea"] = "textarea"
        # pylint: disable=super-with-arguments
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if hasattr(visible.field.widget, "input_type"):
                input_type = visible.field.widget.input_type
            if isinstance(visible.field.widget, Textarea):
                input_type = "textarea"
                visible.field.widget.attrs["rows"] = 5
            visible.field.widget.attrs["class"] = css_classes[input_type]


class CustomForm(StyledForm):
    """Check permissions on save"""

    # pylint: disable=arguments-differ
    def save(self, request, *args, **kwargs):
        """Save and check perms"""
        self.instance.raise_not_editable(request.user)
        return super().save(*args, **kwargs)

    # def clean(self):
    #     self.cleaned_data = super().clean()

    #     print("Clean")
    #     print(self.errors)

    #     for name, field in self.fields.items():
    #         if self.has_error(field):
    #             print(field.widget.__dir__())
    #             self.add_to_attributes(field, "class", "is-danger")

    #     return self.cleaned_data

    def add_error(self, field, error):
        super().add_error(field, error)

        # TODO this (finding the field) is much too complicated; probably this is not the right location?
        #   it is however more or less what super().add_error does...
        if field is None:
            if isinstance(error, dict):
                for field_name, messages in error.items():
                    if field_name in self.fields:
                        self.add_to_attributes(
                            self.fields[field_name], "class", "is-danger"
                        )
            elif isinstance(error, ValidationError):
                if hasattr(error, "error_dict"):
                    error = error.error_dict
                    for field_name, error_list in error.items():
                        if field_name in self.fields:
                            self.add_to_attributes(
                                self.fields[field_name], "class", "is-danger"
                            )
        else:
            self.add_to_attributes(field, "class", "is-danger")

    # TODO this method looks much too complicated for a simple "field.add_class(class)"?
    def add_to_attributes(self, field, attr_name, value):
        current_attributes = field.widget.attrs
        current_classes = set(current_attributes.get(attr_name, "").split())
        current_classes.add(value)

        current_attributes[attr_name] = " ".join(current_classes)
