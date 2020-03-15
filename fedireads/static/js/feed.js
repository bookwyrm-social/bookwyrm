function show_compose(element) {
    var visible_compose_boxes = document.getElementsByClassName('visible');
    for (var i = 0; i < visible_compose_boxes.length; i++) {
        visible_compose_boxes[i].className = 'compose-suggestion';
    }

    var target_id = 'compose-' + element.id;
    var target = document.getElementById(target_id);
    target.className += ' visible';
}

