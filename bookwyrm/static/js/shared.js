window.onload = function() {
    var toggles = document.getElementsByClassName('toggle-control');
    //    .forEach(t => t.onclick = toggle_action);
    for (var i=0; i<toggles.length; i++) {
        toggles[i].onclick = toggle_action;
    }
};

function toggle_action(e) {
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

function reply(e) {
    e.preventDefault();
    ajaxPost(e.target);
    // TODO: display comment
    return true;
}

function selectAll(el) {
    el.parentElement.querySelectorAll('[type="checkbox"]')
        .forEach(t => t.checked=true);
}

function rate_stars(e) {
    e.preventDefault();
    ajaxPost(e.target);
    rating = e.target.rating.value;
    var stars = e.target.parentElement.getElementsByClassName('icon');
    for (var i = 0; i < stars.length ; i++) {
        stars[i].className = rating > i ? 'icon icon-star-full' : 'icon icon-star-empty';
    }
    return true;
}

function tabChange(e, nested) {
    var target = e.target.closest('li')
    var identifier = target.getAttribute('data-id');

    if (nested) {
        var parent_element = target.parentElement.closest('li').parentElement;
    } else {
        var parent_element = target.parentElement;
    }

    parent_element.querySelectorAll('[aria-selected="true"]')
        .forEach(t => t.setAttribute("aria-selected", false));
    target.querySelector('[role="tab"]').setAttribute("aria-selected", true);

    parent_element.querySelectorAll('li')
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
