/* exported LocalStorageTools */
/* globals BookWyrm */

let LocalStorageTools = new (class {
    constructor() {
        document.querySelectorAll("[data-hide]").forEach((t) => this.setDisplay(t));

        document
            .querySelectorAll(".set-display")
            .forEach((t) => t.addEventListener("click", this.updateDisplay.bind(this)));
    }

    /**
     * Update localStorage, then display content based on keys in localStorage.
     *
     * @param  {Event} event
     * @return {undefined}
     */
    updateDisplay(event) {
        // Used in set reading goal
        const key = event.target.dataset.id;
        const value = event.target.dataset.value;

        window.localStorage.setItem(key, value);

        document
            .querySelectorAll('[data-hide="' + key + '"]')
            .forEach((node) => this.setDisplay(node));
    }

    /**
     * Toggle display of a DOM node based on its value in the localStorage.
     *
     * @param {object} node - DOM node to toggle.
     * @return {undefined}
     */
    setDisplay(node) {
        // Used in set reading goal
        const key = node.dataset.hide;
        const value = window.localStorage.getItem(key);

        if (value) {
            BookWyrm.classHide(node);
        } else {
            BookWyrm.classShow(node);
        }
    }
})();
