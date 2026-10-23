"""Tests for thumbnail generation strategy."""

from unittest import TestCase, mock
from PIL import UnidentifiedImageError

from bookwyrm.thumbnail_generation import Strategy


class TestThumbnailGeneration(TestCase):
    """Test Strategy thumbnail generation error handling."""

    def test_on_source_saved_success(self):
        """Should call file.generate() when image is valid"""
        file = mock.MagicMock()
        strategy = Strategy()
        strategy.on_source_saved(file)
        file.generate.assert_called_once()

    def test_on_source_saved_corrupted_image(self):
        """Should catch UnidentifiedImageError when image is corrupted"""
        file = mock.MagicMock()
        file.generate.side_effect = UnidentifiedImageError("cannot identify image file")
        strategy = Strategy()
        strategy.on_source_saved(file)
        file.generate.assert_called_once()

    def test_on_existence_required_corrupted_image(self):
        """Should catch OSError when thumbnail cannot be generated"""
        file = mock.MagicMock()
        file.generate.side_effect = OSError("image file is truncated")
        strategy = Strategy()
        strategy.on_existence_required(file)
        file.generate.assert_called_once()

    def test_on_content_required_corrupted_image(self):
        """Should catch ValueError when image has invalid parameters"""
        file = mock.MagicMock()
        file.generate.side_effect = ValueError("invalid image mode")
        strategy = Strategy()
        strategy.on_content_required(file)
        file.generate.assert_called_once()
