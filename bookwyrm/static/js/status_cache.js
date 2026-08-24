/* exported StatusCache */
/* globals BookWyrm */

let StatusCache = new (class {
    constructor() {
        document
            .querySelectorAll("[data-cache-draft]")
            .forEach((t) => t.addEventListener("change", this.updateDraft.bind(this)));

        document.querySelectorAll("[data-cache-draft]").forEach((t) => this.populateDraft(t));

        document
            .querySelectorAll(".submit-status")
            .forEach((button) => button.addEventListener("submit", this.submitStatus.bind(this)));
    }

    /**
     * Update localStorage copy of drafted status
     *
     * @param  {Event} event
     * @return {undefined}
     */
    updateDraft(event) {
        // Used in set reading goal
        const key = event.target.dataset.cacheDraft;
        const value = event.target.value;

        if (!value) {
            window.localStorage.removeItem(key);

            return;
        }

        window.localStorage.setItem(key, value);
    }

    /**
     * Toggle display of a DOM node based on its value in the localStorage.
     *
     * @param {object} node - DOM node to toggle.
     * @return {undefined}
     */
    populateDraft(node) {
        // Used in set reading goal
        const key = node.dataset.cacheDraft;
        const value = window.localStorage.getItem(key);

        if (!value) {
            return;
        }

        node.value = value;
    }

    /**
     * Post a status with ajax
     *
     * @param  {} event
     * @return {undefined}
     */
    submitStatus(event) {
        const form = event.currentTarget;
        let trigger = event.submitter;

        // Safari doesn't understand "submitter"
        if (!trigger) {
            trigger = event.currentTarget.querySelector("button[type=submit]");
        }

        // This allows the form to submit in the old fashioned way if there's a problem

        if (!trigger || !form) {
            return;
        }

        event.preventDefault();

        form.classList.add("is-processing");
        trigger.setAttribute("disabled", null);

        BookWyrm.ajaxPost(form)
            .finally(() => {
                // Change icon to remove ongoing activity on the current UI.
                // Enable back the element used to submit the form.
                form.classList.remove("is-processing");
                trigger.removeAttribute("disabled");
            })
            .then((response) => {
                if (!response.ok) {
                    throw new Error();
                }
                this.submitStatusSuccess(form);
            })
            .catch((error) => {
                console.warn(error);
                this.announceMessage("status-error-message");
            });
    }

    /**
     * Show a message in the live region
     *
     * @param  {String} the id of the message dom element
     * @return {undefined}
     */
    announceMessage(messageId) {
        const element = document.getElementById(messageId);
        let copy = element.cloneNode(true);

        copy.id = null;
        element.insertAdjacentElement("beforebegin", copy);

        BookWyrm.classShow(copy);
        setTimeout(
            function () {
                copy.remove();
            },
            10000,
            copy
        );
    }

    /**
     * Success state for a posted status
     *
     * @param  {Object} the html form that was submitted
     * @return {undefined}
     */
    submitStatusSuccess(form) {
        // Clear form data
        form.reset();

        // Clear localstorage
        form.querySelectorAll("[data-cache-draft]").forEach((node) =>
            window.localStorage.removeItem(node.dataset.cacheDraft)
        );

        // Close modals
        const modal = form.closest(".modal.is-active");

        if (modal) {
            modal.getElementsByClassName("modal-close")[0].click();

            // Update shelve buttons
            if (form.reading_status) {
                document
                    .querySelectorAll("[data-shelve-button-book='" + form.book.value + "']")
                    .forEach((button) =>
                        this.cycleShelveButtons(button, form.reading_status.value)
                    );
            }

            return;
        }

        // Close reply panel
        const reply = form.closest(".reply-panel");

        if (reply) {
            document.querySelector("[data-controls=" + reply.id + "]").click();
        }

        this.announceMessage("status-success-message");
    }

    /**
     * Change which buttons are available for a shelf
     *
     * @param  {Object} html button dom element
     * @param  {String} the identifier of the selected shelf
     * @return {undefined}
     */
    cycleShelveButtons(button, identifier) {
        // Pressed button
        const shelf = button.querySelector("[data-shelf-identifier='" + identifier + "']");
        let nextIdentifier = shelf.dataset.shelfNext;

        // Set all buttons to hidden
        button
            .querySelectorAll("[data-shelf-identifier]")
            .forEach((item) => BookWyrm.classHide(item));

        // Button that should be visible now
        const next = button.querySelector("[data-shelf-identifier=" + nextIdentifier + "]");

        // Show the desired button
        BookWyrm.classShow(next);

        // ------ update the dropdown buttons
        // Remove existing hidden class
        button
            .querySelectorAll("[data-shelf-dropdown-identifier]")
            .forEach((item) => BookWyrm.classShow(item));

        // Remove existing disabled states

        button
            .querySelectorAll("[data-shelf-dropdown-identifier] button")
            .forEach((item) => (item.disabled = false));

        nextIdentifier = nextIdentifier == "complete" ? "read" : nextIdentifier;
        nextIdentifier =
            nextIdentifier == "stopped-reading-complete" ? "stopped-reading" : nextIdentifier;

        // Disable the current state
        button.querySelector(
            "[data-shelf-dropdown-identifier=" + identifier + "] button"
        ).disabled = true;

        const mainButton = button.querySelector(
            "[data-shelf-dropdown-identifier=" + nextIdentifier + "]"
        );

        // Hide the option that's shown as the main button
        BookWyrm.classHide(mainButton);

        // Just hide the other two menu options, idk what to do with them
        button.querySelectorAll("[data-extra-options]").forEach((item) => BookWyrm.classHide(item));

        // Close menu
        const menu = button.querySelector("details[open]");

        if (menu) {
            menu.removeAttribute("open");
        }
    }
})();
