/* exported BookWyrm */
/* globals TabGroup */

let BookWyrm = new class {
    constructor() {
        this.initOnDOMLoaded();
        this.initReccuringTasks();
        this.initEventListeners();
    }

    initEventListeners() {
        // buttons that display or hide content
        document.querySelectorAll('[data-controls]')
            .forEach(button => button.addEventListener('click', this.toggleAction.bind(this)));

        // javascript interactions (boost/fav)
        document.querySelectorAll('.interaction')
            .forEach(button => button.addEventListener('submit', this.interact.bind(this)));

        // handle aria settings on menus
        document.querySelectorAll('.pulldown-menu')
            .forEach(button => button.addEventListener('click', this.toggleMenu.bind(this)));

        // hidden submit button in a form
        document.querySelectorAll('.hidden-form input')
            .forEach(button => button.addEventListener('change', this.revealForm.bind(this)));

        // browser back behavior
        document.querySelectorAll('[data-back]')
            .forEach(button => button.addEventListener('click', this.back));
    }

    /**
     * Execute code once the DOM is loaded.
     */
    initOnDOMLoaded() {
        window.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.tab-group')
                .forEach(tabs => new TabGroup(tabs));
        });
    }

    /**
     * Execute recurring tasks.
     */
    initReccuringTasks() {
        // Polling
        document.querySelectorAll('[data-poll]')
            .forEach(liveArea => this.polling(liveArea));
    }

    /**
     * Go back in browser history.
     *
     * @param  {Event} event
     *
     * @return {undefined}
     */
    back(event) {
        event.preventDefault();
        history.back();
    }

    /**
     * Update a counter with recurring requests to the API
     *
     * @param  {Object} counter - DOM node
     * @param  {int}    delay   - frequency for polling in ms
     *
     * @return {undefined}
     */
    polling(counter, delay) {
        const bookwyrm = this;

        delay = delay || 10000;
        delay += (Math.random() * 1000);

        setTimeout(function() {
            fetch('/api/updates/' + counter.dataset.poll)
                .then(response => response.json())
                .then(data => bookwyrm.updateCountElement(counter, data));

            bookwyrm.polling(counter, delay * 1.25);
        }, delay, counter);
    }

    /**
     * Update a counter.
     *
     * @param  {object} counter - DOM node
     * @param  {object} data    - json formatted response from a fetch
     *
     * @return {undefined}
     */
    updateCountElement(counter, data) {
        const currentCount = counter.innerText;
        const count = data.count;

        if (count != currentCount) {
            this.addRemoveClass(counter.closest('[data-poll-wrapper]'), 'hidden', count < 1);
            counter.innerText = count;
        }
    }

    /**
     * Toggle form.
     *
     * @param  {Event} event
     *
     * @return {undefined}
     */
    revealForm(event) {
        let trigger = event.currentTarget;
        let hidden = trigger.closest('.hidden-form').querySelectorAll('.hidden')[0];

        this.addRemoveClass(hidden, 'hidden', !hidden);
    }

    /**
     * Execute actions on targets based on triggers.
     *
     * @param  {Event} event
     *
     * @return {undefined}
     */
    toggleAction(event) {
        let trigger = event.currentTarget;
        let pressed = trigger.getAttribute('aria-pressed') == 'false';
        let targetId = trigger.dataset.controls;

        // Un‑press all triggers controlling the same target.
        document.querySelectorAll('[data-controls="' + targetId + '"]')
            .forEach(triggers => triggers.setAttribute(
                'aria-pressed',
                (triggers.getAttribute('aria-pressed') == 'false'))
            );

        if (targetId) {
            let target = document.getElementById(targetId);

            this.addRemoveClass(target, 'hidden', !pressed);
            this.addRemoveClass(target, 'is-active', pressed);
        }

        // Show/hide container.
        let container = document.getElementById('hide-' + targetId);

        if (container) {
            this.addRemoveClass(container, 'hidden', pressed);
        }

        // Check checkbox, if appropriate.
        let checkbox = trigger.dataset['controls-checkbox'];

        if (checkbox) {
            document.getElementById(checkbox).checked = !!pressed;
        }

        // Set focus, if appropriate.
        let focus = trigger.dataset['focus-target'];

        if (focus) {
            let focusEl = document.getElementById(focus);

            focusEl.focus();
            setTimeout(function() { focusEl.selectionStart = focusEl.selectionEnd = 10000; }, 0);
        }
    }

    /**
     * Make a request and update the UI accordingly.
     * This function is used for boosts and favourites.
     *
     * @todo Only update status if the promise is successful.
     *
     * @param  {Event} event
     *
     * @return {undefined}
     */
    interact(event) {
        event.preventDefault();

        this.ajaxPost(event.target);

        // @todo This probably should be done with IDs.
        document.querySelectorAll(`.${event.target.dataset.id}`)
            .forEach(node => this.addRemoveClass(
                node,
                'hidden',
                node.className.indexOf('hidden') == -1
            ));
    }

    /**
     * Handle ARIA states on toggled menus.
     *
     * @note This function seems to be redundant and conflicts with toggleAction.
     *
     * @param  {Event} event
     *
     * @return {undefined}
     */
    toggleMenu(event) {
        let trigger = event.currentTarget;
        let expanded = trigger.getAttribute('aria-expanded') == 'false';
        let targetId = trigger.dataset.controls;

        trigger.setAttribute('aria-expanded', expanded);

        if (targetId) {
            let target = document.getElementById(targetId);

            this.addRemoveClass(target, 'is-active', expanded);
        }
    }

    /**
     * Submit a form using POST.
     *
     * @param  {object} form - Form to be submitted
     *
     * @return {undefined}
     */
    ajaxPost(form) {
        fetch(form.action, {
            method : "POST",
            body: new FormData(form)
        });
    }

    /**
     * Add or remove a class based on a boolean condition.
     *
     * @param  {object}  node      - DOM node to change class on
     * @param  {string}  classname - Name of the class
     * @param  {boolean} add       - Add?
     * @return {undefined}
     */
    addRemoveClass(node, classname, add) {
        if (add) {
            node.classList.add(classname);
        } else {
            node.classList.remove(classname);
        }
    }
}
