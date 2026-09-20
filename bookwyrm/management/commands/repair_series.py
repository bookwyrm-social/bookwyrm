"""fix series with json-like names"""

import ast
import sys
from django.core.management.base import BaseCommand

from bookwyrm.connectors.inventaire import Connector as InventaireConnector
from bookwyrm.models import Edition, Series, SeriesBook, User, Work
from bookwyrm.settings import INSTANCE_ACTOR_USERNAME


def load_connector():
    """load inventaire connector"""
    return InventaireConnector("inventaire.io")


def progress_bar(step, total):
    """show a progress bar"""

    percentage = 100 * float(step) / float(total)
    steps = int(round(percentage / 100 * 31))
    progress = (
        "["
        + ("-" * steps + " " * int(31 - steps))
        + "]"
        + "{:.2f}".format(percentage)
        + "% completed"
    )
    sys.stdout.write("\r" + progress)


def get_series_json(options: dict, book: Edition) -> dict | None:
    """return a dict from a series string"""

    try:
        series = ast.literal_eval(book.series.strip())
        if isinstance(series, list) and isinstance(series[0], dict):
            return series
        error = "Cannot parse into JSON"
    except Exception as err:
        error = err

    return f"ERROR repairing Edition with id: {book.id} | series: {book.series} | error: {error}"


def fix_books(options: dict) -> None:
    """fix book series name values"""

    editions = Edition.objects.filter(series__startswith="[{")
    errors = []
    nameless_errors = []
    nameless = []
    edition_progress = 0
    nameless_progress = 0

    if options["verbosity"] > 0:
        print("\nChecking editions for faulty series...\n")
    for edition in editions:
        if not hasattr(edition, "parent_work"):
            errors.append(
                f"ERROR repairing Edition with id: {edition.id} | series: {edition.series} | No parent_work"
            )
        else:
            series = get_series_json(options, edition)
            edition.series = series
            if isinstance(series, str):
                errors.append(series)
            elif "name" in series:
                if not options["dry_run"]:
                    load_connector().get_or_create_seriesbook_from_data(
                        work=edition.parent_work, edition=edition
                    )
            else:
                nameless.append(edition)

        edition_progress += 1
        progress_bar(edition_progress, editions.count())

    if options["names"]:
        if nameless and options["verbosity"] > 0:
            print(
                f"\n\nFinding missing names for series on {len(nameless)} editions...\n"
            )
        for data in nameless:
            try:
                series = Series(**data.series[0])
            except Exception as err:
                nameless_errors.append(
                    f"ERROR fixing unnamed series on Edition with id: {data.id} | series: {data.series} | error: {err}"
                )
            if not options["dry_run"]:
                return_value = refetch_or_fix_individual_series(options, series)
                if isinstance(return_value, str):
                    nameless_errors.append(return_value)
                else:
                    user = User.objects.get(localname=INSTANCE_ACTOR_USERNAME)
                    SeriesBook.objects.get_or_create(
                        book=data.parent_work, series=return_value, user=user
                    )

            nameless_progress += 1
            progress_bar(nameless_progress, len(nameless))

    if options["verbosity"] > 0:
        print("\n")
        print("-" * 50)
        if options["dry_run"]:
            print("This was a dry run. Results would have been:\n")
        print(f"Processed {editions.count()} editions with suspect series entries")
        if errors:
            print(
                f"{len(errors) + len(nameless_errors)} errors encountered during processing"
            )
        if nameless:
            if not options["names"]:
                print(
                    f"\n{len(nameless)} possibly repairable editions with missing series name"
                )
                print(
                    "Run the repair_series command again with the --names flag to try fixing these"
                )
            else:
                print(
                    f"\n{len(nameless) - len(nameless_errors)} of {len(nameless)} unnamed series repaired"
                )
                if options["dry_run"]:
                    print("\ndry-run may not accurately calculate all errors")

        if options["verbosity"] > 1:
            if errors or nameless_errors:
                print("\nThe following errors were encountered:\n")
                for error in errors:
                    print(error)
                for error in nameless_errors:
                    print(error)
            for work in Work.objects.filter(series__startswith="[{"):
                # These should have all been fixed, so any remaining works need attention
                print(f"Faulty Work remains with id: {work.id} | series: {work.series}")

        print("-" * 50)


