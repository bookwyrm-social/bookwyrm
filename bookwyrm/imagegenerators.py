from imagekit import ImageSpec, register
from imagekit.processors import ResizeToFit


class BookXSmallWebp(ImageSpec):
    processors = [ResizeToFit(80, 80)]
    format = "WEBP"
    options = {"quality": 95}


class BookXSmallJpg(ImageSpec):
    processors = [ResizeToFit(80, 80)]
    format = "JPEG"
    options = {"quality": 95}


class BookSmallWebp(ImageSpec):
    processors = [ResizeToFit(100, 100)]
    format = "WEBP"
    options = {"quality": 95}


class BookSmallJpg(ImageSpec):
    processors = [ResizeToFit(100, 100)]
    format = "JPEG"
    options = {"quality": 95}


class BookMediumWebp(ImageSpec):
    processors = [ResizeToFit(150, 150)]
    format = "WEBP"
    options = {"quality": 95}


class BookMediumJpg(ImageSpec):
    processors = [ResizeToFit(150, 150)]
    format = "JPEG"
    options = {"quality": 95}


class BookLargeWebp(ImageSpec):
    processors = [ResizeToFit(200, 200)]
    format = "WEBP"
    options = {"quality": 95}


class BookLargeJpg(ImageSpec):
    processors = [ResizeToFit(200, 200)]
    format = "JPEG"
    options = {"quality": 95}


class BookXLargeWebp(ImageSpec):
    processors = [ResizeToFit(250, 250)]
    format = "WEBP"
    options = {"quality": 95}


class BookXLargeJpg(ImageSpec):
    processors = [ResizeToFit(250, 250)]
    format = "JPEG"
    options = {"quality": 95}


class BookXxLargeWebp(ImageSpec):
    processors = [ResizeToFit(500, 500)]
    format = "WEBP"
    options = {"quality": 95}


class BookXxLargeJpg(ImageSpec):
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
