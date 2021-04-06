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

    back(e) {
        e.preventDefault();
        history.back();
    }

    polling(counter, delay) {
        let poller = this;

        delay = delay || 10000;
        delay += (Math.random() * 1000);

        setTimeout(function() {
            fetch('/api/updates/' + counter.dataset.poll)
                .then(response => response.json())
                .then(data => poller.updateCountElement(counter, data));
            poller.polling(counter, delay * 1.25);
        }, delay, counter);
    }

    updateCountElement(el, data) {
        const currentCount = el.innerText;
        const count = data.count;

        if (count != currentCount) {
            this.addRemoveClass(el.closest('[data-poll-wrapper]'), 'hidden', count < 1);
            el.innerText = count;
        }
    }

    revealForm(e) {
        let hidden = e.currentTarget.closest('.hidden-form').getElementsByClassName('hidden')[0];

        this.addRemoveClass(hidden, 'hidden', !hidden);
    }

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

        // show/hide container
        let container = document.getElementById('hide-' + targetId);

        if (container) {
            this.addRemoveClass(container, 'hidden', pressed);
        }

        // set checkbox, if appropriate
        let checkbox = trigger.dataset['controls-checkbox'];

        if (checkbox) {
            document.getElementById(checkbox).checked = !!pressed;
        }

        // set focus, if appropriate
        let focus = trigger.dataset['focus-target'];

        if (focus) {
            let focusEl = document.getElementById(focus);

            focusEl.focus();
            setTimeout(function() { focusEl.selectionStart = focusEl.selectionEnd = 10000; }, 0);
        }
    }

    // @todo Only update status if the promise is successful.
    interact(e) {
        e.preventDefault();

        let identifier = e.target.dataset.id;

        this.ajaxPost(e.target);

        // @todo This probably should be done with IDs.
        document.querySelectorAll(`.${identifier}`)
            .forEach(t => this.addRemoveClass(t, 'hidden', t.className.indexOf('hidden') == -1));
    }

    toggleMenu(e) {
        let el = e.currentTarget;
        let expanded = el.getAttribute('aria-expanded') == 'false';
        let targetId = el.dataset.controls;

        el.setAttribute('aria-expanded', expanded);

        if (targetId) {
            let target = document.getElementById(targetId);

            this.addRemoveClass(target, 'is-active', expanded);
        }
    }

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
