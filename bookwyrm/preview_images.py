""" Generate social media preview images for twitter/mastodon/etc """
import math
import os
import textwrap
from io import BytesIO
from uuid import uuid4

import colorsys
from colorthief import ColorThief
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Avg

from bookwyrm import models, settings
from bookwyrm.tasks import app


IMG_WIDTH = settings.PREVIEW_IMG_WIDTH
IMG_HEIGHT = settings.PREVIEW_IMG_HEIGHT
BG_COLOR = settings.PREVIEW_BG_COLOR
TEXT_COLOR = settings.PREVIEW_TEXT_COLOR
DEFAULT_COVER_COLOR = settings.PREVIEW_DEFAULT_COVER_COLOR
TRANSPARENT_COLOR = (0, 0, 0, 0)

margin = math.floor(IMG_HEIGHT / 10)
gutter = math.floor(margin / 2)
inner_img_height = math.floor(IMG_HEIGHT * 0.8)
inner_img_width = math.floor(inner_img_height * 0.7)
font_dir = os.path.join(settings.STATIC_ROOT, "fonts/public_sans")


def get_font(font_name, size=28):
    """Loads custom font"""
    if font_name == "light":
        font_path = os.path.join(font_dir, "PublicSans-Light.ttf")
    if font_name == "regular":
        font_path = os.path.join(font_dir, "PublicSans-Regular.ttf")
    elif font_name == "bold":
        font_path = os.path.join(font_dir, "PublicSans-Bold.ttf")

    try:
        font = ImageFont.truetype(font_path, size)
    except OSError:
        font = ImageFont.load_default()

    return font


def generate_texts_layer(texts, content_width):
    """Adds text for images"""
    font_text_zero = get_font("bold", size=20)
    font_text_one = get_font("bold", size=48)
    font_text_two = get_font("bold", size=40)
    font_text_three = get_font("regular", size=40)

    text_layer = Image.new("RGBA", (content_width, IMG_HEIGHT), color=TRANSPARENT_COLOR)
    text_layer_draw = ImageDraw.Draw(text_layer)

    text_y = 0

    if "text_zero" in texts and texts["text_zero"]:
        # Text one (Book title)
        text_zero = textwrap.fill(texts["text_zero"], width=72)
        text_layer_draw.multiline_text(
            (0, text_y), text_zero, font=font_text_zero, fill=TEXT_COLOR
        )

        try:
            text_y = text_y + font_text_zero.getsize_multiline(text_zero)[1] + 16
        except (AttributeError, IndexError):
            text_y = text_y + 26

    if "text_one" in texts and texts["text_one"]:
        # Text one (Book title)
        text_one = textwrap.fill(texts["text_one"], width=28)
        text_layer_draw.multiline_text(
            (0, text_y), text_one, font=font_text_one, fill=TEXT_COLOR
        )

        try:
            text_y = text_y + font_text_one.getsize_multiline(text_one)[1] + 16
        except (AttributeError, IndexError):
            text_y = text_y + 26

    if "text_two" in texts and texts["text_two"]:
        # Text one (Book subtitle)
        text_two = textwrap.fill(texts["text_two"], width=36)
        text_layer_draw.multiline_text(
            (0, text_y), text_two, font=font_text_two, fill=TEXT_COLOR
        )

        try:
            text_y = text_y + font_text_one.getsize_multiline(text_two)[1] + 16
        except (AttributeError, IndexError):
            text_y = text_y + 26

    if "text_three" in texts and texts["text_three"]:
        # Text three (Book authors)
        text_three = textwrap.fill(texts["text_three"], width=36)
        text_layer_draw.multiline_text(
            (0, text_y), text_three, font=font_text_three, fill=TEXT_COLOR
        )

    text_layer_box = text_layer.getbbox()
    return text_layer.crop(text_layer_box)


def generate_instance_layer(content_width):
    """Places components for instance preview"""
    font_instance = get_font("light", size=28)

    site = models.SiteSettings.objects.get()

    if site.logo_small:
        logo_img = Image.open(site.logo_small)
    else:
        try:
            static_path = os.path.join(settings.STATIC_ROOT, "images/logo-small.png")
            logo_img = Image.open(static_path)
        except FileNotFoundError:
            logo_img = None

    instance_layer = Image.new("RGBA", (content_width, 62), color=TRANSPARENT_COLOR)

    instance_text_x = 0

    if logo_img:
        logo_img.thumbnail((50, 50), Image.ANTIALIAS)

        instance_layer.paste(logo_img, (0, 0))

        instance_text_x = instance_text_x + 60

    instance_layer_draw = ImageDraw.Draw(instance_layer)
    instance_layer_draw.text(
        (instance_text_x, 10), site.name, font=font_instance, fill=TEXT_COLOR
    )

    line_width = 50 + 10 + font_instance.getsize(site.name)[0]

    line_layer = Image.new(
        "RGBA", (line_width, 2), color=(*(ImageColor.getrgb(TEXT_COLOR)), 50)
    )
    instance_layer.alpha_composite(line_layer, (0, 60))

    return instance_layer


