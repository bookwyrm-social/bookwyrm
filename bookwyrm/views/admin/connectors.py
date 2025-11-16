""" manage book data sources """
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views import View

from bookwyrm.models import Connector
from bookwyrm.connectors import create_finna_connector
from bookwyrm.connectors.settings import CONNECTORS


@method_decorator(login_required, name="dispatch")
@method_decorator(
    permission_required("bookwyrm.edit_instance_settings", raise_exception=True),
    name="dispatch",
)
class ConnectorSettings(View):
    """show connector settings page"""

    # pylint: disable=no-self-use
    def get(self, request):
        """list of connectors"""

        # connectors where the previous defaults need to be updated
        # for example when an API endpoint changes and we want admins
        # to update their connector settings

        update_connectors = Connector.objects.none()  # for now

        # example - this would pick up all openlibrary connectors where
        # the isbn_search_url is not "https://openlibrary.org/search.json?isbn="

        # update_connectors = Connector.objects.filter(
        #     connector_file="openlibrary"
        # ).exclude(isbn_search_url="https://openlibrary.org/search.json?isbn=")

        # book API source like Open Library etc
        other_connectors = (
            Connector.objects.exclude(connector_file="bookwyrm_connector")
            .order_by("name")
            .difference(update_connectors)
        )

        # other BookWyrm instances
        bookwrym_connectors = Connector.objects.filter(
            connector_file="bookwyrm_connector"
        ).order_by("identifier")

        # Optional and new connectors e.g. Finna
        # These are not yet Connector objects so we have to describe them in the
        # template at settings/connectors/available.html
        available_connectors = []
        for val in CONNECTORS:
            if Connector.objects.filter(connector_file=val).count() == 0:
                available_connectors.append(val)

        data = {
            "update_connectors": update_connectors,
            "bookwyrm_connectors": bookwrym_connectors,
            "other_connectors": other_connectors,
            "available_connectors": available_connectors,
        }
        return TemplateResponse(request, "settings/connectors/connectors.html", data)


# pylint: disable=unused-argument
def deactivate_connector(request, connector_id):
    """we don't want to use this connector"""

    connector = get_object_or_404(Connector, id=connector_id)
    connector.deactivate(reason="manual")
    return redirect("/settings/connectors/")


# pylint: disable=unused-argument
def activate_connector(request, connector_id: int):
    """oops changed our mind"""

    connector = get_object_or_404(Connector, id=connector_id)
    connector.activate()
    return redirect("/settings/connectors/")


def set_connector_priority(request, connector_id: int):
    """what order should connectors appear in?"""

    priority = request.POST.get("priority")
    connector = get_object_or_404(Connector, id=connector_id)
    connector.change_priority(priority=priority)
    return redirect("/settings/connectors/")


# pylint: disable=unused-argument
def update_connector(request, connector_id: int):
    """update connector info such as API endpoints"""

    connector = get_object_or_404(Connector, id=connector_id)
    # see models.Connector to determine what update() does
    connector.update()
    return redirect("/settings/connectors/")


def create_connector(request):
    """create a new optional connector"""

    connector_file = request.POST.get("connector_file")

    # if you add a new connector, add a check here
    # and make a create_xxx_connector() function in connector_manager.py
    if connector_file == "finna":
        create_finna_connector()

    return redirect("/settings/connectors/")
