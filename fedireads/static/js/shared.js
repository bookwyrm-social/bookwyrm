function show_compose(element, e) {
    e.preventDefault();
    var visible_compose_boxes = document.getElementsByClassName('visible');
    for (var i = 0; i < visible_compose_boxes.length; i++) {
        visible_compose_boxes[i].className = 'compose-suggestion';
    }

    var target_id = 'compose-' + element.id;
    var target = document.getElementById(target_id);
    target.className += ' visible';
}

function hide_element(element) {
    var classes = element.parentElement.className;
    element.parentElement.className = classes.replace('visible', '');
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

function rate(e) {
    e.preventDefault();
    ajaxPost(e.target);
    rating = e.target.value;
    var stars = e.target.parentElement.getElementsByClassName('icon');
    for (var i = 0; i < stars.length ; i++) {
        stars[i].className = rating < i ? 'icon icon-star-full' : 'icon icon-star-empty';
    }
    return true;
}

function tabChange(e) {
    e.preventDefault();
    var target = e.target.parentElement;
    var identifier = target.getAttribute('data-id');

    var options_class = target.getAttribute('data-category');
    var options = document.getElementsByClassName(options_class);
    for (var i = 0; i < options.length; i++) {
        if (!options[i].className.includes('hidden')) {
            options[i].className += ' hidden';
        }
    }

    var tabs = target.parentElement.children;
    for (i = 0; i < tabs.length; i++) {
        if (tabs[i].getAttribute('data-id') == identifier) {
            tabs[i].className += ' active';
        } else {
            tabs[i].className = tabs[i].className.replace('active', '');
        }
    }

    var el = document.getElementById(identifier);
    el.className = el.className.replace('hidden', '');
}

function ajaxPost(form) {
    fetch(form.action, {
        method : "POST",
        body: new FormData(form)
    });
}