def generate_rating_layer(rating, content_width):
    """Places components for rating preview"""
    try:
        icon_star_full = Image.open(
            os.path.join(settings.STATIC_ROOT, "images/icons/star-full.png")
        )
        icon_star_empty = Image.open(
            os.path.join(settings.STATIC_ROOT, "images/icons/star-empty.png")
        )
        icon_star_half = Image.open(
            os.path.join(settings.STATIC_ROOT, "images/icons/star-half.png")
        )
    except FileNotFoundError:
        return None

    icon_size = 64
    icon_margin = 10

    rating_layer_base = Image.new(
        "RGBA", (content_width, icon_size), color=TRANSPARENT_COLOR
    )
    rating_layer_color = Image.new("RGBA", (content_width, icon_size), color=TEXT_COLOR)
    rating_layer_mask = Image.new(
        "RGBA", (content_width, icon_size), color=TRANSPARENT_COLOR
    )

    position_x = 0

    for _ in range(math.floor(rating)):
        rating_layer_mask.alpha_composite(icon_star_full, (position_x, 0))
        position_x = position_x + icon_size + icon_margin

    if math.floor(rating) != math.ceil(rating):
        rating_layer_mask.alpha_composite(icon_star_half, (position_x, 0))
        position_x = position_x + icon_size + icon_margin

    for _ in range(5 - math.ceil(rating)):
        rating_layer_mask.alpha_composite(icon_star_empty, (position_x, 0))
        position_x = position_x + icon_size + icon_margin

    rating_layer_mask = rating_layer_mask.getchannel("A")
    rating_layer_mask = ImageOps.invert(rating_layer_mask)

    rating_layer_composite = Image.composite(
        rating_layer_base, rating_layer_color, rating_layer_mask
    )

    return rating_layer_composite


def generate_default_inner_img():
    """Adds cover image"""
    font_cover = get_font("light", size=28)

    default_cover = Image.new(
        "RGB", (inner_img_width, inner_img_height), color=DEFAULT_COVER_COLOR
    )
    default_cover_draw = ImageDraw.Draw(default_cover)

    text = "no image :("
    text_dimensions = font_cover.getsize(text)
    text_coords = (
        math.floor((inner_img_width - text_dimensions[0]) / 2),
        math.floor((inner_img_height - text_dimensions[1]) / 2),
    )
    default_cover_draw.text(text_coords, text, font=font_cover, fill="white")

    return default_cover


# pylint: disable=too-many-locals
def generate_preview_image(
    texts=None, picture=None, rating=None, show_instance_layer=True
):
    """Puts everything together"""
    texts = texts or {}
    # Cover
    try:
        inner_img_layer = Image.open(picture)
        inner_img_layer.thumbnail((inner_img_width, inner_img_height), Image.ANTIALIAS)
        color_thief = ColorThief(picture)
        dominant_color = color_thief.get_color(quality=1)
    except:  # pylint: disable=bare-except
        inner_img_layer = generate_default_inner_img()
        dominant_color = ImageColor.getrgb(DEFAULT_COVER_COLOR)

    # Color
    if BG_COLOR in ["use_dominant_color_light", "use_dominant_color_dark"]:
        image_bg_color = "rgb(%s, %s, %s)" % dominant_color

        # Adjust color
        image_bg_color_rgb = [x / 255.0 for x in ImageColor.getrgb(image_bg_color)]
        image_bg_color_hls = colorsys.rgb_to_hls(*image_bg_color_rgb)

        if BG_COLOR == "use_dominant_color_light":
            lightness = max(0.9, image_bg_color_hls[1])
        else:
            lightness = min(0.15, image_bg_color_hls[1])

        image_bg_color_hls = (
            image_bg_color_hls[0],
            lightness,
            image_bg_color_hls[2],
        )
        image_bg_color = tuple(
            math.ceil(x * 255) for x in colorsys.hls_to_rgb(*image_bg_color_hls)
        )
    else:
        image_bg_color = BG_COLOR

    # Background (using the color)
    img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), color=image_bg_color)

    # Contents
    inner_img_x = margin + inner_img_width - inner_img_layer.width
    inner_img_y = math.floor((IMG_HEIGHT - inner_img_layer.height) / 2)
    content_x = margin + inner_img_width + gutter
    content_width = IMG_WIDTH - content_x - margin

    contents_layer = Image.new(
        "RGBA", (content_width, IMG_HEIGHT), color=TRANSPARENT_COLOR
    )
    contents_composite_y = 0

    if show_instance_layer:
        instance_layer = generate_instance_layer(content_width)
        contents_layer.alpha_composite(instance_layer, (0, contents_composite_y))
        contents_composite_y = contents_composite_y + instance_layer.height + gutter

    texts_layer = generate_texts_layer(texts, content_width)
    contents_layer.alpha_composite(texts_layer, (0, contents_composite_y))
    contents_composite_y = contents_composite_y + texts_layer.height + gutter

    if rating:
        # Add some more margin
        contents_composite_y = contents_composite_y + gutter
        rating_layer = generate_rating_layer(rating, content_width)

        if rating_layer:
            contents_layer.alpha_composite(rating_layer, (0, contents_composite_y))
            contents_composite_y = contents_composite_y + rating_layer.height + gutter

    contents_layer_box = contents_layer.getbbox()
    contents_layer_height = contents_layer_box[3] - contents_layer_box[1]

    contents_y = math.floor((IMG_HEIGHT - contents_layer_height) / 2)

    if show_instance_layer:
        # Remove Instance Layer from centering calculations
        contents_y = contents_y - math.floor((instance_layer.height + gutter) / 2)

    contents_y = max(contents_y, margin)

    # Composite layers
    img.paste(
        inner_img_layer, (inner_img_x, inner_img_y), inner_img_layer.convert("RGBA")
    )
    img.alpha_composite(contents_layer, (content_x, contents_y))

    return img.convert("RGB")


