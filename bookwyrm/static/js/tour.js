const homeTour = new Shepherd.Tour({
    exitOnEsc: true,
});

homeTour.addSteps([
        {
            text: "Search for books, users, or lists using this search box.",
            title: "Search box",
            attachTo: {
                element: "#search_input",
                on: "bottom",
            },
            buttons: [
                {
                    action() {
                        return this.cancel();
                    },
                    secondary: true,
                    text: "Cancel",
                    classes: "is-danger",
                },
                {
                    action() {
                        return this.next();
                    },
                    text: "Next",
                },
            ],
        },
        {
            text: "Search book records by scanning an ISBN barcode using your camera.",
            title: "Barcode reader",
            attachTo: {
                element: ".icon-barcode",
                on: "bottom",
            },
            buttons: [
                {
                    action() {
                        return this.back();
                    },
                    secondary: true,
                    text: "Back",
                },
                {
                    action() {
                        return this.next();
                    },
                    text: "Next",
                },
            ],
        },
        {
            text: "The latest books to be added to your reading shelves will be shown here.",
            title: "Your Books",
            attachTo: {
                element: "#suggested_books_block",
                on: "right",
            },
            buttons: [
                {
                    action() {
                        return this.back();
                    },
                    secondary: true,
                    text: "Back",
                },
                {
                    action() {
                        return this.next();
                    },
                    text: "Next",
                },
            ],
        },
        {
            text: "The bell will light up when you have a new notification. Click on it to find out what exciting thing has happened!",
            title: "Notifications",
            attachTo: {
                element: '[href="/notifications"]',
                on: "left-end",
            },
            buttons: [
                {
                    action() {
                        return this.back();
                    },
                    secondary: true,
                    text: "Back",
                },
                {
                    action() {
                        return this.next();
                    },
                    text: "Next",
                },
            ],
        },
        {
            text: "Your profile, books, direct messages, and settings can be accessed by clicking on your name here.<br><br>Try selecting <code>Profile</code> from the drop down menu to continue the tour.",
            title: "Profile and settings menu",
            attachTo: {
                element: "#navbar-dropdown",
                on: "left-end",
            },
            buttons: [
                {
                    action() {
                        return this.back();
                    },
                    secondary: true,
                    text: "Back",
                },
                {
                    action() {
                        return this.next();
                    },
                    text: "Ok",
                },
            ],
        }
]);

// TODO: User Profile
// TODO: Groups
    // TODO: creating groups and adding users
    // TODO: visibility
// TODO: Lists
    // TODO: creating lists and adding books
    // TODO: visibility - followers-only
// TODO: Books
    // TODO: reading status shelves
    // TODO: creating a shelf
    // TODO: importing

function startTour(tourName) {
    if (tourName === 'home') {
        homeTour.start()
    }
}
