export const steps = [
    {
        title: gettext("Home feed"),
        text: gettext("This is your home page, where you will see the latest activity from people you follow.")
    },
    {
        title: gettext("Search box"),
        text: gettext("Search for books, authors, users, or lists using this search box." ),
        attachTo: {
            element: "#header-searchbox",
            on: "bottom",
        }
    },
    {
        title: gettext("Barcode reader"),
        text: gettext("Search book records by scanning an ISBN barcode using your device's camera - great when you're in the bookstore or library!"),
        attachTo: {
            element: "#barcode-scanner-box",
            on: "bottom",
        }
    },
    {
        title: gettext("Navigation bar"),
        text: gettext("Visit <strong>Lists</strong> to discover reading suggestions, <strong>Discover</strong> for the latest activity on this BookWyrm instance, or <strong>Your Books</strong> to see your book shelves."),
        attachTo: {
            element: "#navbar-start",
            on: "bottom",
        }
    },
    {
        title: gettext("Your books"),
        text: gettext("Books on your reading status shelves will be shown here. You can also publish a review, comment or quote, as well as changing the reading status from here."),
        attachTo: {
            element: "#suggested-books",
            on: "right",
        }
    },
    {
        title: gettext("Timelines"),
        text: gettext("Updates from people you are following will appear in your <strong>Home</strong> timeline.<br><br>The <strong>Books</strong> tab shows activity from anyone, related to your books."),
        attachTo: {
            element: "#feed",
            on: "left",
        }
    },
    {
        title: gettext("Notifications"),
        text: gettext("The bell will light up when you have a new notification. When it does, click on it to find out what exciting thing has happened!"),
        attachTo: {
            element: "#notifications",
            on: "bottom",
        }
    },
    {
        title: gettext("Profile and settings menu"),
        text: gettext("Your profile, user directory, direct messages, and settings can be accessed by clicking on your name in the menu here."),
        attachTo: {
            element: "#user-profile",
            on: "bottom",
        }
    },
]