def save_and_cleanup(image, instance=None):
    """Save and close the file"""
    if not isinstance(instance, (models.Book, models.User, models.SiteSettings)):
        return False
    file_name = "%s-%s.jpg" % (str(instance.id), str(uuid4()))
    image_buffer = BytesIO()

    try:
        try:
            old_path = instance.preview_image.path
        except ValueError:
            old_path = ""

        # Save
        image.save(image_buffer, format="jpeg", quality=75)

        instance.preview_image = InMemoryUploadedFile(
            ContentFile(image_buffer.getvalue()),
            "preview_image",
            file_name,
            "image/jpg",
            image_buffer.tell(),
            None,
        )

        save_without_broadcast = isinstance(instance, (models.Book, models.User))
        if save_without_broadcast:
            instance.save(broadcast=False)
        else:
            instance.save()

        # Clean up old file after saving
        if os.path.exists(old_path):
            os.remove(old_path)

    finally:
        image_buffer.close()
    return True


# pylint: disable=invalid-name
@app.task
def generate_site_preview_image_task():
    """generate preview_image for the website"""
    if not settings.ENABLE_PREVIEW_IMAGES:
        return

    site = models.SiteSettings.objects.get()

    if site.logo:
        logo = site.logo
    else:
        logo = os.path.join(settings.STATIC_ROOT, "images/logo.png")

    texts = {
        "text_zero": settings.DOMAIN,
        "text_one": site.name,
        "text_three": site.instance_tagline,
    }

    image = generate_preview_image(texts=texts, picture=logo, show_instance_layer=False)

    save_and_cleanup(image, instance=site)


# pylint: disable=invalid-name
@app.task
def generate_edition_preview_image_task(book_id):
    """generate preview_image for a book"""
    if not settings.ENABLE_PREVIEW_IMAGES:
        return

    book = models.Book.objects.select_subclasses().get(id=book_id)

    rating = models.Review.objects.filter(
        privacy="public",
        deleted=False,
        book__in=[book_id],
    ).aggregate(Avg("rating"))["rating__avg"]

    texts = {
        "text_one": book.title,
        "text_two": book.subtitle,
        "text_three": book.author_text,
    }

    image = generate_preview_image(texts=texts, picture=book.cover, rating=rating)

    save_and_cleanup(image, instance=book)


@app.task
def generate_user_preview_image_task(user_id):
    """generate preview_image for a book"""
    if not settings.ENABLE_PREVIEW_IMAGES:
        return

    user = models.User.objects.get(id=user_id)

    texts = {
        "text_one": user.display_name,
        "text_three": "@{}@{}".format(user.localname, settings.DOMAIN),
    }

    if user.avatar:
        avatar = user.avatar
    else:
        avatar = os.path.join(settings.STATIC_ROOT, "images/default_avi.jpg")

    image = generate_preview_image(texts=texts, picture=avatar)

    save_and_cleanup(image, instance=user)
