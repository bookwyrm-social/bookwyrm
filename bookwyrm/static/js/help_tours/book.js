export const steps = [
    {
        text: gettext("This is home page of a book. Let's see what you can do while you're here!"),
        title: gettext('Book page'),
    },
    {
        text: gettext('If the cover or description are missing you can updated them straight from this page. To edit more details, use the Edit Edition button.'),
        title: gettext('Edit book details'),
        attachTo: {
            element: "#edit-book-button",
            on: "left",
        },
        extraHighlights: [ 'button[data-controls^="add_description"]', '.book-cover']
    },
    {
        text: gettext('This is where you can set a reading status for this book. You can press the button to move to the next stage, or use the drop down button to select the reading status you want to set.'),
        title: gettext('Reading status'),
        attachTo: {
            element: "#shelve-button",
            on: "right",
        }
    },
    {
        text: gettext("You can also manually add reading dates here. Unlike changing the reading status, adding dates manually will not automatically add them to a shelf. Have a favourite book you re-read every year? We've got you covered - you can add multiple read dates for the same book 😀"),
        title: gettext('Add read dates'),
        attachTo: {
            element: "#add-readthrough-button",
            on: "top",
        },
    },
    {
        text: gettext('There can be multiple editions of a book, in various formats or languages. Click this link to choose which edition you want to use, or to edit the parent work.'),
        title: gettext('Other editions'),
        attachTo: {
            element: "#other-editions-link",
            on: "top",
        },
    },
    {
        text: gettext('Here you will find reviews and comments from other users.'),
        title: gettext('Read what other people think'),
        attachTo: {
            element: "#reviews-header",
            on: "right",
        },
        extraHighlights: [ "#reviews"]
    },
    {
        text: gettext('You can post your own review, comment, or quote here.'),
        title: gettext('Share your thoughts'),
        attachTo: {
            element: "#review-comment-quote",
            on: "right",
        },
    },
    {
        text: gettext('Know the perfect book for people who liked this one? Make a recommendation here.'),
        title: gettext('Suggest something similar'),
        attachTo: {
            element: "#suggestion-list-block",
            on: "left",
        },
    },

    {
        text: gettext('Some ebooks can be downloaded for free from external sources. They will be shown here.'),
        title: gettext('Download links'),
        attachTo: {
            element: "#book-file-links",
            on: "left",
        },
    }
]