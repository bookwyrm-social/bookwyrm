/**
 * Set guided tour user value to False
 * @param  {csrf_token} string
 * @return {undefined}
 */

/* eslint-disable no-unused-vars */
function disableGuidedTour(csrf_token) {
    "use strict";
    fetch("/guided-tour/False", {
        headers: {
            "X-CSRFToken": csrf_token,
        },
        method: "POST",
        redirect: "follow",
        mode: "same-origin",
    });
}
