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
            .forEach(button => button.onclick = this.toggleAction.bind(this));

        // javascript interactions (boost/fav)
        document.querySelectorAll('.interaction')
            .forEach(button => button.onsubmit = this.interact.bind(this));

        // handle aria settings on menus
        document.querySelectorAll('.pulldown-menu')
            .forEach(button => button.onclick = this.toggleMenu.bind(this));

        // hidden submit button in a form
        document.querySelectorAll('.hidden-form input')
            .forEach(button => button.onchange = this.revealForm.bind(this));

        // browser back behavior
        document.querySelectorAll('[data-back]')
            .forEach(button => button.onclick = this.back);
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

    polling(el, delay) {
        let poller = this;

        delay = delay || 10000;
        delay += (Math.random() * 1000);

        setTimeout(function() {
            fetch('/api/updates/' + el.getAttribute('data-poll'))
                .then(response => response.json())
                .then(data => poller.updateCountElement(el, data));
            poller.polling(el, delay * 1.25);
        }, delay, el);
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

        if (hidden) {
            this.removeClass(hidden, 'hidden');
        }
    }

    toggleAction(e) {
        let el = e.currentTarget;
        let pressed = el.getAttribute('aria-pressed') == 'false';
        let targetId = el.getAttribute('data-controls');

        document.querySelectorAll('[data-controls="' + targetId + '"]')
            .forEach(t => {
                t.setAttribute('aria-pressed', (t.getAttribute('aria-pressed') == 'false'))
            });

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
        let checkbox = el.getAttribute('data-controls-checkbox');

        if (checkbox) {
            document.getElementById(checkbox).checked = !!pressed;
        }

        // set focus, if appropriate
        let focus = el.getAttribute('data-focus-target');

        if (focus) {
            let focusEl = document.getElementById(focus);

            focusEl.focus();
            setTimeout(function() { focusEl.selectionStart = focusEl.selectionEnd = 10000; }, 0);
        }
    }

    // @todo Only update status if the promise is successful.
    interact(e) {
        e.preventDefault();

        let identifier = e.target.getAttribute('data-id');

        this.ajaxPost(e.target);

        // @todo This probably should be done with IDs.
        document.querySelectorAll(`.${identifier}`)
            .forEach(t => this.addRemoveClass(t, 'hidden', t.className.indexOf('hidden') == -1));
    }

    toggleMenu(e) {
        let el = e.currentTarget;
        let expanded = el.getAttribute('aria-expanded') == 'false';
        let targetId = el.getAttribute('data-controls');

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

    addRemoveClass(el, classname, bool) {
        if (bool) {
            this.addClass(el, classname);
        } else {
            this.removeClass(el, classname);
        }
    }

    addClass(el, classname) {
        let classes = el.className.split(' ');

        if (classes.indexOf(classname) > -1) {
            return;
        }

        el.className = classes.concat(classname).join(' ');
    }

    removeClass(el, className) {
        let classes = [];

        if (el.className) {
            classes = el.className.split(' ');
        }

        const idx = classes.indexOf(className);

        if (idx > -1) {
            classes.splice(idx, 1);
        }

        el.className = classes.join(' ');
    }
}
