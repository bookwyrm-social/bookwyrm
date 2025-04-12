# BookWyrm

[![](https://img.shields.io/github/release/bookwyrm-social/bookwyrm.svg?colorB=58839b)](https://github.com/bookwyrm-social/bookwyrm/releases)
[![Run Python Tests](https://github.com/bookwyrm-social/bookwyrm/actions/workflows/django-tests.yml/badge.svg)](https://github.com/bookwyrm-social/bookwyrm/actions/workflows/django-tests.yml)
[![Pylint](https://github.com/bookwyrm-social/bookwyrm/actions/workflows/pylint.yml/badge.svg)](https://github.com/bookwyrm-social/bookwyrm/actions/workflows/pylint.yml)

BookWyrm is a social network for tracking your reading, talking about books, writing reviews, and discovering what to read next. Federation allows BookWyrm users to join small, trusted communities that can connect with one another, and with other ActivityPub services like [Mastodon](https://joinmastodon.org/) and [Pleroma](http://pleroma.social/).


## Links

[![Mastodon Follow](https://img.shields.io/mastodon/follow/000146121?domain=https%3A%2F%2Ftech.lgbt&style=social)](https://tech.lgbt/@bookwyrm)

 - [Project homepage](https://joinbookwyrm.com/)
 - [Support](https://patreon.com/bookwyrm)
 - [Documentation](https://docs.joinbookwyrm.com/)


## About BookWyrm
BookWyrm is a platform for social reading. You can use it to track what you're reading, review books, and follow your friends. It isn't primarily meant for cataloguing or as a data-source for books, but it does do both of those things to some degree.

## Federation
BookWyrm is built on [ActivityPub](http://activitypub.rocks/). With ActivityPub, it inter-operates with different instances of BookWyrm, and other ActivityPub compliant services, like Mastodon. This means you can run an instance for your book club, and still follow your friend who posts on a server devoted to 20th century Russian speculative fiction. It also means that your friend on mastodon can read and comment on a book review that you post on your BookWyrm instance.

Federation makes it possible to have small, self-determining communities, in contrast to the monolithic service you find on GoodReads or Twitter. An instance can be focused on a particular interest, be just for a group of friends, or anything else that brings people together. Each community can choose which other instances they want to federate with, and moderate and run their community autonomously. Check out https://runyourown.social/ to get a sense of the philosophy and logistics behind small, high-trust social networks.

Developers of other ActivityPub software can find out more about BookWyrm's implementation at [`FEDERATION.md`](https://github.com/bookwyrm-social/bookwyrm/blob/main/FEDERATION.md).

## Features

### Post about books
Compose reviews, comment on what you're reading, and post quotes from books. You can converse with other BookWyrm users across the network about what they're reading.

### Track reading activity
Keep track of what books you've read, and what books you'd like to read in the future.

### Federation with ActivityPub
Federation allows you to interact with users on other instances and services, and also shares metadata about books and authors, which collaboratively builds a decentralized database of books.

### Privacy and moderation
Users and administrators can control who can see their posts and what other instances to federate with.

## Tech Stack
Web backend
- [Django](https://www.djangoproject.com/) web server
- [PostgreSQL](https://www.postgresql.org/) database
- [ActivityPub](https://activitypub.rocks/) federation
- [Celery](https://docs.celeryproject.org/) task queuing
- [Redis](https://redis.io/) task backend
- [Redis (again)](https://redis.io/) activity stream manager

Front end
- Django templates
- [Bulma.io](https://bulma.io/) css framework
- Vanilla JavaScript, in moderation

Deployment
- [Docker](https://www.docker.com/) and docker-compose
- [Gunicorn](https://gunicorn.org/) web runner
- [Flower](https://github.com/mher/flower) celery monitoring
- [Nginx](https://nginx.org/en/) HTTP server


## Set up BookWyrm
The [documentation website](https://docs.joinbookwyrm.com/) has instruction on how to set up BookWyrm in a [developer environment](https://docs.joinbookwyrm.com/install-dev.html) or [production](https://docs.joinbookwyrm.com/install-prod.html).

## Contributing

There are many ways you can contribute to the success and health of the BookWyrm project! You do not have to know how to write code and we are always keen to see more people get involved. Find out how you can join the project at [CONTRIBUTING.md](https://github.com/bookwyrm-social/bookwyrm/blob/main/CONTRIBUTING.md)