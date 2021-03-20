// set javascript listeners
function updateDisplay(e) {
    // used in set reading goal
    var key = e.target.getAttribute('data-id');
    var value = e.target.getAttribute('data-value');
    window.localStorage.setItem(key, value);

    document.querySelectorAll('[data-hide="' + key + '"]')
        .forEach(t => setDisplay(t));
}

function setDisplay(el) {
    // used in set reading goal
    var key = el.getAttribute('data-hide');
    var value = window.localStorage.getItem(key);
    addRemoveClass(el, 'hidden', value);
}
