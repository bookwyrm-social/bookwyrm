(function () {
    "use strict";

    const mimeTypes = [
        "AAC",
        "AZW",
        "Daisy",
        "EPUB",
        "FB2",
        "FB3",
        "FLAC",
        "HTML",
        "M4A",
        "M4B",
        "MOBI",
        "MP3",
        "OGG",
        "PDF",
        "Plaintext",
        "Print book",
    ];

    const regexEscape = (string) => string.replace(/[$^*()-+.?[]{}|\\\/]/g, "\\$&");

    /**
     * Suggest a completion as a user types
     *
     * Use `data-autocomplete="<completions set identifier>"`on the input field.
     * specifying the trie to be used for autocomplete
     *
     * @example
     * <input
     *     type="input"
     *     data-autocomplete="mimetype"
     * >
     * @param  {Event} event
     * @return {undefined}
     */
    function autocomplete(event) {
        const input = event.target;

        const cleanInput = regexEscape(input.value);

        const suggestions = mimeTypes.filter((mimeType) =>
            RegExp("^" + cleanInput, "i").test(mimeType)
        );

        const boxId = input.getAttribute("list");

        // Create suggestion box, if needed
        const suggestionsBox = document.getElementById(boxId);

        // Clear existing suggestions
        suggestionsBox.innerHTML = "";

        // Populate suggestions box
        suggestions.forEach((suggestion) => {
            const suggestionItem = document.createElement("option");

            suggestionItem.textContent = suggestion;
            suggestionsBox.appendChild(suggestionItem);
        });
    }

    document.querySelectorAll("[data-autocomplete]").forEach((input) => {
        input.addEventListener("input", autocomplete);
    });
})();
