export const steps = [
    {
        title: gettext("Book shelves"),
        text: gettext("Book shelves are used to keep track of your reading activity. They are similar to lists, but are also used to create readthroughs.")
    },
    {
        title: gettext("Default shelves"),
        text: gettext("'To Read', 'Currently Reading', 'Read' and 'Stopped Reading' are all default shelves and cannot be deleted. These are used to keep track of your reading." ),
        attachTo: {
            element: "#user-shelves",
            on: "bottom",
        }
    },
    {
        title: gettext("Custom shelves"),
        text: gettext("You can create an unlimited number of custom shelves to organise your books however you like. Before creating a shelf, consider whether a List suits your needs better." ),
        attachTo: {
            element: "#create-shelf-button",
            on: "left",
        },
        extraHighlights: ['a[href="/list"]']
    },
    {
        title: gettext("Edit"),
        text: gettext("You can change the name, description, and privacy levels for each shelf." ),
        attachTo: {
            element: "#edit-shelf-button",
            on: "left",
        }
    },
    {
        title: gettext("Filters"),
        text: gettext("For shelves with many books, you can filter by keywords to find the book you are looking for." ),
        attachTo: {
            element: "#filters-panel",
            on: "top",
        }
    },
    {
        title: gettext("Import"),
        text: gettext("Books can be imported from another service like Goodreads or LibraryThing by uploading an export file." ),
        attachTo: {
            element: "#import-books",
            on: "bottom",
        }
    },
]