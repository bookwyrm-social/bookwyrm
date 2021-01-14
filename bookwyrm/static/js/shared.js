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
};

function toggleAction(e) {
    // set hover, if appropriate
    var hover = e.target.getAttribute('data-hover-target')
    if (hover) {
        document.getElementById(hover).focus();
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

function toggleMenu(el) {
    el.setAttribute('aria-expanded', el.getAttribute('aria-expanded') == 'false');
}

function ajaxPost(form) {
    fetch(form.action, {
        method : "POST",
        body: new FormData(form)
    });
}