def refetch_or_fix_individual_series(options: dict, series: Series) -> str | None:
    """get series data from inventaire or name from alternative names"""

    if series.inventaire_id not in ["", None]:
        series_list = load_connector().format_series(
            keys=[f"https://inventaire.io/entity/{series.inventaire_id}"]
        )
        if not series_list or len(series_list) < 1:
            return f"ERROR fixing nameless series id: {series.id} error: Can't find series data on Inventaire"

        data = series_list[0]  # we only passed in one series key
        if "name" not in data:  # let's double check!
            return f"ERROR fixing nameless series id: {series.id} error: Can't find series name on Inventaire"

        series.name = data["name"]
        series.alternative_names = list(
            set(series.alternative_names + data["alternative_names"])
        )
        for field in Series._meta.get_fields():
            if hasattr(field, "deduplication_field") and field.name in data:
                setattr(series, field.name, data[field.name])
        series.save()
        return series

    elif options["all"]:
        # there is no inventaire_id so we can't just re-fetch the series
        # try using the first alternative name if we have one
        if not series.alternative_names:
            return f"ERROR fixing nameless series id: {series.id} error: No names or inventaire id"

        series.name = series.alternative_names[0]
        series.save()
        return series


def repair_nameless_series(options: dict) -> None:
    """fix series that don't have names"""

    if options["dry_run"]:
        print("It is not possible to repair nameless series during a dry run")

    series_to_fix = Series.objects.filter(name__in=["", None])
    progress = 0
    errors = []

    if options["verbosity"] > 0:
        print(f"\nFinding names for {series_to_fix.count()} series\n")

    for series in series_to_fix:
        return_value = refetch_or_fix_individual_series(options, series)
        if isinstance(return_value, str):
            errors.append(return_value)
        progress += 1
        progress_bar(progress, series_to_fix.count())

    if options["verbosity"] > 0:
        print("\n")
        print("-" * 50)
        print(
            f"Fixed {series_to_fix.count() - len(errors)} of {series_to_fix.count()} nameless series"
        )
        if errors:
            print(f"{len(errors)} errors encountered during processing")
            if options["verbosity"] > 1:
                print("\nThe following errors were encountered:\n")
                for error in errors:
                    print(error)
        print("\n")
        print("-" * 50)


def get_counts():
    """just get counts of items that could be repaired"""

    series = Series.objects.filter(name__in=["", None])
    editions = Edition.objects.filter(series__startswith="[{")
    works = Work.objects.filter(series__startswith="[{")

    print("\n")
    print("-" * 50)
    print(f"  Total Series to fix: {series.count()}")
    print(f"  Total Editions to fix: {editions.count()}")
    print(f"  Total Works to fix: {works.count()}")
    print("-" * 50)


class Command(BaseCommand):
    """Run process according to flags"""

    help = "Amend faulty series data created due to bugs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--names",
            action="store_true",
            help="When repairing series on books, also fix nameless series on those books.\nThis may take a long time to run as it will query Inventaire",
        )

        parser.add_argument(
            "--skip-books",
            action="store_true",
            help="Repair nameless series, but do not check works and editions for series errors.\nThis may take a long time to run as it will query Inventaire",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Repair all names. This will use the first alternative name if there is no inventaire ID available",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what could have happened, without changing any data",
        )

        parser.add_argument(
            "--counts",
            action="store_true",
            help="Get total counts of data that would be processed",
        )

    def handle(self, *args, **options):
        """run process according to flag"""

        if options["counts"]:
            get_counts()
        elif options["skip_books"]:
            repair_nameless_series(options)
        else:
            fix_books(options)
