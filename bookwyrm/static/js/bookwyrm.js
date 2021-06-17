/* exported BookWyrm */
/* globals TabGroup */

let BookWyrm = new class {
    constructor() {
        this.MAX_FILE_SIZE_BYTES = 10 * 1000000;
        this.initOnDOMLoaded();
        this.initReccuringTasks();
        this.initEventListeners();
    }

    initEventListeners() {
        document.querySelectorAll('[data-controls]')
            .forEach(button => button.addEventListener(
                'click',
                this.toggleAction.bind(this))
            );

        document.querySelectorAll('.interaction')
            .forEach(button => button.addEventListener(
                'submit',
                this.interact.bind(this))
            );

        document.querySelectorAll('.hidden-form input')
            .forEach(button => button.addEventListener(
                'change',
                this.revealForm.bind(this))
            );

        document.querySelectorAll('[data-back]')
            .forEach(button => button.addEventListener(
                'click',
                this.back)
            );

        document.querySelectorAll('input[type="file"]')
            .forEach(node => node.addEventListener(
                'change',
                this.disableIfTooLarge.bind(this)
            ));
    }

    /**
     * Execute code once the DOM is loaded.
     */
    initOnDOMLoaded() {
        const bookwyrm = this;

        window.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.tab-group')
                .forEach(tabs => new TabGroup(tabs));
            document.querySelectorAll('input[type="file"]').forEach(
                bookwyrm.disableIfTooLarge.bind(bookwyrm)
            );
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
     * @return {undefined}
     */
    back(event) {
        event.preventDefault();
        history.back();
    }

    /**
     * Update a counter with recurring requests to the API
     * The delay is slightly randomized and increased on each cycle.
     *
     * @param  {Object} counter - DOM node
     * @param  {int}    delay   - frequency for polling in ms
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
     * @return {undefined}
     */
    updateCountElement(counter, data) {
        const currentCount = counter.innerText;
        const count = data.count;
        const hasMentions = data.has_mentions;

        if (count != currentCount) {
            this.addRemoveClass(counter.closest('[data-poll-wrapper]'), 'is-hidden', count < 1);
            counter.innerText = count;
            this.addRemoveClass(counter.closest('[data-poll-wrapper]'), 'is-danger', hasMentions);
        }
    }

    /**
     * Toggle form.
     *
     * @param  {Event} event
     * @return {undefined}
     */
    revealForm(event) {
        let trigger = event.currentTarget;
        let hidden = trigger.closest('.hidden-form').querySelectorAll('.is-hidden')[0];

        this.addRemoveClass(hidden, 'is-hidden', !hidden);
    }

    /**
     * Execute actions on targets based on triggers.
     *
     * @param  {Event} event
     * @return {undefined}
     */
    toggleAction(event) {
        event.preventDefault();
        let trigger = event.currentTarget;
        let pressed = trigger.getAttribute('aria-pressed') === 'false';
        let targetId = trigger.dataset.controls;

        // Toggle pressed status on all triggers controlling the same target.
        document.querySelectorAll('[data-controls="' + targetId + '"]')
            .forEach(otherTrigger => otherTrigger.setAttribute(
                'aria-pressed',
                otherTrigger.getAttribute('aria-pressed') === 'false'
            ));

        // @todo Find a better way to handle the exception.
        if (targetId && ! trigger.classList.contains('pulldown-menu')) {
            let target = document.getElementById(targetId);

            this.addRemoveClass(target, 'is-hidden', !pressed);
            this.addRemoveClass(target, 'is-active', pressed);
        }

        // Show/hide pulldown-menus.
        if (trigger.classList.contains('pulldown-menu')) {
            this.toggleMenu(trigger, targetId);
        }

        // Show/hide container.
        let container = document.getElementById('hide-' + targetId);

        if (container) {
            this.toggleContainer(container, pressed);
        }

        // Check checkbox, if appropriate.
        let checkbox = trigger.dataset.controlsCheckbox;

        if (checkbox) {
            this.toggleCheckbox(checkbox, pressed);
        }

        // Set focus, if appropriate.
        let focus = trigger.dataset.focusTarget;

        if (focus) {
            this.toggleFocus(focus);
        }

        return false;
    }

    /**
     * Show or hide menus.
     *
     * @param  {Event} event
     * @return {undefined}
     */
    toggleMenu(trigger, targetId) {
        let expanded = trigger.getAttribute('aria-expanded') == 'false';

        trigger.setAttribute('aria-expanded', expanded);

        if (targetId) {
            let target = document.getElementById(targetId);

            this.addRemoveClass(target, 'is-active', expanded);
        }
    }

    /**
     * Show or hide generic containers.
     *
     * @param  {object}  container - DOM node
     * @param  {boolean} pressed   - Is the trigger pressed?
     * @return {undefined}
     */
    toggleContainer(container, pressed) {
        this.addRemoveClass(container, 'is-hidden', pressed);
    }

    /**
     * Check or uncheck a checbox.
     *
     * @param  {object}  checkbox - DOM node
     * @param  {boolean} pressed  - Is the trigger pressed?
     * @return {undefined}
     */
    toggleCheckbox(checkbox, pressed) {
        document.getElementById(checkbox).checked = !!pressed;
    }

    /**
     * Give the focus to an element.
     * Only move the focus based on user interactions.
     *
     * @param  {string} nodeId - ID of the DOM node to focus (button, link…)
     * @return {undefined}
     */
    toggleFocus(nodeId) {
        let node = document.getElementById(nodeId);

        node.focus();

        setTimeout(function() {
            node.selectionStart = node.selectionEnd = 10000;
        }, 0);
    }

    /**
     * Make a request and update the UI accordingly.
     * This function is used for boosts, favourites, follows and unfollows.
     *
     * @param  {Event} event
     * @return {undefined}
     */
    interact(event) {
        event.preventDefault();

        const bookwyrm = this;
        const form = event.currentTarget;
        const relatedforms = document.querySelectorAll(`.${form.dataset.id}`);

        // Toggle class on all related forms.
        relatedforms.forEach(relatedForm => bookwyrm.addRemoveClass(
            relatedForm,
            'is-hidden',
            relatedForm.className.indexOf('is-hidden') == -1
        ));

        this.ajaxPost(form).catch(error => {
            // @todo Display a notification in the UI instead.
            console.warn('Request failed:', error);
        });
    }

    /**
     * Submit a form using POST.
     *
     * @param  {object} form - Form to be submitted
     * @return {Promise}
     */
    ajaxPost(form) {
        return fetch(form.action, {
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

    disableIfTooLarge(eventOrElement) {
        const { addRemoveClass, MAX_FILE_SIZE_BYTES } = this;
        const element = eventOrElement.currentTarget || eventOrElement;

        const submits = element.form.querySelectorAll('[type="submit"]');
        const warns = element.parentElement.querySelectorAll('.file-too-big');
        const isTooBig = element.files &&
            element.files[0] &&
            element.files[0].size > MAX_FILE_SIZE_BYTES;

        if (isTooBig) {
            submits.forEach(submitter => submitter.disabled = true);
            warns.forEach(
                sib => addRemoveClass(sib, 'is-hidden', false)
            );
        } else {
            submits.forEach(submitter => submitter.disabled = false);
            warns.forEach(
                sib => addRemoveClass(sib, 'is-hidden', true)
            );
        }
    }
}();
