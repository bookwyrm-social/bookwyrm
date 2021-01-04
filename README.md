# BookWyrm

Social reading and reviewing, decentralized with ActivityPub

## Contents
 - [The overall idea](#the-overall-idea)
   - [What it is and isn't](#what-it-is-and-isnt)
   - [The role of federation](#the-role-of-federation)
   - [Features](#features)
 - [Setting up the developer environment](#setting-up-the-developer-environment)
 - [Installing in Production](#installing-in-production)
 - [Project structure](#project-structure)
 - [Book data](#book-data)
 - [Contributing](#contributing)

## The overall idea
### What it is and isn't
BookWyrm is a platform for social reading! You can use it to track what you're reading, review books, and follow your friends. It isn't  primarily meant for cataloguing or as a datasource for books, but it does do both of those things to some degree. 

### The role of federation
BookWyrm is built on [ActivityPub](http://activitypub.rocks/). With ActivityPub, it inter-operates with different instances of BookWyrm, and other ActivityPub compliant services, like Mastodon and Pixelfed. This means you can run an instance for your book club, and still follow your friend who posts on a server devoted to 20th century Russian speculative fiction. It also means that your friend on mastodon can read and comment on a book review that you post on your BookWyrm instance.

Federation makes it possible to have small, self-determining communities, in contrast to the monolithic service you find on GoodReads or Twitter. An instance can be focused on a particular type of literature, be just for use by people who are in a book club together, or anything else that brings people together. Each community can choose which other instances they want to federate with, and moderate and run their community autonomously. Check out https://runyourown.social/ to get a sense of the philosophy and logistics behind small, high-trust social networks.

### Features
Since the project is still in its early stages, not everything here is fully implemented. There is plenty of room for suggestions and ideas. Open an [issue](https://github.com/mouse-reeve/bookwyrm/issues) to get the conversation going!
 - Posting about books
    - Compose reviews, with or without ratings, which are aggregated in the book page
    - Compose other kinds of statuses about books, such as:
     - Comments on a book
     - Quotes or excerpts
     - Recommenations of other books
    - Reply to statuses
    - Aggregate reviews of a book across connected BookWyrm instances
    - Differentiate local and federated reviews and rating
 - Track reading activity
    - Shelve books on default "to-read," "currently reading," and "read" shelves
    - Create custom shelves
    - Store started reading/finished reading dates
    - Update followers about reading activity (optionally, and with granular privacy controls)
 - Federation with ActivityPub
    - Broadcast and receive user statuses and activity
    - Broadcast copies of books that can be used as canonical data sources
    - Identify shared books across instances and aggregate related content
    - Follow and interact with users across BookWyrm instances
    - Inter-operate with non-BookWyrm ActivityPub services
 - Granular privacy controls
    - Local-only, followers-only, and public posting
    - Option for users to manually approve followers
    - Allow blocking and flagging for moderation
    - Control which instances you want to federate with

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
    user.is_admin = True
    user.is_staff = True
    user.is_superuser = True
    user.save()
    ```
   - Go to the admin panel (`/admin/bookwyrm/sitesettings/1/change` on your domain) and set your instance name, description, code of conduct, and toggle whether registration is open on your instance


## Project structure
All the url routing is in `bookwyrm/urls.py`. This includes the application views (your home page, user page, book page, etc), application endpoints (things that happen when you click buttons), and federation api endpoints (inboxes, outboxes, webfinger, etc).

The application views and actions are in `bookwyrm/views.py`. The internal actions call api handlers which deal with federating content. Outgoing messages (any action done by a user that is federated out), as well as outboxes, live in `bookwyrm/outgoing.py`, and all handlers for incoming messages, as well as inboxes and webfinger, live in `bookwyrm/incoming.py`. Connection to openlibrary.org to get book data is handled in `bookwyrm/connectors/openlibrary.py`. ActivityPub serialization is handled in the `bookwyrm/activitypub/` directory.

Celery is used for background tasks, which includes receiving incoming ActivityPub activities, ActivityPub broadcasting, and external data import. 

The UI is all django templates because that is the default. You can replace it with a complex javascript framework over my ~dead body~ mild objections.


## Book data
The application is set up to get book data from arbitrary outside sources -- right now, it's only able to connect to OpenLibrary, but other connectors could be written. By default, a book is non-canonical copy of an OpenLibrary book, and will be updated with OpenLibrary if the data there changes. However, a book can edited and decoupled from its original data source, or added locally with no external data source.

There are three concepts in the book data model:
 - `Book`, an abstract, high-level concept that could mean either a `Work` or an `Edition`. No data is saved as a `Book`, it serves as shared model for `Work` and `Edition`
 - `Work`, the theoretical umbrella concept of a book that encompasses every edition of the book, and
 - `Edition`, a concrete, actually published version of a book
 
Whenever a user interacts with a book, they are interacting with a specific edition. Every work has a default edition, but the user can select other editions. Reviews aggregated for all editions of a work when you view an edition's page.


## Contributing
There are many ways you can contribute to this project! You are welcome and encouraged to create or contribute an issue to report a bug, request a feature, make a usability suggestion, or express a nebulous desire.

If you'd like to add to the codebase, that's super rad and you should do it! At this point, there isn't a formalized process, but you can take a look at the open issues, or contact me directly and chat about it.
