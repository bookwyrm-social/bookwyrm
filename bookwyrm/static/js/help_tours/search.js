export const steps = [
    {
        title: gettext("Search"),
        text: gettext("When you use the search box in the header you will end up on this page. You can explore search results and further customise your search here.")
    },
    {
        title: gettext("Search box"),
        text: gettext("Your search results will appear here. By default only local results will be shown unless nothing can be found on this instance." ),
        attachTo: {
            element: "#search-results-block",
            on: "top",
        }
    },
    {
        title: gettext("Search Results Types"),
        text: gettext("BookWyrm doesn't just search books. Select the appropriate tab to find authors, users, and lists on this instance." ),
        attachTo: {
            element: "#search-type-tabs",
            on: "bottom",
        }
    },
    {
        title: gettext("Change your search terms"),
        text: gettext("Didn't find what you were looking for? You can adjust your search terms here." ),
        attachTo: {
            element: "#new-search-input",
            on: "bottom",
        }
    },
    {
        title: gettext("Refine your search"),
        text: gettext("Select the type of thing you are searching for (book, author, user, or list)." ),
        attachTo: {
            element: "#search-type-selector",
            on: "bottom",
        }
    },
    {
        title: gettext("Run your search!"),
        text: gettext("Press the search button to run your new search!" ),
        attachTo: {
            element: "#search-button",
            on: "bottom",
        }
    }
]