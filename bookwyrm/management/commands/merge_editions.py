""" PROCEED WITH CAUTION: uses deduplication fields to permanently
merge edition data objects """
from bookwyrm import models
from bookwyrm.management.merge_command import MergeCommand


class Command(MergeCommand):
    """merges two editions by ID"""

    help = "merges specified editions into one"

    MODEL = models.Edition
