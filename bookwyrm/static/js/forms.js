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
     * Duplicate a whole block recursively
     *
     * @param {node} the node to duplicate
     * @param {input_id} the node id
     * @param {parent} the parent to attach to
     */
    function duplicateBlock({node, input_id, parent}) {

        const duplicate = node.cloneNode()
        parent.appendChild(duplicate);
        if (node.hasChildNodes()) {
            node.childNodes.forEach( (chld) => {
                duplicateBlock({"node": chld, "parent": duplicate})
            })
        }
    }

    /**
     * Duplicate an input field
     *
     * @param {event} the click event on the associated button
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

        if (trigger.dataset.sibling) {
            const siblingId = trigger.dataset.sibling;
            const target = document.getElementById(siblingId);
            const newParent = target.parentNode.cloneNode();
            target.parentNode.parentNode.appendChild(newParent);
            const controlDiv = document.createElement("div");
            controlDiv.className = "control";
            controlDiv.appendChild(label);
            controlDiv.appendChild(input);
            newParent.appendChild(controlDiv);
            duplicateBlock({"node": target, "input_id": siblingId, "parent": newParent})
        } else {
            parent.appendChild(label);
            parent.appendChild(input);
        }
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
