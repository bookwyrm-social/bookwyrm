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
     * @param  {Event} event
     * @return {undefined}
     */
    submitStatus(event) {
        event.preventDefault();
        const form = event.currentTarget;

        BookWyrm.ajaxPost(form).catch(error => {
            // @todo Display a notification in the UI instead.
            console.warn('Request failed:', error);
        });

        // Clear form data
        form.reset();

        // Clear localstorage
        form.querySelectorAll('[data-cache-draft]')
            .forEach(node => window.localStorage.removeItem(node.dataset.cacheDraft));

        // Close modals
        let modal = form.closest(".modal.is-active");
        if (!!modal) {
            modal.getElementsByClassName("modal-close")[0].click();
        }

        // Close reply panel
        let reply = form.closest(".reply-panel");
        if (!!reply) {
            document.querySelector("[data-controls=" + reply.id + "]").click();
        }

        // Update shelve buttons
    }
}();

