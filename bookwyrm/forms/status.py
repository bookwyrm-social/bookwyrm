""" using django model forms """
from bookwyrm import models
from .custom_form import CustomForm


# pylint: disable=missing-class-docstring
class RatingForm(CustomForm):
    class Meta:
        model = models.ReviewRating
        fields = ["user", "book", "rating", "privacy"]


class ReviewForm(CustomForm):
    class Meta:
        model = models.Review
        fields = [
            "user",
            "book",
            "name",
            "content",
            "rating",
            "content_warning",
            "sensitive",
            "privacy",
        ]


class CommentForm(CustomForm):
    class Meta:
        model = models.Comment
        fields = [
            "user",
            "book",
            "content",
            "content_warning",
            "sensitive",
            "privacy",
            "progress",
            "progress_mode",
            "reading_status",
        ]


class QuotationForm(CustomForm):
    class Meta:
        model = models.Quotation
        fields = [
            "user",
            "book",
            "quote",
            "content",
            "content_warning",
            "sensitive",
            "privacy",
            "position",
            "endposition",
            "position_mode",
        ]


class ReplyForm(CustomForm):
    class Meta:
        model = models.Status
        fields = [
            "user",
            "content",
            "content_warning",
            "sensitive",
            "reply_parent",
            "privacy",
        ]


class StatusForm(CustomForm):
    class Meta:
        model = models.Status
        fields = ["user", "content", "content_warning", "sensitive", "privacy"]


class DirectForm(CustomForm):
    class Meta:
        model = models.Status
        fields = ["user", "content", "content_warning", "sensitive", "privacy"]
