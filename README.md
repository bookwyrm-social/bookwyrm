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

## Contributing
There are many ways you can contribute to this project, regardless of your level of technical expertise.

### Feedback and feature requests
Please feel encouraged and welcome to point out bugs, suggestions, feature requests, and ideas for how things ought to work using [GitHub issues](https://github.com/mouse-reeve/bookwyrm/issues).

### Code contributions
Code contributions are gladly welcomed! If you're not sure where to start, take a look at the ["Good first issue"](https://github.com/mouse-reeve/bookwyrm/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) tag. Because BookWyrm is a small project, there isn't a lot of formal structure, but there is a huge capacity for one-on-one support, which can look like asking questions as you go, pair programming, video chats, et cetera, so please feel free to reach out.

If you have questions about the project or contributing, you can set up a video call during BookWyrm ["office hours"](https://calendly.com/mouse-reeve/30min).

### Translation
Do you speak a language besides English? BookWyrm needs localization! If you're comfortable using git and want to get into the code, there are [instructions](#working-with-translations-and-locale-files) on how to create and edit localization files. If you feel more comfortable working in a regular text editor and would prefer not to run the application, get in touch directly and we can figure out a system, like emailing a text file, that works best.

### Financial Support
BookWyrm is an ad-free passion project with no intentions of seeking out venture funding or corporate financial relationships. If you want to help keep the project going, you can donate to the [Patreon](https://www.patreon.com/bookwyrm), or make a one time gift via [PayPal](https://paypal.me/oulipo).

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

### Editing static files
If you edit the CSS or JavaScript, you will need to run Django's `collectstatic` command in order for your changes to have effect. You can do this by running:
``` bash
./bw-dev collectstatic
```

### Working with translations and locale files
Text in the html files are wrapped in translation tags (`{% trans %}` and `{% blocktrans %}`), and Django generates locale files for all the strings in which you can add translations for the text. You can find existing translations in the `locale/` directory.

The application's language is set by a request header sent by your browser to the application, so to change the language of the application, you can change the default language requested by your browser.

#### Adding a locale
To start translation into a language which is currently supported, run the django-admin `makemessages` command with the language code for the language you want to add (like `de` for German, or `en-gb` for British English):
``` bash
./bw-dev makemessages -l <language code>
```

#### Editing a locale
When you have a locale file, open the `django.po` in the directory for the language (for example, if you were adding German, `locale/de/LC_MESSAGES/django.po`. All the the text in the application will be shown in paired strings, with `msgid` as the original text, and `msgstr` as the translation (by default, this is set to an empty string, and will display the original text).

Add your translations to the `msgstr` strings. As the messages in the application are updated, `gettext` will sometimes add best-guess fuzzy matched options for those translations. When a message is marked as fuzzy, it will not be used in the application, so be sure to remove it when you translate that line.

When you're done, compile the locale by running:

``` bash
./bw-dev compilemessages
```

You can add the `-l <language code>` to only compile one language. When you refresh the application, you should see your translations at work.

## Installing in Production

This project is still young and isn't, at the moment, very stable, so please proceed with caution when running in production.

### Server setup
- Get a domain name and set up DNS for your server
- Set your server up with appropriate firewalls for running a web application (this instruction set is tested against Ubuntu 20.04)
- Set up an email service (such as mailgun) and the appropriate SMTP/DNS settings
- Install Docker and docker-compose

### Install and configure BookWyrm

The `production` branch of BookWyrm contains a number of tools not on the `main` branch that are suited for running in production, such as `docker-compose` changes to update the default commands or configuration of containers, and individual changes to container config to enable things like SSL or regular backups.

Instructions for running BookWyrm in production:

- Get the application code:
    `git clone git@github.com:mouse-reeve/bookwyrm.git`
- Switch to the `production` branch
    `git checkout production`
- Create your environment variables file
    `cp .env.example .env`
    - Add your domain, email address, SMTP credentials
    - Set a secure redis password and secret key
    - Set a secure database password for postgres
- Update your nginx configuration in `nginx/default.conf`
    - Replace `your-domain.com` with your domain name
- Run the application (this should also set up a Certbot ssl cert for your domain) with
    `docker-compose up --build`, and make sure all the images build successfully
- When docker has built successfully, stop the process with `CTRL-C`
- Comment out the `command: certonly...` line in `docker-compose.yml`
- Run docker-compose in the background with: `docker-compose up -d`
- Initialize the database with: `./bw-dev initdb`
- Set up schedule backups with cron that runs that `docker-compose exec db pg_dump -U <databasename>` and saves the backup to a safe location
- Get the application code:
    `git clone git@github.com:mouse-reeve/bookwyrm.git`
- Switch to the `production` branch
    `git checkout production`
- Create your environment variables file
    `cp .env.example .env`
    - Add your domain, email address, SMTP credentials
    - Set a secure redis password and secret key
    - Set a secure database password for postgres
- Update your nginx configuration in `nginx/default.conf`
    - Replace `your-domain.com` with your domain name
    - If you aren't using the `www` subdomain, remove the www.your-domain.com version of the domain from the `server_name` in the first server block in `nginx/default.conf` and remove the `-d www.${DOMAIN}` flag at the end of the `certbot` command in `docker-compose.yml`.
    - If you are running another web-server on your host machine, you will need to follow the [reverse-proxy instructions](#running-bookwyrm-behind-a-reverse-proxy)
- Run the application (this should also set up a Certbot ssl cert for your domain) with
    `docker-compose up --build`, and make sure all the images build successfully
    - If you are running other services on your host machine, you may run into errors where services fail when attempting to bind to a port.
    See the [troubleshooting guide](#port-conflicts) for advice on resolving this.
- When docker has built successfully, stop the process with `CTRL-C`
- Comment out the `command: certonly...` line in `docker-compose.yml`, and uncomment the following line (`command: renew ...`) so that the certificate will be automatically renewed.
- Uncomment the https redirect and `server` block in `nginx/default.conf` (lines 17-48).
- Run docker-compose in the background with: `docker-compose up -d`
- Initialize the database with: `./bw-dev initdb`

Congrats! You did it, go to your domain and enjoy the fruits of your labors.

### Configure your instance
- Register a user account in the application UI
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

### Backups

BookWyrm's db service dumps a backup copy of its database to its `/backups` directory daily at midnight UTC.
Backups are named `backup__%Y-%m-%d.sql`.

The db service has an optional script for periodically pruning the backups directory so that all recent daily backups are kept, but for older backups, only weekly or monthly backups are kept.
To enable this script:
- Uncomment the final line in `postgres-docker/cronfile`
- rebuild your instance `docker-compose up --build`

You can copy backups from the backups volume to your host machine with `docker cp`:
- Run `docker-compose ps` to confirm the db service's full name (it's probably `bookwyrm_db_1`.
- Run `docker cp <container_name>:/backups <host machine path>`

### Updating your instance

When there are changes available in the production branch, you can install and get them running on your instance using the command `./bw-dev update`. This does a number of things:
- `git pull` gets the updated code from the git repository. If there are conflicts, you may need to run `git pull` separately and resolve the conflicts before trying the `./bw-dev update` script again.
- `docker-compose build` rebuilds the images, which ensures that the correct packages are installed. This step takes a long time and is only needed when the dependencies (including pip `requirements.txt` packages) have changed, so you can comment it out if you want a quicker update path and don't mind un-commenting it as needed.
- `docker-compose exec web python manage.py migrate` runs the database migrations in Django
- `docker-compose exec web python manage.py collectstatic --no-input` loads any updated static files (such as the JavaScript and CSS)
- `docker-compose restart` reloads the docker containers

### Re-building activity streams

If something goes awry with user timelines, and you want to re-create them en mass, there's a management command for that:
`docker-compose run --rm web python manage.py rebuild_feeds`

### Port Conflicts

BookWyrm has multiple services that run on their default ports.
This means that, depending on what else you are running on your host machine, you may run into errors when building or running BookWyrm when attempts to bind to those ports fail.

If this occurs, you will need to change your configuration to run services on different ports.
This may require one or more changes the following files:
- `docker-compose.yml`
- `nginx/default.conf`
- `.env` (You create this file yourself during setup)

E.g., If you need Redis to run on a different port:
- In `docker-compose.yml`:
    - In `services` -> `redis` -> `command`, add `--port YOUR_PORT` to the command
    - In `services` -> `redis` -> `ports`, change `6379:6379` to your port
- In `.env`, update `REDIS_PORT`

If you are already running a web-server on your machine, you will need to set up a reverse-proxy.

#### Running BookWyrm Behind a Reverse-Proxy

If you are running another web-server on your machine, you should have it handle proxying web requests to BookWyrm.

The default BookWyrm configuration already has an nginx server that proxies requests to the django app that handles SSL and directly serves static files.
The static files are stored in a Docker volume that several BookWyrm services access, so it is not recommended to remove this server completely.

To run BookWyrm behind a reverse-proxy, make the following changes:
- In `nginx/default.conf`:
    - Comment out the two default servers
    - Uncomment the server labeled Reverse-Proxy server
    - Replace `your-domain.com` with your domain name
- In `docker-compose.yml`:
    - In `services` -> `nginx` -> `ports`, comment out the default ports and add `- 8001:8001`
    - In `services` -> `nginx` -> `volumes`, comment out the two volumes that begin `./certbot/`
    - In `services`, comment out the `certbot` service

At this point, you can follow, the [setup](#server-setup) instructions as listed.
Once docker is running, you can access your BookWyrm instance at `http://localhost:8001` (**NOTE:** your server is not accessible over `https`).

Steps for setting up a reverse-proxy are server dependent.

##### Nginx

Before you can set up nginx, you will need to locate your nginx configuration directory, which is dependent on your platform and how you installed nginx.
See [nginx's guide](http://nginx.org/en/docs/beginners_guide.html) for details.

To set up your server:
- In you `nginx.conf` file, ensure that `include servers/*;` isn't commented out.
- In your nginx `servers` directory, create a new file named after your domain containing the following information:
    ```nginx
    server {
        server_name your-domain.com www.your-domain.com;

        location / {
            proxy_pass http://localhost:8000;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $host;
        }

        location /images/ {
            proxy_pass http://localhost:8001;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $host;
        }

        location /static/ {
            proxy_pass http://localhost:8001;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $host;
        }

        listen [::]:80 ssl;
        listen 80 ssl;
    }
    ```
- run `sudo certbot run --nginx --email YOUR_EMAIL -d your-domain.com -d www.your-domain.com`
- restart nginx

If everything worked correctly, your BookWyrm instance should now be externally accessible.


## Book data
The application is set up to share book and author data between instances, and get book data from arbitrary outside sources. Right now, the only connector is to OpenLibrary, but other connectors could be written.

There are three concepts in the book data model:
- `Book`, an abstract, high-level concept that could mean either a `Work` or an `Edition`. No data is saved as a `Book`, it serves as shared model for `Work` and `Edition`
- `Work`, the theoretical umbrella concept of a book that encompasses every edition of the book, and
- `Edition`, a concrete, actually published version of a book

Whenever a user interacts with a book, they are interacting with a specific edition. Every work has a default edition, but the user can select other editions. Reviews aggregated for all editions of a work when you view an edition's page.
