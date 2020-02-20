# FediReads

Social reading and reviewing, decentralized with ActivityPub

## The overall idea
### What it is an isn't
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


## Structure

All the url routing is in `fedireads/urls.py`. This includes the application views (your home page, user page, book page, etc),
application endpoints (things that happen when you click buttons), and federation api endpoints (inboxes, outboxes, webfinger, etc).

The application views and actions are in `fedireads/views.py`. The internal actions call api handlers which deal with federating content.
Outgoing messages (any action done by a user that is federated out), as well as outboxes, live in `fedireads/outgoing.py`, and all handlers for incoming
messages, as well as inboxes and webfinger, live in `fedireads/incoming.py`. Connection to openlibrary.org to get book data is handled in `fedireads/openlibrary.py`.

The UI is all django templates because that is the default. You can replace it with a complex javascript framework over my ~dead body~ mild objections.


## Thoughts and considerations

### What even are books
It's important for this application to function that books can be identified reliably across different instances. I'm using OpenLibrary.org data, which works well (thanks OpenLibrary!) and I'm treating it as canonical and not the copies in the local databases. This means that instances will be consistent, but the major downside is that if users want to modify books or add books that aren't available, they need to do it on OpenLibrary, rather than their own instance.

### Explain "review"
There's no actual reason to be beholden to simple 5 star reviews with a text body. Are there other ways of thinking about a review
that could be represented in a database?
