# BookWyrm

Social reading and reviewing, decentralized with ActivityPub

## Contents
- [Joining BookWyrm](#joining-bookwyrm)
- [Contributing](#contributing)
- [About BookWyrm](#about-bookwyrm)
   - [What it is and isn't](#what-it-is-and-isnt)
   - [The role of federation](#the-role-of-federation)
   - [Features](#features)
 - [Setting up the developer environment](#setting-up-the-developer-environment)
 - [Installing in Production](#installing-in-production)
 - [Book data](#book-data)

## Joining BookWyrm
BookWyrm is still a young piece of software, and isn't at the level of stability and feature-richness that you'd find in a production-ready application. But it does what it says on the box! If you'd like to join an instance, you can check out the [instances](https://github.com/mouse-reeve/bookwyrm/blob/main/instances.md) list.

You can request an invite to https://bookwyrm.social by [email](mailto:mousereeve@riseup.net), [Mastodon direct message](https://friend.camp/@tripofmice), or [Twitter direct message](https://twitter.com/tripofmice).


## Contributing
See [contributing](https://github.com/mouse-reeve/bookwyrm/blob/main/CONTRIBUTING.md) for code, translation or monetary contributions.

## About BookWyrm
### What it is and isn't
BookWyrm is a platform for social reading! You can use it to track what you're reading, review books, and follow your friends. It isn't primarily meant for cataloguing or as a data-source for books, but it does do both of those things to some degree.

### The role of federation
BookWyrm is built on [ActivityPub](http://activitypub.rocks/). With ActivityPub, it inter-operates with different instances of BookWyrm, and other ActivityPub compliant services, like Mastodon. This means you can run an instance for your book club, and still follow your friend who posts on a server devoted to 20th century Russian speculative fiction. It also means that your friend on mastodon can read and comment on a book review that you post on your BookWyrm instance.

Federation makes it possible to have small, self-determining communities, in contrast to the monolithic service you find on GoodReads or Twitter. An instance can be focused on a particular interest, be just for a group of friends, or anything else that brings people together. Each community can choose which other instances they want to federate with, and moderate and run their community autonomously. Check out https://runyourown.social/ to get a sense of the philosophy and logistics behind small, high-trust social networks.

### Features
Since the project is still in its early stages, the features are growing every day, and there is plenty of room for suggestions and ideas. Open an [issue](https://github.com/mouse-reeve/bookwyrm/issues) to get the conversation going!
 - Posting about books
    - Compose reviews, with or without ratings, which are aggregated in the book page
    - Compose other kinds of statuses about books, such as:
     - Comments on a book
     - Quotes or excerpts
    - Reply to statuses
    - View aggregate reviews of a book across connected BookWyrm instances
    - Differentiate local and federated reviews and rating in your activity feed
 - Track reading activity
    - Shelve books on default "to-read," "currently reading," and "read" shelves
    - Create custom shelves
    - Store started reading/finished reading dates, as well as progress updates along the way
    - Update followers about reading activity (optionally, and with granular privacy controls)
    - Create lists of books which can be open to submissions from anyone, curated, or only edited by the creator
 - Federation with ActivityPub
    - Broadcast and receive user statuses and activity
    - Share book data between instances to create a networked database of metadata
    - Identify shared books across instances and aggregate related content
    - Follow and interact with users across BookWyrm instances
    - Inter-operate with non-BookWyrm ActivityPub services (currently, Mastodon is supported)
 - Granular privacy controls
    - Private, followers-only, and public privacy levels for posting, shelves, and lists
    - Option for users to manually approve followers
    - Allow blocking and flagging for moderation

### The Tech Stack
Web backend
 - [Django](https://www.djangoproject.com/) web server
 - [PostgreSQL](https://www.postgresql.org/) database
 - [ActivityPub](http://activitypub.rocks/) federation
 - [Celery](http://celeryproject.org/) task queuing
 - [Redis](https://redis.io/) task backend

Front end
 - Django templates
 - [Bulma.io](https://bulma.io/) css framework
 - Vanilla JavaScript, in moderation

Deployment
 - [Docker](https://www.docker.com/) and docker-compose
 - [Gunicorn](https://gunicorn.org/) web runner
 - [Flower](https://github.com/mher/flower) celery monitoring
 - [Nginx](https://nginx.org/en/) HTTP server

## Set up Bookwyrm

See the [installation instructions](https://github.com/mouse-reeve/bookwyrm/blob/main/INSTALLATION.md) on how to set up Bookwyrm in developer environment or production.
