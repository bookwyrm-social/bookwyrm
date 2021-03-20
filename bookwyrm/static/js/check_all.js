// Toggle all checkboxes.

/**
 * Toggle all descendant checkboxes of a target.
 *
 * Use `data-target="ID_OF_TARGET"` on the node being listened to.
 *
 * @param  {Event} event - change Event
 * @return {undefined}
 */
function toggleAllCheckboxes(event) {
    const mainCheckbox = event.target;

    document
        .querySelectorAll(`#${mainCheckbox.dataset.target} [type="checkbox"]`)
        .forEach(checkbox => {checkbox.checked = mainCheckbox.checked;});
}
