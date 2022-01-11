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

        return searchTrie(trie);
    }

    function searchTrie(trie) {
        const options = Object.values(trie);

        if (typeof trie == 'string') {
            return [trie];
        }

        return options.map(option => {
            const newTrie = option;

            if (typeof newTrie == 'string') {
                return [newTrie];
            }

            return searchTrie(newTrie);
        }).reduce((prev, next) => prev.concat(next));
    }

    document
        .querySelectorAll('[data-autocomplete]')
        .forEach(input => {
            input.addEventListener('input', autocomplete);
        });
})();

const mimetypeTrie = {
    "a": {
        "a": {
            "c": "AAC",
        },
        "z": {
            "w": "AZW",
        }
    },
    "d": "Daisy",
    "e": "ePub",
    "f": "FLAC",
    "h": "HTML",
    "m": {
        "4": {
            "a": "M4A",
            "b": "M4B",
        },
        "o": "MOBI",
        "p": "MP3",
    },
    "o": "OGG",
    "p": {
        "d": {
            "f": "PDF",
        },
        "l": "Plaintext",
    },
};

