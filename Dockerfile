FROM python:3.9

ENV PYTHONUNBUFFERED 1

RUN mkdir /app /app/static /app/images

WORKDIR /app

# Use RUN curl because ADD will re-download the file every time to make sure it
# hasn't changed, which is exactly what we don't want
RUN mkdir -p /app/static/fonts/source_han_sans
RUN curl \
  https://github.com/adobe-fonts/source-han-sans/raw/release/Variable/OTC/SourceHanSans-VF.ttf.ttc \
  -o /app/static/fonts/source_han_sans/SourceHanSans-VF.ttf.ttc

COPY requirements.txt /app/
RUN pip install -r requirements.txt --no-cache-dir
RUN apt-get update && apt-get install -y gettext libgettextpo-dev tidy && apt-get clean
