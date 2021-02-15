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
There are many ways you can contribute to this project, regardless of your level of technical expertise. 

### Feedback and feature requests
Please feel encouraged and welcome to point out bugs, suggestions, feature requests, and ideas for how things ought to work using [GitHub issues](https://github.com/mouse-reeve/bookwyrm/issues).

### Code contributions
Code contributons are gladly welcomed! If you're not sure where to start, take a look at the ["Good first issue"](https://github.com/mouse-reeve/bookwyrm/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) tag. Because BookWyrm is a small project, there isn't a lot of formal structure, but there is a huge capacity for one-on-one support, which can look like asking questions as you go, pair programming, video chats, et cetera, so please feel free to reach out.

If you have questions about the project or contributing, you can seet up a video call during BookWyrm ["office hours"](https://calendly.com/mouse-reeve/30min).

### Financial Support
BookWyrm is an ad-free passion project with no intentions of seeking out venture funding or corporate financial relationships. If you want to help keep the project going, you can donate to the [Patreon](https://www.patreon.com/bookwyrm), or make a one time gift via [PayPal](https://paypal.me/oulipo).

## About BookWyrm
### What it is and isn't
BookWyrm is a platform for social reading! You can use it to track what you're reading, review books, and follow your friends. It isn't  primarily meant for cataloguing or as a datasource for books, but it does do both of those things to some degree. 

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

## Setting up the developer environment

Set up the environment file:

``` bash
cp .env.example .env
```

For most testing, you'll want to use ngrok. Remember to set the DOMAIN in `.env` to your ngrok domain.

You'll have to install the Docker and docker-compose. When you're ready, run:

```bash
docker-compose build
docker-compose run --rm web python manage.py migrate
docker-compose run --rm web python manage.py initdb
docker-compose up
```

Once the build is complete, you can access the instance at `localhost:1333`

## Installing in Production

This project is still young and isn't, at the momoment, very stable, so please procede with caution when running in production.
### Server setup
 - Get a domain name and set up DNS for your server
 - Set your server up with appropriate firewalls for running a web application (this instruction set is tested again Ubuntu 20.04)
 - Set up a mailgun account and the appropriate DNS settings
 - Install Docker and docker-compose
### Install and configure BookWyrm
 - Get the application code:
  `git clone git@github.com:mouse-reeve/bookwyrm.git`
 - Switch to the `production` branch
  `git checkout production`
 - Create your environment variables file
  `cp .env.example .env`
   - Add your domain, email address, mailgun credentials
   - Set a secure redis password and secret key
   - Set a secure database password for postgres
 - Update your nginx configuration in `nginx/default.conf`
   - Replace `your-domain.com` with your domain name
 - Run the application (this should also set up a Certbot ssl cert for your domain)
  `docker-compose up --build`
  Make sure all the images build successfully
 - When docker has built successfully, stop the process with `CTRL-C`
 - Comment out the `command: certonly...` line in `docker-compose.yml`
 - Run docker-compose in the background
  `docker-compose up -d`
 - Initialize the database
  `./bw-dev initdb`
 - Set up schedule backups with cron that runs that `docker-compose exec db pg_dump -U <databasename>` and saves the backup to a safe locationgi
 - Congrats! You did it, go to your domain and enjoy the fruits of your labors
### Configure your instance
 - Register a user account in the applcation UI
 - Make your account a superuser (warning: do *not* use django's `createsuperuser` command)
   - On your server, open the django shell
    `./bw-dev shell`
   - Load your user and make it a superuser
    ```python
    from bookwyrm import models
    user = models.User.objects.get(id=1)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    ```
   - Go to the site settings (`/settings/site-settings` on your domain) and configure your instance name, description, code of conduct, and toggle whether registration is open on your instance


## Book data
The application is set up to share book and author data between instances, and get book data from arbitrary outside sources. Right now, the only connector is to OpenLibrary, but other connectors could be written.

There are three concepts in the book data model:
 - `Book`, an abstract, high-level concept that could mean either a `Work` or an `Edition`. No data is saved as a `Book`, it serves as shared model for `Work` and `Edition`
 - `Work`, the theoretical umbrella concept of a book that encompasses every edition of the book, and
 - `Edition`, a concrete, actually published version of a book
 
Whenever a user interacts with a book, they are interacting with a specific edition. Every work has a default edition, but the user can select other editions. Reviews aggregated for all editions of a work when you view an edition's page.
