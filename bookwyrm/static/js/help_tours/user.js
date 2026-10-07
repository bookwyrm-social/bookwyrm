let profileLocked = document.getElementById('locked-profile');

export const steps = [
    {
        text: gettext("This is a user profile page. This user has locked their profile so we can't show you anything else here."),
        title: gettext("User profile"),
        attachTo: {
            element: "#locked-profile",
            on: "top",
        },
        button: [
            {
                action() {
                    return this.complete();
                },
                text: "{% trans 'Ok' %}",
                classes: "is-primary",
            },
        ]
    },
    {
        text: gettext("This is a user profile page. Other Bookwyrm users can visit your own profile page - which parts they can see depends on your privacy settings."),
        title: gettext("User Profile"),
        showOn: () => !profileLocked,
    },
    {
        text: gettext("All of the reviews and comments published by a user are shown in this tab."),
        title: gettext("Reviews and Comments"),

        attachTo: {
            element: "#reviews-comments-tab",
            on: "right",
        }
    },
    {
        text: gettext("This tab shows everything read towards your annual reading goal, or allows you to set one. You don't have to set a reading goal if that's not your thing, and your goal can be private."),
        title: gettext("Reading Goal"),
        attachTo: {
            element: "#reading-goal-tab",
            on: "right",
        }
    },
    {
        text: gettext("Groups bring together Bookwyrm users and allow them to curate lists together."),
        title: gettext("Groups"),
        attachTo: {
            element: "#groups-tab",
            on: "right",
        }
    },
    {
        text: gettext("A list is a collection of books that have something in common."),
        title: gettext("Lists"),
        attachTo: {
            element: "#lists-tab",
            on: "right",
        }
    },
    {
        text: gettext("You can suggest books that are similar to other books – our 'algorithm' is other readers! Your suggestions are shown in this tab."),
        title: gettext("Suggestions"),
        attachTo: {
            element: "#suggestions-tab",
            on: "right",
        }
    },
    {
        text: gettext("Books can be arranged on shelves and are organized here."),
        title: gettext("Book Shelves"),
        attachTo: {
            element: "#books-tab",
            on: "right",
        }
    },
    {
        text: gettext("You can subscribe to all of a user's posts, or only certain types (such as reviews) via RSS."),
        title: gettext("RSS feeds"),
        attachTo: {
            element: "#rss-feed",
            on: "left",
        }
    },
]
