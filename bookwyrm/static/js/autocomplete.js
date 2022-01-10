(function() {
    'use strict';

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

        // Get suggestions
        let suggestions = getSuggestions(input.value, mimetypeTrie);

        const boxId = input.getAttribute("list");

        // Create suggestion box, if needed
        let suggestionsBox = document.getElementById(boxId);

        // Clear existing suggestions
        suggestionsBox.innerHTML = "";

        // Populate suggestions box
        suggestions.forEach(suggestion => {
            const suggestionItem = document.createElement("option");

            suggestionItem.textContent = suggestion;
            suggestionsBox.appendChild(suggestionItem);
        });
    }

    function getSuggestions(input, trie) {
        // Follow the trie through the provided input
        input.split("").forEach(letter => {
            trie = trie[letter];

            if (!trie) {
                return;
            }
        });

        if (!trie) {
            return [];
        }

        return searchTrie(input, trie);
    }

    function searchTrie(output, trie) {
        const options = Object.keys(trie);

        if (!options.length) {
            return [output];
        }

        return options.map(option => {
            const newTrie = trie[option];

            if (!newTrie) {
                return;
            }

            return searchTrie(output + option, trie[option]);
        }).reduce((prev, next) => prev.concat(next));
    }

    document
        .querySelectorAll('[data-autocomplete]')
        .forEach(input => {
            input.addEventListener('input', autocomplete);
        });
})();

const mimetypeTrie = {
    "p": {
        "d": {
            "f": {
                "": {},
                "x": {},
            },
        },
        "n": {
            "g": {}
        },
    }
};

