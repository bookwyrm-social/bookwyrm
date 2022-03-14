(function () {
    "use strict";

    /**
     * Duplicate an input field
     *
     * @param {event} the click even on the associated button
     */
    function duplicateInput(event) {
        const trigger = event.currentTarget;
        const input_id = trigger.dataset.duplicate;
        const orig = document.getElementById(input_id);
        const parent = orig.parentNode;
        const new_count = parent.querySelectorAll("input").length + 1;

        let input = orig.cloneNode();

        input.id += "-" + new_count;
        input.value = "";

        let label = parent.querySelector("label").cloneNode();

        label.setAttribute("for", input.id);

        parent.appendChild(label);
        parent.appendChild(input);
    }

    document
        .querySelectorAll("[data-duplicate]")
        .forEach((node) => node.addEventListener("click", duplicateInput));
})();
