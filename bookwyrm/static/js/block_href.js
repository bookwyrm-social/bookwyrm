/* exported BlockHref */

let BlockHref = new class {
    constructor() {
        document.querySelectorAll('[data-href]')
            .forEach(t => t.addEventListener('click', this.followLink.bind(this)));
    }

    /**
     * Follow a fake link
     *
     * @param  {Event} event
     * @return {undefined}
     */
    followLink(event) {
        const url = event.currentTarget.dataset.href;

        window.location.href = url;
    }
}();

