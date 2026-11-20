export const steps = [
    {
        text: gettext('If the cover or description are missing you can updated them straight from this page. To edit more details, use this button.'),
        title: gettext('Edit book details'),
        attachTo: {
            element: "#edit-book-button",
            on: "left",
        },
        scrollTo: false,
        extraHighlights: [ 'button[data-controls^="add_description"]', '.book-cover'],
        buttons: [
            {
                action() {
                    return this.next();
                },
                text: gettext("Next"),
                classes: "is-primary"
            },
        ]
    },
    {
        text: gettext('This is where you can set a reading status for this book. You can press the button to progress to the next stage, or use the drop down button to select the reading status you want to set.'),
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
        text: gettext('There can be multiple editions of a book, in various formats or languages. Choose which edition you want to use, or to edit the parent work.'),
        title: gettext('Other editions'),
        attachTo: {
            element: "#other-editions-link",
            on: "top",
        },
    },
    {
        text: gettext('Check out reviews and comments from other users.'),
        title: gettext('Read what other people think'),
        attachTo: {
            element: "#reviews-header",
            on: "right",
        },
        extraHighlights: [ "#reviews"]
    },
    {
        text: gettext('Post your own review, comment, or quote here.'),
        title: gettext('Share your thoughts'),
        attachTo: {
            element: "#review-comment-quote",
            on: "right",
        },
    },
    {
        text: gettext('Know the perfect book for people who liked this one? Make a recommendation!'),
        title: gettext('Suggest something similar'),
        attachTo: {
            element: "#suggestion-list-block",
            on: "left",
        },
    },

    {
        text: gettext('Some eBooks can be downloaded from external sources.'),
        title: gettext('Download links'),
        attachTo: {
            element: "#book-file-links",
            on: "left",
        },
    }
]