// set up javascript listeners
window.onload = function() {
    // let buttons set keyboard focus
    Array.from(document.getElementsByClassName('toggle-control'))
        .forEach(t => t.onclick = toggleAction);

    // javascript interactions (boost/fav)
    Array.from(document.getElementsByClassName('interaction'))
        .forEach(t => t.onsubmit = interact);

    // select all
    Array.from(document.getElementsByClassName('select-all'))
        .forEach(t => t.onclick = selectAll);

    // toggle between tabs
    Array.from(document.getElementsByClassName('tab-change-nested'))
        .forEach(t => t.onclick = tabChangeNested);
    Array.from(document.getElementsByClassName('tab-change'))
        .forEach(t => t.onclick = tabChange);

    // handle aria settings on menus
    Array.from(document.getElementsByClassName('pulldown-menu'))
        .forEach(t => t.onclick = toggleMenu);

    // display based on localstorage vars
    document.querySelectorAll('[data-hide]')
        .forEach(t => setDisplay(t));

    // update localstorage
    Array.from(document.getElementsByClassName('set-display'))
        .forEach(t => t.onclick = updateDisplay);

    // toggle display
    Array.from(document.getElementsByClassName('toggle-button'))
        .forEach(t => t.onclick = toggleDisplay);
};

function updateDisplay(e) {
    var key = e.target.getAttribute('data-id');
    var value = e.target.getAttribute('data-value');
    window.localStorage.setItem(key, value);

    document.querySelectorAll('[data-hide="' + key + '"]')
        .forEach(t => setDisplay(t));
}

function setDisplay(el) {
    var key = el.getAttribute('data-hide');
    var value = window.localStorage.getItem(key)
    if (!value) {
        el.className = el.className.replace('hidden', '');
    } else if (value != null && !!value) {
        el.className += ' hidden';
    }
}

function toggleAction(e) {
    var pressed = e.currentTarget.getAttribute('aria-pressed') == 'false';
    e.currentTarget.setAttribute('aria-pressed', pressed);

    var targetId = e.currentTarget.getAttribute('data-controls');
    if (targetId) {
        var target = document.getElementById(targetId);
        if (pressed) {
            target.className = target.className.replace('hidden', '');
        } else {
            target.className += ' hidden';
        }

    }

    // set hover, if appropriate
    var hover = e.currentTarget.getAttribute('data-hover-target');
    if (hover) {
        document.getElementById(hover).focus();
    }

    // set checkbox, if appropriate
    var checkbox = e.currentTarget.getAttribute('data-controls-checkbox');
    if (checkbox) {
        document.getElementById(checkbox).checked = !!pressed;
    }
}


function interact(e) {
    e.preventDefault();
    ajaxPost(e.target);
    var identifier = e.target.getAttribute('data-id');
    var elements = document.getElementsByClassName(identifier);
    for (var i = 0; i < elements.length; i++) {
        if (elements[i].className.includes('hidden')) {
            elements[i].className = elements[i].className.replace('hidden', '');
        } else {
            elements[i].className += ' hidden';
        }
    }
    return true;
}

function selectAll(e) {
    e.target.parentElement.parentElement.querySelectorAll('[type="checkbox"]')
        .forEach(t => t.checked=true);
}

function tabChangeNested(e) {
    var target = e.target.closest('li')
    var parentElement = target.parentElement.closest('li').parentElement;
    handleTabChange(target, parentElement)
}

function tabChange(e) {
    var target = e.target.closest('li')
    var parentElement = target.parentElement;
    handleTabChange(target, parentElement)
}


function handleTabChange(target, parentElement) {
    parentElement.querySelectorAll('[aria-selected="true"]')
        .forEach(t => t.setAttribute("aria-selected", false));
    target.querySelector('[role="tab"]').setAttribute("aria-selected", true);

    parentElement.querySelectorAll('li')
        .forEach(t => t.className='');
    target.className = 'is-active';
}

function toggleMenu(e) {
    var el = e.target.closest('.pulldown-menu');
    el.setAttribute('aria-expanded', el.getAttribute('aria-expanded') == 'false');
}

function ajaxPost(form) {
    fetch(form.action, {
        method : "POST",
        body: new FormData(form)
    });
}
