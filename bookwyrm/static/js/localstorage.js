/* exported LocalStorageTools */
/* globals BookWyrm */

let LocalStorageTools = new class {
    constructor() {
        // display based on localstorage vars
        document.querySelectorAll('[data-hide]')
            .forEach(t => this.setDisplay(t));

        // update localstorage
        document.querySelectorAll('.set-display')
            .forEach(t => t.addEventListener('click', this.updateDisplay.bind(this)));
    }

    // set javascript listeners
    updateDisplay(e) {
        // used in set reading goal
        let key = e.target.dataset.id;
        let value = e.target.dataset.value;

        window.localStorage.setItem(key, value);

        document.querySelectorAll('[data-hide="' + key + '"]')
            .forEach(t => this.setDisplay(t));
    }

    setDisplay(el) {
        // used in set reading goal
        let key = el.dataset.hide;
        let value = window.localStorage.getItem(key);

        BookWyrm.addRemoveClass(el, 'hidden', value);
    }
}
