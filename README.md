# fedireads

Social reading and reviewing, decentralized with ActivityPub

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
