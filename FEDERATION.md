# Federation

BookWyrm uses the [ActivityPub](http://activitypub.rocks/) protocol to send and receive user activity between other BookWyrm instances and other services that implement ActivityPub. To handle book data, BookWyrm has a handful of extended Activity types which are not part of the standard, but are legible to other BookWyrm instances.

## Activities and Objects

### Users and relationships
User relationship interactions follow the standard ActivityPub spec.

- `Follow`: request to receive statuses from a user, and view their statuses that have followers-only privacy
- `Accept`: approves a `Follow` and finalizes the relationship
- `Reject`: denies a `Follow`
- `Block`: prevent users from seeing one another's statuses, and prevents the blocked user from viewing the actor's profile
- `Update`: updates a user's profile and settings
- `Delete`: deactivates a user
- `Undo`: reverses a `Block` or `Follow`

### Activities
- `Create/Status`: saves a new status in the database.
- `Delete/Status`: Removes a status
- `Like/Status`: Creates a favorite on the status
- `Announce/Status`: Boosts the status into the actor's timeline
- `Undo/*`,: Reverses an `Announce`, `Like`, or `Move`
- `Move/User`: Moves a user from one ActivityPub id to another.

### Collections
User's books and lists are represented by [`OrderedCollection`](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollection)

### Statuses

BookWyrm is focused on book reading activities - it is not a general-purpose messaging application. For this reason, BookWyrm only accepts status `Create` activities if they are:

- Direct messages (i.e., `Note`s with the privacy level `direct`, which mention a local user),
- Related to a book (of a custom status type that includes the field `inReplyToBook`),
- Replies to existing statuses saved in the database

All other statuses will be received by the instance inbox, but by design **will not be delivered to user inboxes or displayed to users**.

### Custom Object types

With the exception of `Note`, the following object types are used in Bookwyrm but are not currently provided with a custom JSON-LD `@context` extension IRI. This is likely to change in future to make them true deserialisable JSON-LD objects.

##### Note

Within BookWyrm a `Note` is constructed according to [the ActivityStreams vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-note), however `Note`s can only be created as direct messages or as replies to other statuses. As mentioned above, this also applies to incoming `Note`s.

##### Review

A `Review` is a status in response to a book (indicated by the `inReplyToBook` field), which has a title, body, and numerical rating between 0 (not rated) and 5.

Example:

```json
{
    "id": "https://example.net/user/library_lurker/review/2",
    "type": "Review",
    "published": "2023-06-30T21:43:46.013132+00:00",
    "attributedTo": "https://example.net/user/library_lurker",
    "content": "<p>This is an enjoyable book with great characters.</p>",
    "to": ["https://example.net/user/library_lurker/followers"],
    "cc": [],
    "replies": {
        "id": "https://example.net/user/library_lurker/review/2/replies",
        "type": "OrderedCollection",
        "totalItems": 0,
        "first": "https://example.net/user/library_lurker/review/2/replies?page=1",
        "last": "https://example.net/user/library_lurker/review/2/replies?page=1",
        "@context": "https://www.w3.org/ns/activitystreams"
        },
        "summary": "Spoilers ahead!",
        "tag": [],
        "attachment": [],
        "sensitive": true,
    "inReplyToBook": "https://example.net/book/1",
    "name": "What a cracking read",
    "rating": 4.5,
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

##### Comment

A `Comment` on a book mentions a book and has a message body, reading status, and progress indicator.

Example:

```json
{
    "id": "https://example.net/user/library_lurker/comment/9",
    "type": "Comment",
    "published": "2023-06-30T21:43:46.013132+00:00",
    "attributedTo": "https://example.net/user/library_lurker",
    "content": "<p>This is a very enjoyable book so far.</p>",
    "to": ["https://example.net/user/library_lurker/followers"],
    "cc": [],
    "replies": {
        "id": "https://example.net/user/library_lurker/comment/9/replies",
        "type": "OrderedCollection",
        "totalItems": 0,
        "first": "https://example.net/user/library_lurker/comment/9/replies?page=1",
        "last": "https://example.net/user/library_lurker/comment/9/replies?page=1",
        "@context": "https://www.w3.org/ns/activitystreams"
        },
        "summary": "Spoilers ahead!",
        "tag": [],
        "attachment": [],
        "sensitive": true,
    "inReplyToBook": "https://example.net/book/1",
    "readingStatus": "reading",
    "progress": 25,
    "progressMode": "PG",
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

##### Quotation

A quotation (aka "quote") has a message body, an excerpt from a book including position as a page number or percentage indicator, and mentions a book.

Example:

```json
{
    "id": "https://example.net/user/mouse/quotation/13",
    "url": "https://example.net/user/mouse/quotation/13",
    "inReplyTo": null,
    "published": "2020-05-10T02:38:31.150343+00:00",
    "attributedTo": "https://example.net/user/mouse",
    "to": [
        "https://www.w3.org/ns/activitystreams#Public"
        ],
    "cc": [
        "https://example.net/user/mouse/followers"
        ],
    "sensitive": false,
    "content": "I really like this quote",
    "type": "Quotation",
    "replies": {
        "id": "https://example.net/user/mouse/quotation/13/replies",
        "type": "Collection",
        "first": {
            "type": "CollectionPage",
            "next": "https://example.net/user/mouse/quotation/13/replies?only_other_accounts=true&page=true",
            "partOf": "https://example.net/user/mouse/quotation/13/replies",
            "items": []
            }
        },
    "inReplyToBook": "https://example.net/book/1",
    "quote": "To be or not to be, that is the question.",
    "position": 50,
    "positionMode": "PCT",
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

### Custom Objects

##### Work
A particular book, a "work" in the [FRBR](https://en.wikipedia.org/wiki/Functional_Requirements_for_Bibliographic_Records) sense.

Example:

```json
{
    "id": "https://bookwyrm.social/book/5988",
    "type": "Work",
    "authors": [
        "https://bookwyrm.social/author/417"
    ],
    "first_published_date": null,
    "published_date": null,
    "title": "Piranesi",
    "sort_title": null,
    "subtitle": null,
    "description": "**From the *New York Times* bestselling author of *Jonathan Strange & Mr. Norrell*, an intoxicating, hypnotic new novel set in a dreamlike alternative reality.",
    "languages": [],
    "series": null,
    "series_number": null,
    "subjects": [
        "English literature"
    ],
    "subject_places": [],
    "openlibrary_key": "OL20893680W",
    "librarything_key": null,
    "goodreads_key": null,
    "attachment": [
        {
            "url": "https://bookwyrm.social/images/covers/10226290-M.jpg",
            "type": "Image"
        }
    ],
    "lccn": null,
    "editions": [
        "https://bookwyrm.social/book/5989"
    ],
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

##### Edition
A particular _manifestation_ of a Work, in the [FRBR](https://en.wikipedia.org/wiki/Functional_Requirements_for_Bibliographic_Records) sense.

Example:

```json
{
    "id": "https://bookwyrm.social/book/5989",
    "lastEditedBy": "https://example.net/users/rat",
    "type": "Edition",
    "authors": [
        "https://bookwyrm.social/author/417"
    ],
    "first_published_date": null,
    "published_date": "2020-09-15T00:00:00+00:00",
    "title": "Piranesi",
    "sort_title": null,
    "subtitle": null,
    "description": "Piranesi's house is no ordinary building; its rooms are infinite, its corridors endless, its walls are lined with thousands upon thousands of statues, each one different from all the others.",
    "languages": [
        "English"
    ],
    "series": null,
    "series_number": null,
    "subjects": [],
    "subject_places": [],
    "openlibrary_key": "OL29486417M",
    "librarything_key": null,
    "goodreads_key": null,
    "isfdb": null,
    "attachment": [
        {
            "url": "https://bookwyrm.social/images/covers/50202953._SX318_.jpg",
            "type": "Image"
        }
    ],
    "isbn_10": "1526622424",
    "isbn_13": "9781526622426",
    "oclc_number": null,
    "asin": null,
    "pages": 272,
    "physical_format": null,
    "publishers": [
        "Bloomsbury Publishing Plc"
    ],
    "work": "https://bookwyrm.social/book/5988",
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

#### Shelf

A user's book collection. By default, every user has a `to-read`, `reading`, `read`, and `stopped-reading` shelf which are used to track reading progress. Users may create an unlimited number of additional shelves with their own ids.

Example

```json
{
    "id": "https://example.net/user/avid_reader/books/extraspecialbooks-5",
    "type": "Shelf",
    "totalItems": 0,
    "first": "https://example.net/user/avid_reader/books/extraspecialbooks-5?page=1",
    "last": "https://example.net/user/avid_reader/books/extraspecialbooks-5?page=1",
    "name": "Extra special books",
    "owner": "https://example.net/user/avid_reader",
    "to": [
        "https://www.w3.org/ns/activitystreams#Public"
    ],
    "cc": [
        "https://example.net/user/avid_reader/followers"
    ],
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

#### List

A collection of books that may have items contributed by users other than the one who created the list.

Example:

```json
{
    "id": "https://example.net/list/1",
    "type": "BookList",
    "totalItems": 0,
    "first": "https://example.net/list/1?page=1",
    "last": "https://example.net/list/1?page=1",
    "name": "My cool list",
    "owner": "https://example.net/user/avid_reader",
    "to": [
        "https://www.w3.org/ns/activitystreams#Public"
    ],
    "cc": [
        "https://example.net/user/avid_reader/followers"
    ],
    "summary": "A list of books I like.",
    "curation": "curated",
    "@context": "https://www.w3.org/ns/activitystreams"
}
```

#### Activities

- `Create`: Adds a shelf or list to the database.
- `Delete`: Removes a shelf or list.
- `Add`: Adds a book to a shelf or list.
- `Remove`: Removes a book from a shelf or list.

## Alternative Serialization
Because BookWyrm uses custom object types that aren't listed in [the standard ActivityStreams Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary), some statuses are transformed into standard types when sent to or viewed by non-BookWyrm services. `Review`s are converted into `Article`s, and `Comment`s and `Quotation`s are converted into `Note`s, with a link to the book and the cover image attached.

In future this may be done with [JSON-LD type arrays](https://www.w3.org/TR/json-ld/#specifying-the-type) instead.

## Other extensions

### Webfinger

Bookwyrm uses the [Webfinger](https://datatracker.ietf.org/doc/html/rfc7033) standard to identify and disambiguate fediverse actors. The [Webfinger documentation on the Mastodon project](https://docs.joinmastodon.org/spec/webfinger/) provides a good overview of how Webfinger is used.

### HTTP Signatures

Bookwyrm uses and requires HTTP signatures for all `POST` requests. `GET` requests are not signed by default, but if Bookwyrm receives a `403` response to a `GET` it will re-send the request, signed by the default server user. This usually will have a user id of `https://example.net/user/bookwyrm.instance.actor`

#### publicKey id

In older versions of Bookwyrm the `publicKey.id` was incorrectly listed in request headers as `https://example.net/user/username#main-key`. As of v0.6.3 the id is now listed correctly, as `https://example.net/user/username/#main-key`. In most ActivityPub implementations this will make no difference as the URL will usually resolve to the same place.

### NodeInfo

Bookwyrm uses the [NodeInfo](http://nodeinfo.diaspora.software/) standard to provide statistics and version information for each instance.

## Further Documentation

See [docs.joinbookwyrm.com/](https://docs.joinbookwyrm.com/) for more documentation.