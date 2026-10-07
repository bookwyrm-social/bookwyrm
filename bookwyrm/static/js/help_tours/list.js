export const steps = [
    {
        title: gettext("List page"),
        text: gettext("This is a book list page. Users can create lists of books for any reason.")
    },
    {
        title: gettext("List items"),
        text: gettext("Curators can order books in the list, and add notes on each book." ),
        attachTo: {
            element: "#list-items-block",
            on: "top",
        }
    },
    {
        title: gettext("Add books"),
        text: gettext("Search for books to add or suggest" ),
        attachTo: {
            element: "#booklist-add-searchbox",
            on: "left",
        }
    },
    {
        title: gettext("Add books"),
        text: gettext("...or pick one of the suggested titles." ),
        attachTo: {
            element: "#booklist-add-suggestion",
            on: "left",
        }
    },
    {
        title: gettext("Edit"),
        text: gettext("You can edit your own lists to change the name and add a description. Lists have multiple privacy options, and curation can be private, by approval, open to anyone, or managed collectively by a group." ),
        attachTo: {
            element: "#edit-list-button",
            on: "left",
        }
    },
    {
        title: gettext("Sorting"),
        text: gettext("Lists have a default order determined by curators, but you can also sort them by book title and average rating." ),
        attachTo: {
            element: "#sort-list-form",
            on: "left",
        }
    },
    {
        title: gettext("Embed code"),
        text: gettext("You can display any list on your own website by using the embed code" ),
        attachTo: {
            element: "#embed-block",
            on: "left",
        }
    },
    {
        title: gettext("Bookmark this list"),
        text: gettext("Love this list? Save or bookmark it to your saved lists so you can find it later." ),
        attachTo: {
            element: "#save-list-button",
            on: "bottom",
        }
    }
]