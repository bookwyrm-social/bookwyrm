
(function() {
    'use strict';

    /**
     * Toggle all descendant checkboxes of a target.
     *
     * Use `data-target="ID_OF_TARGET"` on the node on which the event is listened
     * to (checkbox, button, link…), where_ID_OF_TARGET_ should be the ID of an
     * ancestor for the checkboxes.
     *
     * @example
     * <input
     *     type="checkbox"
     *     data-action="toggle-all"
     *     data-target="failed-imports"
     * >
     * @param  {Event} event
     * @return {undefined}
     */
    function toggleAllCheckboxes(event) {
        const mainCheckbox = event.target;

        document
            .querySelectorAll(`#${mainCheckbox.dataset.target} [type="checkbox"]`)
            .forEach(checkbox => checkbox.checked = mainCheckbox.checked);
    }

    document
        .querySelectorAll('[data-action="toggle-all"]')
        .forEach(input => {
            input.addEventListener('change', toggleAllCheckboxes);
        });
})();
