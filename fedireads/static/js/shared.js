function hide_element(element) {
    var classes = element.parentElement.className;
    element.parentElement.className = classes.replace('visible', '');
}

function interact(e) {
    e.preventDefault();
    ajaxPost(e.target);
    if (e.target.className.includes('active')) {
        e.target.className = '';
    } else {
        e.target.className += ' active';
    }
    return true;
}

function comment(e) {
    e.preventDefault();
    ajaxPost(e.target);
    // TODO: display comment
    return true;
}

function ajaxPost(form, callback) {
    // jeez. https://stackoverflow.com/questions/33021995
    var url = form.action;
    var xhr = new XMLHttpRequest();

    var params = [].filter.call(form.elements, function(el) {
        return typeof(el.checked) === 'undefined' || el.checked;
    })
    .filter(function(el) { return !!el.name; })
    .filter(function(el) { return el.disabled; })
    .map(function(el) {
        return encodeURIComponent(el.name) + '=' + encodeURIComponent(el.value);
    }).join('&');

    xhr.open('POST', url);
    xhr.setRequestHeader('Content-type', 'application/x-form-urlencoded');
    xhr.setRequestHeader('X-CSRFToken', csrf_token);

    if (callback) {
        xhr.onload = callback.bind(xhr);
    }
    xhr.send(params);
}
