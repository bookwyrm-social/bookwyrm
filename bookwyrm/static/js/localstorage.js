/* exported LocalStorageTools */
/* globals BookWyrm */

let LocalStorageTools = new class {
    constructor() {
        // display based on localstorage vars
        document.querySelectorAll('[data-hide]')
            .forEach(t => this.setDisplay(t));

        // update localstorage
        document.querySelectorAll('.set-display')
            .forEach(t => t.onclick = this.updateDisplay.bind(this));
    }

    // set javascript listeners
    updateDisplay(e) {
        // used in set reading goal
        let key = e.target.getAttribute('data-id');
        let value = e.target.getAttribute('data-value');

        window.localStorage.setItem(key, value);

        document.querySelectorAll('[data-hide="' + key + '"]')
            .forEach(t => this.setDisplay(t));
    }

    setDisplay(el) {
        // used in set reading goal
        let key = el.getAttribute('data-hide');
        let value = window.localStorage.getItem(key);

        BookWyrm.addRemoveClass(el, 'hidden', value);
    }
}
