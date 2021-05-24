import math
import textwrap

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile

from bookwyrm import models, settings
from bookwyrm.tasks import app

# dev
import logging

IMG_WIDTH = settings.PREVIEW_IMG_WIDTH
IMG_HEIGHT = settings.PREVIEW_IMG_HEIGHT
BG_COLOR = (182, 186, 177)
TRANSPARENT_COLOR = (0, 0, 0, 0)
TEXT_COLOR = (16, 16, 16)

margin = math.ceil(IMG_HEIGHT / 10)
gutter = math.ceil(margin / 2)
cover_img_limits = math.ceil(IMG_HEIGHT * 0.8)
path = Path(__file__).parent.absolute()
font_path = path.joinpath("static/fonts/public_sans")


def generate_texts_layer(edition, text_x):
    try:
        font_title = ImageFont.truetype("%s/PublicSans-Bold.ttf" % font_path, 48)
        font_authors = ImageFont.truetype("%s/PublicSans-Regular.ttf" % font_path, 40)
    except OSError:
        font_title = ImageFont.load_default()
        font_authors = ImageFont.load_default()

    text_layer = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), color=TRANSPARENT_COLOR)
    text_layer_draw = ImageDraw.Draw(text_layer)

    text_y = 0

    text_y = text_y + 6

    # title
    title = textwrap.fill(edition.title, width=28)
    text_layer_draw.multiline_text((0, text_y), title, font=font_title, fill=TEXT_COLOR)

    text_y = text_y + font_title.getsize_multiline(title)[1] + 16

    # subtitle
    authors_text = ", ".join(a.name for a in edition.authors.all())
    authors = textwrap.fill(authors_text, width=36)
    text_layer_draw.multiline_text(
        (0, text_y), authors, font=font_authors, fill=TEXT_COLOR
    )

    imageBox = text_layer.getbbox()
    return text_layer.crop(imageBox)


def generate_site_layer(text_x):
    try:
        font_instance = ImageFont.truetype("%s/PublicSans-Light.ttf" % font_path, 28)
    except OSError:
        font_instance = ImageFont.load_default()

    site = models.SiteSettings.objects.get()

    if site.logo_small:
        logo_img = Image.open(site.logo_small)
    else:
        static_path = path.joinpath("static/images/logo-small.png")
        logo_img = Image.open(static_path)

    site_layer = Image.new("RGBA", (IMG_WIDTH - text_x - margin, 50), color=BG_COLOR)

    logo_img.thumbnail((50, 50), Image.ANTIALIAS)

    site_layer.paste(logo_img, (0, 0))

    site_layer_draw = ImageDraw.Draw(site_layer)
    site_layer_draw.text((60, 10), site.name, font=font_instance, fill=TEXT_COLOR)

    return site_layer


def generate_preview_image(edition):
    img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), color=BG_COLOR)

    cover_img_layer = Image.open(edition.cover)
    cover_img_layer.thumbnail((cover_img_limits, cover_img_limits), Image.ANTIALIAS)

    text_x = margin + cover_img_layer.width + gutter

    texts_layer = generate_texts_layer(edition, text_x)
    text_y = IMG_HEIGHT - margin - texts_layer.height

    site_layer = generate_site_layer(text_x)

    # Composite all layers
    img.paste(cover_img_layer, (margin, margin))
    img.alpha_composite(texts_layer, (text_x, text_y))
    img.alpha_composite(site_layer, (text_x, margin))

    file_name = "%s.png" % str(uuid4())

    image_buffer = BytesIO()
    try:
        img.save(image_buffer, format="png")
        edition.preview_image = InMemoryUploadedFile(
            ContentFile(image_buffer.getvalue()),
            "preview_image",
            file_name,
            "image/png",
            image_buffer.tell(),
            None,
        )

        edition.save(update_fields=["preview_image"])
    finally:
        image_buffer.close()


@app.task
def generate_preview_image_task(instance, *args, **kwargs):
    """generate preview_image after save"""
    updated_fields = kwargs["update_fields"]

    if not updated_fields or "preview_image" not in updated_fields:
        logging.warn("image name to delete", instance.preview_image.name)
        generate_preview_image(edition=instance)
