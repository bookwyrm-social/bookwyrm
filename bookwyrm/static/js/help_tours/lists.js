export const steps = [
    {
        text: gettext("You can see any lists you have access to here, including from other instances. Lists are a great way to find new books to read!"),
        title: gettext('Lists'),
        buttons: [
            {
                action() {
                    return this.next();
                },
                text: gettext("Next"),
            },
        ]
    },
    {
        text: gettext("You can bookmark or 'save' your favorite lists. Find them at this tab."),
        title: gettext('Saved Lists'),
        attachTo: {
            element: "#saved-lists-tab",
            on: "right-start",
        }
    },
    {
        text: gettext("Create your own book list. There are options for how a list is curated as well as privacy settings to determine who can see your list."),
        title: gettext('Create a list'),
        attachTo: {
            element: "#create-list-button",
            on: "left",
        },
        extraHighlights: ['#your-lists']
    }
]