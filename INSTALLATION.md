# Installation instructions


## Setting up the developer environment

Set up the development environment file:

``` bash
cp .env.dev.example .env
```

Set up nginx for development `nginx/default.conf`:
``` bash
cp nginx/development nginx/default.conf
```

For most testing, you'll want to use ngrok. Remember to set the DOMAIN in `.env` to your ngrok domain.

You'll have to install the Docker and docker-compose. When you're ready, run:

```bash
docker-compose build
docker-compose run --rm web python manage.py migrate
docker-compose run --rm web python manage.py initdb
docker-compose up
```

Once the build is complete, you can access the instance at `http://localhost:1333`

### Editing static files
If you edit the CSS or JavaScript, you will need to run Django's `collectstatic` command in order for your changes to have effect. You can do this by running:
``` bash
./bw-dev collectstatic
```

If you have [installed yarn](https://yarnpkg.com/getting-started/install), you can run `yarn watch:static` to automatically run the previous script every time a change occurs in _bookwyrm/static_ directory.

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
- Switch to the `production` branch:
    `git checkout production`
- Create your environment variables file, `cp .env.prod.example .env`, and update the following:
    - `SECRET_KEY` | A difficult to guess, secret string of characers
    - `DOMAIN` | Your web domain
    - `EMAIL` | Email address to be used for certbot domain verification
    - `POSTGRES_PASSWORD` | Set a secure password for the database
    - `REDIS_ACTIVITY_PASSWORD` | Set a secure password for Redis Activity subsystem
    - `REDIS_BROKER_PASSWORD` | Set a secure password for Redis queue broker subsystem
    - `FLOWER_USER` | Your own username for accessing Flower queue monitor
    - `FLOWER_PASSWORD` | Your own secure password for accessing Flower queue monitor
- Update your nginx configuration in `nginx/default.conf`
    - Replace `your-domain.com` with your domain name
- Configure nginx
    - Make a copy of the production template config and set it for use in nginx `cp nginx/production nginx/default.conf`
    - Update `nginx/default.conf`:
        - Replace `your-domain.com` with your domain name
        - If you aren't using the `www` subdomain, remove the www.your-domain.com version of the domain from the `server_name` in the first server block in `nginx/default.conf` and remove the `-d www.${DOMAIN}` flag at the end of the `certbot` command in `docker-compose.yml`.
        - If you are running another web-server on your host machine, you will need to follow the [reverse-proxy instructions](#running-bookwyrm-behind-a-reverse-proxy)
- If you need to initialize your certbot for your domain, set `CERTBOT_INIT=true` in your `.env` file
- Run the application (this should also set up a Certbot ssl cert for your domain) with
    `docker-compose up --build`, and make sure all the images build successfully
    - If you are running other services on your host machine, you may run into errors where services fail when attempting to bind to a port.
    See the [troubleshooting guide](#port-conflicts) for advice on resolving this.
- When docker has built successfully, stop the process with `CTRL-C`
- If you set `CERTBOT_INIT=true` earlier, set it now as `CERTBOT_INIT=false` so that certbot runs in renew mode
- Run docker-compose in the background with: `docker-compose up -d`
- Initialize the database with: `./bw-dev initdb`
- Set up schedule backups with cron that runs that `docker-compose exec db pg_dump -U <databasename>` and saves the backup to a safe location

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
