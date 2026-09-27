/**
 * Import Shepherd
*/
import Shepherd from '../vendor/shepherd.module.js'
const tour = new Shepherd.Tour({
    useModalOverlay: true,
    defaultStepOptions: {
        skipMissingElement: true,
        scrollTo: true,
        highlightClass: 'tour-element-highlight',
        cancelIcon: {
            enabled: true,
            label: gettext('Close Tour'),
        },
        buttons: [
            {
                action() {
                    return this.back();
                },
                secondary: true,
                text: gettext("Back"),
            },
            {
                action() {
                    return this.next();
                },
                text: gettext("Next"),
            },
        ]
    }
});

/**
 * Default object for pages without a tour
 * @return {object}
 */
function getStepEmpty() {
    return {
        id: "default",
        title: gettext("Help"),
        text: gettext("This page doesn't have a tour yet, but many do. You can also check") + " <a href='https://docs.joinbookwyrm.com'>" + gettext("the BookWyrm documentation") + "</a>.",
        buttons: [
            {
                action() {
                    return this.complete();
                },
                text: gettext("Ok"),
                classes: "is-primary",
            }
        ]
    }
}

/**
 * Shepherd tour end step object
 * @return {object}
 */
function getStepComplete() {
    return {
        id: "end",
        title:  gettext("Finish"),
        text: gettext("That's all for now. Click the Help button on any page to get more tips!"),
        attachTo: {
                element: "#help-button",
                on: "bottom-end",
            },
        buttons: [
            {
                action() {
                    return this.back();
                },
                secondary: true,
                text: gettext("Back")
            },
            {
                action() {
                    return this.complete();
                },
                text: gettext("Ok"),
                classes: "is-primary",
            }
        ]
    }
}

/**
 * Set guided tour user value to False
 * @param  {csrf_token} string
 * @return {undefined}
 */
function disableGuidedTour(csrf_token) {
    return fetch("/guided-tour/False", {
        headers: {
            "X-CSRFToken": csrf_token,
        },
        method: "POST",
        redirect: "follow",
        mode: "same-origin",
    });
}

/**
 * Create the start up tour for new users
 * @return {Shepherd.Tour}
 */
const startUpTour = new Shepherd.Tour({
    useModalOverlay: true,
});

/**
 * Add step to the default guided tour invite
 * @return {object}
 */
startUpTour.addSteps([
    {
        title: gettext("Take the tour"),
        text: gettext("Welcome to BookWyrm! Would you like a quick tour to get started? You can use this Help button for a tour of any page."),
        attachTo: {
            element: "#help-button",
            on: "bottom-end",
        },
        buttons: [
            {
                action() {
                    return this.complete();
                },
                secondary: true,
                text: gettext("No thanks"),
                attrs: {
                    'id': 'button-decline-tour'
                }
            },
            {
                action() {
                    this.complete();

                    return tour.next();
                },
                text: gettext("Yes please!"),
                classes: "is-primary",
                attrs: {
                    'id': 'button-accept-tour'
                }
            },
        ]
    }
])

export { tour, getStepEmpty, getStepComplete, startUpTour, disableGuidedTour }
