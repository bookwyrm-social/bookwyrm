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

    series = ast.literal_eval(book.series.strip())
    if isinstance(series, list) and isinstance(series[0], dict):
        return series
    raise ValueError(f"Series values in edition {book.id} cannot be parsed to JSON")


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
        edition_progress += 1
        progress_bar(edition_progress, editions.count())
        try:
            if not edition.parent_work:
                raise ValueError(f"Edition {edition.id} has no parent work")
            else:
                series = get_series_json(options, edition)
                edition.parent_work.series = series
                if "name" in series[0]:
                    if not options["dry_run"]:
                        edition.series = series[0]["name"]
                        load_connector().get_or_create_seriesbook_from_data(
                            work=edition.parent_work, edition=edition
                        )
                else:
                    nameless.append(edition)
        except Exception as err:
            errors.append(err)

    if options["names"]:
        if nameless and options["verbosity"] > 0:
            print(
                f"\n\nFinding missing names for series on {len(nameless)} editions...\n"
            )
        for data in nameless:
            nameless_progress += 1
            progress_bar(nameless_progress, len(nameless))
            try:
                series = Series(**data.parent_work.series[0])
                if not options["dry_run"]:
                    return_value = refetch_or_fix_individual_series(options, series)
                    user = User.objects.get(localname=INSTANCE_ACTOR_USERNAME)
                    SeriesBook.objects.get_or_create(
                        book=data.parent_work, series=return_value, user=user
                    )
                    update_fields = ["series"]
                    edition.series = None
                    edition.parent_work.series = None
                    edition.save(update_fields=update_fields)
                    edition.parent_work.save(update_fields=update_fields)
            except Exception as err:
                nameless_errors.append(err)
                continue

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


def refetch_or_fix_individual_series(options: dict, series: Series) -> Series:
    """get series data from inventaire or name from alternative names"""

    if series.inventaire_id not in ["", None]:
        series_list = load_connector().format_series(keys=[series.inventaire_id])
        if not series_list or len(series_list) < 1:
            raise ValueError(f"Can't find series data on Inventaire for {series.id}")

        data = series_list[0]  # we only passed in one series key
        if "name" not in data:  # let's double check!
            raise ValueError(f"Can't find series name on Inventaire for {series.id}")

        series.name = data["name"]
        series.alternative_names = list(
            set(series.alternative_names + data["alternative_names"])
        )
        update_fields = ["name", "alternative_names"]
        for field in Series._meta.get_fields():
            if hasattr(field, "deduplication_field") and field.name in data:
                setattr(series, field.name, data[field.name])
                update_fields.append(field.name)

    elif options["all"]:
        # there is no inventaire_id so we can't just re-fetch the series
        # try using the first alternative name if we have one
        if not series.alternative_names:
            raise ValueError(
                f"Can't fix nameless series. No names or inventaire id for {series.id}"
            )

        series.name = series.alternative_names[0]
        update_fields = ["name"]

    if series.id not in ["", None]:
        series.save(update_fields=update_fields)
    else:
        series.user = User.objects.get(localname=INSTANCE_ACTOR_USERNAME)
        series.save()
    return series


def repair_nameless_series(options: dict) -> None:
    """fix series that don't have names"""

    if options["dry_run"]:
        raise Exception("It is not possible to repair nameless series during a dry run")

    errors = []
    progress = 0
    series_to_fix = Series.objects.filter(name__in=["", None])
    if options["verbosity"] > 0:
        print(f"\nFinding names for {series_to_fix.count()} series\n")

    for series in series_to_fix:
        if not options["dry_run"]:
            try:
                refetch_or_fix_individual_series(options, series)
            except Exception as err:
                errors.append(err)
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
