import colorsys
import math
import os
import textwrap

from colorthief import ColorThief
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Avg

from bookwyrm import models, settings
from bookwyrm.tasks import app

# dev
import logging

IMG_WIDTH = settings.PREVIEW_IMG_WIDTH
IMG_HEIGHT = settings.PREVIEW_IMG_HEIGHT
BG_COLOR = settings.PREVIEW_BG_COLOR
TEXT_COLOR = settings.PREVIEW_TEXT_COLOR
DEFAULT_COVER_COLOR = settings.PREVIEW_DEFAULT_COVER_COLOR
TRANSPARENT_COLOR = (0, 0, 0, 0)

margin = math.floor(IMG_HEIGHT / 10)
gutter = math.floor(margin / 2)
cover_img_limits = math.floor(IMG_HEIGHT * 0.8)
path = Path(__file__).parent.absolute()
font_dir = path.joinpath("static/fonts/public_sans")
icon_font_dir = path.joinpath("static/css/fonts")

def get_font(font_name, size=28):
    if font_name == "light":
        font_path = "%s/PublicSans-Light.ttf" % font_dir
    if font_name == "regular":
        font_path = "%s/PublicSans-Regular.ttf" % font_dir
    elif font_name == "bold":
        font_path = "%s/PublicSans-Bold.ttf" % font_dir
    elif font_name == "icomoon":
        font_path = "%s/icomoon.ttf" % icon_font_dir

    try:
        font = ImageFont.truetype(font_path, size)
    except OSError:
        font = ImageFont.load_default()

    return font


def generate_texts_layer(book, content_width):
    font_title = get_font("bold", size=48)
    font_authors = get_font("regular", size=40)

    text_layer = Image.new("RGBA", (content_width, IMG_HEIGHT), color=TRANSPARENT_COLOR)
    text_layer_draw = ImageDraw.Draw(text_layer)

    text_y = 0

    # title
    title = textwrap.fill(book.title, width=28)
    text_layer_draw.multiline_text((0, text_y), title, font=font_title, fill=TEXT_COLOR)

    text_y = text_y + font_title.getsize_multiline(title)[1] + 16

    # subtitle
    authors_text = book.author_text
    authors = textwrap.fill(authors_text, width=36)
    text_layer_draw.multiline_text(
        (0, text_y), authors, font=font_authors, fill=TEXT_COLOR
    )

    text_layer_box = text_layer.getbbox()
    return text_layer.crop(text_layer_box)


def generate_instance_layer(content_width):
    font_instance = get_font("light", size=28)

    site = models.SiteSettings.objects.get()

    if site.logo_small:
        logo_img = Image.open(site.logo_small)
    else:
        static_path = path.joinpath("static/images/logo-small.png")
        logo_img = Image.open(static_path)

    instance_layer = Image.new("RGBA", (content_width, 62), color=TRANSPARENT_COLOR)

    logo_img.thumbnail((50, 50), Image.ANTIALIAS)

    instance_layer.paste(logo_img, (0, 0))

    instance_layer_draw = ImageDraw.Draw(instance_layer)
    instance_layer_draw.text((60, 10), site.name, font=font_instance, fill=TEXT_COLOR)

    line_width = 50 + 10 + font_instance.getsize(site.name)[0]

    line_layer = Image.new("RGBA", (line_width, 2), color=(*(ImageColor.getrgb(TEXT_COLOR)), 50))
    instance_layer.alpha_composite(line_layer, (0, 60))

    return instance_layer


def generate_rating_layer(rating, content_width):
    font_icons = get_font("icomoon", size=60)

    icon_star_full = Image.open(path.joinpath("static/images/icons/star-full.png"))
    icon_star_empty = Image.open(path.joinpath("static/images/icons/star-empty.png"))
    icon_star_half = Image.open(path.joinpath("static/images/icons/star-half.png"))

    icon_size = 64
    icon_margin = 10

    rating_layer_base = Image.new("RGBA", (content_width, icon_size), color=TRANSPARENT_COLOR)
    rating_layer_color = Image.new("RGBA", (content_width, icon_size), color=TEXT_COLOR)
    rating_layer_mask = Image.new("RGBA", (content_width, icon_size), color=TRANSPARENT_COLOR)

    position_x = 0

    for r in range(math.floor(rating)):
        rating_layer_mask.alpha_composite(icon_star_full, (position_x, 0))
        position_x = position_x + icon_size + icon_margin

    if math.floor(rating) != math.ceil(rating):
        rating_layer_mask.alpha_composite(icon_star_half, (position_x, 0))
        position_x = position_x + icon_size + icon_margin

    for r in range(5 - math.ceil(rating)):
        rating_layer_mask.alpha_composite(icon_star_empty, (position_x, 0))
        position_x = position_x + icon_size + icon_margin

    rating_layer_mask = rating_layer_mask.getchannel("A")
    rating_layer_mask = ImageOps.invert(rating_layer_mask)

    rating_layer_composite = Image.composite(rating_layer_base, rating_layer_color, rating_layer_mask)

    return rating_layer_composite


