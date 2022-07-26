""" using django model forms """
from django import forms


class ArrayWidget(forms.widgets.TextInput):
    """Inputs for postgres array fields"""

    # pylint: disable=unused-argument
    # pylint: disable=no-self-use
    def value_from_datadict(self, data, files, name):
        """get all values for this name"""
        return [i for i in data.getlist(name) if i]


class Select(forms.Select):
    """custom template for select widget"""

    template_name = "widgets/select.html"


class SelectDateWidget(forms.SelectDateWidget):
    """
    A widget that splits date input into two <select> boxes and a numerical year.
    """

    template_name = "widgets/addon_multiwidget.html"
    select_widget = Select

    def get_context(self, name, value, attrs):
        """sets individual widgets"""
        context = super().get_context(name, value, attrs)
        date_context = {}
        year_name = self.year_field % name
        date_context["year"] = forms.NumberInput().get_context(
            name=year_name,
            value=context["widget"]["value"]["year"],
            attrs={
                **context["widget"]["attrs"],
                "id": f"id_{year_name}",
                "class": "input",
            },
        )
        month_choices = list(self.months.items())
        if not self.is_required:
            month_choices.insert(0, self.month_none_value)
        month_name = self.month_field % name
        date_context["month"] = self.select_widget(
            attrs, choices=month_choices
        ).get_context(
            name=month_name,
            value=context["widget"]["value"]["month"],
            attrs={**context["widget"]["attrs"], "id": f"id_{month_name}"},
        )
        day_choices = [(i, i) for i in range(1, 32)]
        if not self.is_required:
            day_choices.insert(0, self.day_none_value)
        day_name = self.day_field % name
        date_context["day"] = self.select_widget(
            attrs,
            choices=day_choices,
        ).get_context(
            name=day_name,
            value=context["widget"]["value"]["day"],
            attrs={**context["widget"]["attrs"], "id": f"id_{day_name}"},
        )
        subwidgets = []
        for field in self._parse_date_fmt():
            subwidgets.append(date_context[field]["widget"])
        context["widget"]["subwidgets"] = subwidgets
        return context
