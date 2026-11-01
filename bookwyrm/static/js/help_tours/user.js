let profileLocked = document.getElementById('locked-profile');

export const steps = [
    {
        text: gettext("This is a user profile page. This user has locked their profile so we can't show you anything else here."),
        title: gettext("User profile"),
        attachTo: {
            element: "#locked-profile",
            on: "top",
        },
        buttons: [
            {
                action() {
                    return this.complete();
                },
                text: gettext("Ok"),
                classes: "is-primary",
            },
        ]
    },
    {
        text: gettext("This is a user profile page. Which parts you can see depends on the user's privacy settings."),
        title: gettext("User Profile"),
        showOn: () => !profileLocked,
        buttons: [
            {
                action() {
                    return this.next();
                },
                text: gettext("Next"),
                classes: "is-primary",
            },
        ]
    },
    {
        text: gettext("This user's reflections on their reading."),
        title: gettext("Reviews and Comments"),

        attachTo: {
            element: "#reviews-comments-tab",
            on: "bottom",
        }
    },
    {
        text: gettext("Everything read this calendar year."),
        title: gettext("Reading Goal"),
        attachTo: {
            element: "#reading-goal-tab",
            on: "bottom",
        }
    },
    {
        text: gettext("Groups bring together Bookwyrm users and allow them to curate lists together."),
        title: gettext("Groups"),
        attachTo: {
            element: "#groups-tab",
            on: "bottom",
        }
    },
    {
        text: gettext("A list is a collection of books that have something in common."),
        title: gettext("Lists"),
        attachTo: {
            element: "#lists-tab",
            on: "bottom",
        }
    },
    {
        text: gettext("You can suggest books that are similar to other books – our 'algorithm' is other readers!"),
        title: gettext("Suggestions"),
        attachTo: {
            element: "#suggestions-tab",
            on: "bottom",
        }
    },
    {
        text: gettext("Books can be organized into shelves."),
        title: gettext("Book Shelves"),
        attachTo: {
            element: "#books-tab",
            on: "bottom",
        }
    },
    {
        text: gettext("The most recent reading activity."),
        title: gettext("Reading Activity"),
        attachTo: {
            element: "#user-books-block",
            on: "bottom",
        }
    },
    {
        text: gettext("All user activity is listed in their public feed"),
        title: gettext("Activity Feed"),
        attachTo: {
            element: "[id^=feed_]",
            on: "top",
        }
    },
    {
        text: gettext("Subscribe to all of a user's posts, or only certain types (such as reviews) via RSS."),
        title: gettext("RSS feeds"),
        attachTo: {
            element: "#rss-feed",
            on: "left",
        }
    },
]