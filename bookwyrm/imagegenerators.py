"""Generators for all the different thumbnail sizes"""

from imagekit import ImageSpec, register
from imagekit.processors import ResizeToFit


class BookXSmallWebp(ImageSpec):
    """Handles XSmall size in Webp format"""

    processors = [ResizeToFit(80, 80)]
    format = "WEBP"
    options = {"quality": 95}


class BookXSmallJpg(ImageSpec):
    """Handles XSmall size in Jpeg format"""

    processors = [ResizeToFit(80, 80)]
    format = "JPEG"
    options = {"quality": 95}


class BookSmallWebp(ImageSpec):
    """Handles Small size in Webp format"""

    processors = [ResizeToFit(100, 100)]
    format = "WEBP"
    options = {"quality": 95}


class BookSmallJpg(ImageSpec):
    """Handles Small size in Jpeg format"""

    processors = [ResizeToFit(100, 100)]
    format = "JPEG"
    options = {"quality": 95}


class BookMediumWebp(ImageSpec):
    """Handles Medium size in Webp format"""

    processors = [ResizeToFit(150, 150)]
    format = "WEBP"
    options = {"quality": 95}


class BookMediumJpg(ImageSpec):
    """Handles Medium size in Jpeg format"""

    processors = [ResizeToFit(150, 150)]
    format = "JPEG"
    options = {"quality": 95}


class BookLargeWebp(ImageSpec):
    """Handles Large size in Webp format"""

    processors = [ResizeToFit(200, 200)]
    format = "WEBP"
    options = {"quality": 95}


class BookLargeJpg(ImageSpec):
    """Handles Large size in Jpeg format"""

    processors = [ResizeToFit(200, 200)]
    format = "JPEG"
    options = {"quality": 95}


class BookXLargeWebp(ImageSpec):
    """Handles XLarge size in Webp format"""

    processors = [ResizeToFit(250, 250)]
    format = "WEBP"
    options = {"quality": 95}


class BookXLargeJpg(ImageSpec):
    """Handles XLarge size in Jpeg format"""

    processors = [ResizeToFit(250, 250)]
    format = "JPEG"
    options = {"quality": 95}


class BookXxLargeWebp(ImageSpec):
    """Handles XxLarge size in Webp format"""

    processors = [ResizeToFit(500, 500)]
    format = "WEBP"
    options = {"quality": 95}


class BookXxLargeJpg(ImageSpec):
    """Handles XxLarge size in Jpeg format"""

    processors = [ResizeToFit(500, 500)]
    format = "JPEG"
    options = {"quality": 95}


register.generator("bw:book:xsmall:webp", BookXSmallWebp)
register.generator("bw:book:xsmall:jpg", BookXSmallJpg)
register.generator("bw:book:small:webp", BookSmallWebp)
register.generator("bw:book:small:jpg", BookSmallJpg)
register.generator("bw:book:medium:webp", BookMediumWebp)
register.generator("bw:book:medium:jpg", BookMediumJpg)
register.generator("bw:book:large:webp", BookLargeWebp)
register.generator("bw:book:large:jpg", BookLargeJpg)
register.generator("bw:book:xlarge:webp", BookXLargeWebp)
register.generator("bw:book:xlarge:jpg", BookXLargeJpg)
register.generator("bw:book:xxlarge:webp", BookXxLargeWebp)
register.generator("bw:book:xxlarge:jpg", BookXxLargeJpg)
