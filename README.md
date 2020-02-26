# FediReads

Social reading and reviewing, decentralized with ActivityPub

## Contents
 - [The overall idea](#the-overall-idea)
   - [What it is and isn't](#what-it-is-and-isnt)
   - [The role of federation](#the-role-of-federation)
   - [Features](#features)
 - [Setting up the developer environment](#setting-up-the-developer-environment)
 - [Project structure](#project-structure)
 - [Contributing](#contributing)

## The overall idea
### What it is and isn't
FediReads is meant to be a platform for social reading; specifically, for tracking what you're reading and sharing your updates with friends, and reviewing and commenting on books. It isn't meant primarily for cataloguing or as a datasource for books, but it may incidentally act in that way even when that isn't the focus of the software. For example, listing books you've read can be a way for you to catalog their personal reading, even though the feature is designed with the intent of sharing updates on what you've read.

### The role of federation
FediReads is built on [ActivityPub](http://activitypub.rocks/) and uses that standard to inter-operate between different instances of FediReads run on different servers by different people, and to inter-operate with other ActivityPub compliant services, like Mastodon and Pixelfed. This means, for example, that your friend on mastodon can read and comment on your Fedireads book review.

Federation also makes it possible to have small, self-determining communities, as opposed to a monolithic service like you find on GoodReads or Twitter. An instance could be focused on a particular type of literature, just for use by people who are in a book club together, or anything else that brings them together. Each community can choose what other instances they want to federate with, and moderate and run their community autonomously. Check out https://runyourown.social/ to get a sense of the philosophy I'm working from for how social networks out to be.

### Features
This project is still in its very early stages, but these are the higher-level features it should have:
 - Book reviews
    - Post and comment on reviews
    - Find reviews of a book across connected FediReads instances
    - Differentiate local and federated reviews and rating
 - Track reading activity
    - Store "shelves" that list books a user wants to read/is reading/has read
    - Allow users to create their own shelves
    - Update followers about user activity (optionally, and with granular privacy controls)
    - Allow users to comment on reading activity (optionally, and with granular privacy controls)
 - Federation with ActivityPub
    - Identify shared books across instances
    - Follow and interact across FediReads instances
    - Inter-operate with non-FediReads ActivityPub services
 - Granular privacy controls
    - Local-only, followers-only, and public posting
    - Option for users to manually approve followers
    - Allow blocking and flagging for moderaton
    - Control over which instances you want to federate with

But this isn't a set in stone, unchangeable list, so if you have ideas about how this could be tweaked, changed, or improved, please open an issue and start a conversation about it.

## Setting up the developer environment
You will need postgres installed and running on your computer.

``` bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb fedireads
```

Create the psql user in `psql fedireads`:
``` psql
CREATE ROLE fedireads WITH LOGIN PASSWORD 'fedireads';
GRANT ALL PRIVILEGES ON DATABASE fedireads TO fedireads;
```

Initialize the database (or, more specifically, delete the existing database, run migrations, and start fresh):
``` bash
./rebuilddb.sh
```
This creates two users, `mouse` with password `password123` and `rat` with password `ratword`.

And go to the app at `localhost:8000`

For most testing, you'll want to use ngrok. Remember to set the DOMAIN in `.env` to your ngrok domain.


## Project structure

All the url routing is in `fedireads/urls.py`. This includes the application views (your home page, user page, book page, etc), application endpoints (things that happen when you click buttons), and federation api endpoints (inboxes, outboxes, webfinger, etc).

The application views and actions are in `fedireads/views.py`. The internal actions call api handlers which deal with federating content. Outgoing messages (any action done by a user that is federated out), as well as outboxes, live in `fedireads/outgoing.py`, and all handlers for incoming messages, as well as inboxes and webfinger, live in `fedireads/incoming.py`. Connection to openlibrary.org to get book data is handled in `fedireads/openlibrary.py`. ActivityPub serialization is handled in the `activitypub/` directory.

There's some organization/refactoring work to be done to clarify the separation of concerns and keep the code readable and well organized.

The UI is all django templates because that is the default. You can replace it with a complex javascript framework over my ~dead body~ mild objections.


## Contributing
There are many ways you can contribute to this project! You are welcome and encouraged to create or contribute a github issue to report a bug, request a feature, make a usability suggestion, or express a nevulous desire.

If you'd like to add to the codebase, the issues are a good place to start to get a sense of what needs to be done -- feel free to ask questions and tag @mouse-reeve. This isn't a formalized process at this point.
