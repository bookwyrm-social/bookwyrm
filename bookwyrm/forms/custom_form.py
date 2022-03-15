""" Overrides django's default form class """
from collections import defaultdict
from django.forms import ModelForm
from django.forms.widgets import Textarea


class CustomForm(ModelForm):
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
        super(CustomForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            if hasattr(visible.field.widget, "input_type"):
                input_type = visible.field.widget.input_type
            if isinstance(visible.field.widget, Textarea):
                input_type = "textarea"
                visible.field.widget.attrs["rows"] = 5
            visible.field.widget.attrs["class"] = css_classes[input_type]
