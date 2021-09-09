/* exported StatusCache */

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

        const bookwyrm = this;
        const form = event.currentTarget;

        this.ajaxPost(form).catch(error => {
            // @todo Display a notification in the UI instead.
            console.warn('Request failed:', error);
        });

        // Clear form data
        form.reset();
    }
}();

