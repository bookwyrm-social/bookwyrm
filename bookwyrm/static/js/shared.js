// set up javascript listeners
window.onload = function() {
    // buttons that display or hide content
    document.querySelectorAll('[data-controls]')
        .forEach(t => t.onclick = toggleAction);

    // javascript interactions (boost/fav)
    Array.from(document.getElementsByClassName('interaction'))
        .forEach(t => t.onsubmit = interact);

    // handle aria settings on menus
    Array.from(document.getElementsByClassName('pulldown-menu'))
        .forEach(t => t.onclick = toggleMenu);

    // hidden submit button in a form
    document.querySelectorAll('.hidden-form input')
        .forEach(t => t.onchange = revealForm);

    // polling
    document.querySelectorAll('[data-poll]')
        .forEach(el => polling(el));

    // browser back behavior
    document.querySelectorAll('[data-back]')
        .forEach(t => t.onclick = back);

    Array.from(document.getElementsByClassName('tab-group'))
        .forEach(t => new TabGroup(t));

    // display based on localstorage vars
    document.querySelectorAll('[data-hide]')
        .forEach(t => setDisplay(t));

    // update localstorage
    Array.from(document.getElementsByClassName('set-display'))
        .forEach(t => t.onclick = updateDisplay);

    // Toggle all checkboxes.
    document
        .querySelectorAll('[data-action="toggle-all"]')
        .forEach(input => {
            input.addEventListener('change', toggleAllCheckboxes);
        });
};

function back(e) {
    e.preventDefault();
    history.back();
}

function polling(el, delay) {
    delay = delay || 10000;
    delay += (Math.random() * 1000);
    setTimeout(function() {
        fetch('/api/updates/' + el.getAttribute('data-poll'))
            .then(response => response.json())
            .then(data => updateCountElement(el, data));
        polling(el, delay * 1.25);
    }, delay, el);
}

function updateCountElement(el, data) {
    const currentCount = el.innerText;
    const count = data.count;
    if (count != currentCount) {
        addRemoveClass(el.closest('[data-poll-wrapper]'), 'hidden', count < 1);
        el.innerText = count;
    }
}


function revealForm(e) {
    var hidden = e.currentTarget.closest('.hidden-form').getElementsByClassName('hidden')[0];
    if (hidden) {
        removeClass(hidden, 'hidden');
    }
}


function toggleAction(e) {
    var el = e.currentTarget;
    var pressed = el.getAttribute('aria-pressed') == 'false';

    var targetId = el.getAttribute('data-controls');
    document.querySelectorAll('[data-controls="' + targetId + '"]')
        .forEach(t => t.setAttribute('aria-pressed', (t.getAttribute('aria-pressed') == 'false')));

    if (targetId) {
        var target = document.getElementById(targetId);
        addRemoveClass(target, 'hidden', !pressed);
        addRemoveClass(target, 'is-active', pressed);
    }

    // show/hide container
    var container = document.getElementById('hide-' + targetId);
    if (!!container) {
        addRemoveClass(container, 'hidden', pressed);
    }

    // set checkbox, if appropriate
    var checkbox = el.getAttribute('data-controls-checkbox');
    if (checkbox) {
        document.getElementById(checkbox).checked = !!pressed;
    }

    // set focus, if appropriate
    var focus = el.getAttribute('data-focus-target');
    if (focus) {
        var focusEl = document.getElementById(focus);
        focusEl.focus();
        setTimeout(function(){ focusEl.selectionStart = focusEl.selectionEnd = 10000; }, 0);
    }
}

function interact(e) {
    e.preventDefault();
    ajaxPost(e.target);
    var identifier = e.target.getAttribute('data-id');
    Array.from(document.getElementsByClassName(identifier))
        .forEach(t => addRemoveClass(t, 'hidden', t.className.indexOf('hidden') == -1));
}

function toggleMenu(e) {
    var el = e.currentTarget;
    var expanded = el.getAttribute('aria-expanded') == 'false';
    el.setAttribute('aria-expanded', expanded);
    var targetId = el.getAttribute('data-controls');
    if (targetId) {
        var target = document.getElementById(targetId);
        addRemoveClass(target, 'is-active', expanded);
    }
}

function ajaxPost(form) {
    fetch(form.action, {
        method : "POST",
        body: new FormData(form)
    });
}

function addRemoveClass(el, classname, bool) {
    if (bool) {
        addClass(el, classname);
    } else {
        removeClass(el, classname);
    }
}

function addClass(el, classname) {
    var classes = el.className.split(' ');
    if (classes.indexOf(classname) > -1) {
        return;
    }
    el.className = classes.concat(classname).join(' ');
}

function removeClass(el, className) {
    var classes = [];
    if (el.className) {
        classes = el.className.split(' ');
    }
    const idx = classes.indexOf(className);
    if (idx > -1) {
        classes.splice(idx, 1);
    }
    el.className = classes.join(' ');
}
