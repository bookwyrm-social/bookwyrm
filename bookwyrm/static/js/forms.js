(function () {
    "use strict";

    /**
     * Remove input field
     *
     * @param {event} the button click event
     */
    function removeInput(event) {
        const trigger = event.currentTarget;
        const input_id = trigger.dataset.remove;
        const input = document.getElementById(input_id);

        input.remove();
    }

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

    document
        .querySelectorAll("[data-remove]")
        .forEach((node) => node.addEventListener("click", removeInput));

    // Get element, add a keypress listener...
    document.getElementById("subjects").addEventListener("keypress", function (e) {
        // Linstening to element e.target
        // If e.target is an input field within "subjects" div preventDefault()
        if (e.target && e.target.nodeName == "INPUT") {
            if (event.keyCode == 13) {
                event.preventDefault();
            }
        }
    });
})();