def generate_default_cover():
    font_cover = get_font("light", size=28)

    cover_width = math.floor(cover_img_limits * .7)
    default_cover = Image.new("RGB", (cover_width, cover_img_limits), color=DEFAULT_COVER_COLOR)
    default_cover_draw = ImageDraw.Draw(default_cover)

    text = "no cover :("
    text_dimensions = font_cover.getsize(text)
    text_coords = (math.floor((cover_width - text_dimensions[0]) / 2),
                   math.floor((cover_img_limits - text_dimensions[1]) / 2))
    default_cover_draw.text(text_coords, text, font=font_cover, fill='white')

    return default_cover


def generate_preview_image(book_id, rating=None):
    book = models.Book.objects.select_subclasses().get(id=book_id)

    rating = models.Review.objects.filter(
        privacy="public",
        deleted=False,
        book__in=[book_id],
    ).aggregate(Avg("rating"))["rating__avg"]

    # Cover
    try:
      cover_img_layer = Image.open(book.cover)
      cover_img_layer.thumbnail((cover_img_limits, cover_img_limits), Image.ANTIALIAS)
      color_thief = ColorThief(book.cover)
      dominant_color = color_thief.get_color(quality=1)
    except:
      cover_img_layer = generate_default_cover()
      dominant_color = ImageColor.getrgb(DEFAULT_COVER_COLOR)

    # Color
    if BG_COLOR == 'use_dominant_color':
        image_bg_color = "rgb(%s, %s, %s)" % dominant_color
        # Lighten color
        image_bg_color_rgb = [x/255.0 for x in ImageColor.getrgb(image_bg_color)]
        image_bg_color_hls = colorsys.rgb_to_hls(*image_bg_color_rgb)
        image_bg_color_hls = (image_bg_color_hls[0], 0.9, image_bg_color_hls[1])
        image_bg_color = tuple([math.ceil(x * 255) for x in colorsys.hls_to_rgb(*image_bg_color_hls)])
    else:
        image_bg_color = BG_COLOR

    # Background (using the color)
    img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), color=image_bg_color)

    # Contents
    content_x = margin + cover_img_layer.width + gutter
    content_width = IMG_WIDTH - content_x - margin

    instance_layer = generate_instance_layer(content_width)
    texts_layer = generate_texts_layer(book, content_width)

    contents_layer = Image.new("RGBA", (content_width, IMG_HEIGHT), color=TRANSPARENT_COLOR)
    contents_composite_y = 0
    contents_layer.alpha_composite(instance_layer, (0, contents_composite_y))
    contents_composite_y = contents_composite_y + instance_layer.height + gutter
    contents_layer.alpha_composite(texts_layer, (0, contents_composite_y))
    contents_composite_y = contents_composite_y + texts_layer.height + 30

    if rating:
        # Add some more margin
        contents_composite_y = contents_composite_y + 30
        rating_layer = generate_rating_layer(rating, content_width)
        contents_layer.alpha_composite(rating_layer, (0, contents_composite_y))
        contents_composite_y = contents_composite_y + rating_layer.height + 30

    contents_layer_box = contents_layer.getbbox()
    contents_layer_height = contents_layer_box[3] - contents_layer_box[1]

    contents_y = math.floor((IMG_HEIGHT - contents_layer_height) / 2)
    # Remove Instance Layer from centering calculations
    contents_y = contents_y - math.floor((instance_layer.height + gutter) / 2)
    
    if contents_y < margin:
        contents_y = margin

    cover_y = math.floor((IMG_HEIGHT - cover_img_layer.height) / 2)

    # Composite layers
    img.paste(cover_img_layer, (margin, cover_y))
    img.alpha_composite(contents_layer, (content_x, contents_y))

    file_name = "%s.png" % str(uuid4())

    image_buffer = BytesIO()
    try:
        try:
            old_path = book.preview_image.path
        except ValueError:
            old_path = ''

        # Save
        img.save(image_buffer, format="png")
        book.preview_image = InMemoryUploadedFile(
            ContentFile(image_buffer.getvalue()),
            "preview_image",
            file_name,
            "image/png",
            image_buffer.tell(),
            None,
        )
        book.save(update_fields=["preview_image"])

        # Clean up old file after saving
        if os.path.exists(old_path):
            os.remove(old_path)
    finally:
        image_buffer.close()


@app.task
def generate_preview_image_from_edition_task(book_id, updated_fields=None):
    """generate preview_image after save"""
    if not updated_fields or "preview_image" not in updated_fields:
        generate_preview_image(book_id=book_id)
