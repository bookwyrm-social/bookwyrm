/* exported StatusCache */
/* globals BookWyrm */

let StatusCache = new class {
    constructor() {
        document.querySelectorAll('[data-cache-draft]')
            .forEach(t => t.addEventListener('change', this.updateDraft.bind(this)));

        document.querySelectorAll('[data-cache-draft]')
            .forEach(t => this.populateDraft(t));

        document.querySelectorAll('.submit-status')
            .forEach(button => button.addEventListener(
                'submit',
                this.submitStatus.bind(this))
            );
    }

    /**
     * Update localStorage copy of drafted status
     *
     * @param  {Event} event
     * @return {undefined}
     */
    updateDraft(event) {
        // Used in set reading goal
        let key = event.target.dataset.cacheDraft;
        let value = event.target.value;

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
        let key = node.dataset.cacheDraft;
        let value = window.localStorage.getItem(key);

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
        event.preventDefault();
        const form = event.currentTarget;
        const trigger = event.submitter;

        BookWyrm.addRemoveClass(form, 'is-processing', true);
        trigger.setAttribute('disabled', null);

        BookWyrm.ajaxPost(form).finally(() => {
            // Change icon to remove ongoing activity on the current UI.
            // Enable back the element used to submit the form.
            BookWyrm.addRemoveClass(form, 'is-processing', false);
            trigger.removeAttribute('disabled');
        })
        .then(this.submitStatusSuccess.bind(this, form))
        .catch(error => {
            // @todo Display a notification in the UI instead.
            //       For now, the absence of change will be enough.
            console.warn('Request failed:', error);

            BookWyrm.addRemoveClass(form, 'has-error', form.className.indexOf('is-hidden') == -1);
        });
    }

    submitStatusSuccess(form) {
        // Clear form data
        form.reset();

        // Clear localstorage
        form.querySelectorAll('[data-cache-draft]')
            .forEach(node => window.localStorage.removeItem(node.dataset.cacheDraft));

        // Close modals
        let modal = form.closest(".modal.is-active");

        if (modal) {
            modal.getElementsByClassName("modal-close")[0].click();

            // Update shelve buttons
            document.querySelectorAll("[data-shelve-button-book='" + form.book.value +"']")
                .forEach(button => this.cycleShelveButtons(button, form.reading_status.value));

            return;
        }

        // Close reply panel
        let reply = form.closest(".reply-panel");

        if (reply) {
            document.querySelector("[data-controls=" + reply.id + "]").click();
        }
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
        let shelf = button.querySelector("[data-shelf-identifier='" + identifier + "']");
        let next_identifier = shelf.dataset.shelfNext;

        // Set all buttons to hidden
        button.querySelectorAll("[data-shelf-identifier]")
            .forEach(item => BookWyrm.addRemoveClass(item, "is-hidden", true));

        // Button that should be visible now
        let next = button.querySelector("[data-shelf-identifier=" + next_identifier + "]");

        // Show the desired button
        BookWyrm.addRemoveClass(next, "is-hidden", false);

        // ------ update the dropdown buttons
        // Remove existing hidden class
        button.querySelectorAll("[data-shelf-dropdown-identifier]")
            .forEach(item => BookWyrm.addRemoveClass(item, "is-hidden", false));

        // Remove existing disabled states
        button.querySelectorAll("[data-shelf-dropdown-identifier] button")
            .forEach(item => item.disabled = false);

        next_identifier = next_identifier == 'complete' ? 'read' : next_identifier;

        // Disable the current state
        button.querySelector(
            "[data-shelf-dropdown-identifier=" + identifier + "] button"
        ).disabled = true;

        let main_button = button.querySelector(
            "[data-shelf-dropdown-identifier=" + next_identifier + "]"
        );

        // Hide the option that's shown as the main button
        BookWyrm.addRemoveClass(main_button, "is-hidden", true);

        // Just hide the other two menu options, idk what to do with them
        button.querySelectorAll("[data-extra-options]")
            .forEach(item => BookWyrm.addRemoveClass(item, "is-hidden", true));

        // Close menu
        let menu = button.querySelector(".dropdown-trigger[aria-expanded=true]");

        if (menu) {
            menu.click();
        }
    }
}();

