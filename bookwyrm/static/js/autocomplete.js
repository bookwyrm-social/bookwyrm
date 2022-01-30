(function () {
    "use strict";

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
        let trie = tries[input.getAttribute("data-autocomplete")];

        let suggestions = getSuggestions(input.value, trie);

        const boxId = input.getAttribute("list");

        // Create suggestion box, if needed
        let suggestionsBox = document.getElementById(boxId);

        // Clear existing suggestions
        suggestionsBox.innerHTML = "";

        // Populate suggestions box
        suggestions.forEach((suggestion) => {
            const suggestionItem = document.createElement("option");

            suggestionItem.textContent = suggestion;
            suggestionsBox.appendChild(suggestionItem);
        });
    }

    function getSuggestions(input, trie) {
        // Follow the trie through the provided input
        input = input.toLowerCase();

        input.split("").forEach((letter) => {
            if (!trie) {
                return;
            }

            trie = trie[letter];
        });

        if (!trie) {
            return [];
        }

        return searchTrie(trie);
    }

    function searchTrie(trie) {
        const options = Object.values(trie);

        if (typeof trie == "string") {
            return [trie];
        }

        return options
            .map((option) => {
                const newTrie = option;

                if (typeof newTrie == "string") {
                    return [newTrie];
                }

                return searchTrie(newTrie);
            })
            .reduce((prev, next) => prev.concat(next));
    }

    document.querySelectorAll("[data-autocomplete]").forEach((input) => {
        input.addEventListener("input", autocomplete);
    });
})();

const tries = {
    mimetype: {
        a: {
            a: {
                c: "AAC",
            },
            z: {
                w: "AZW",
            },
        },
        d: {
            a: {
                i: {
                    s: {
                        y: "Daisy",
                    },
                },
            },
        },
        e: {
            p: {
                u: {
                    b: "ePub",
                },
            },
        },
        f: {
            l: {
                a: {
                    c: "FLAC",
                },
            },
        },
        h: {
            t: {
                m: {
                    l: "HTML",
                },
            },
        },
        m: {
            4: {
                a: "M4A",
                b: "M4B",
            },
            o: {
                b: {
                    i: "MOBI",
                },
            },
            p: {
                3: "MP3",
            },
        },
        o: {
            g: {
                g: "OGG",
            },
        },
        p: {
            d: {
                f: "PDF",
            },
            l: {
                a: {
                    i: {
                        n: {
                            t: {
                                e: {
                                    x: {
                                        t: "Plaintext",
                                    },
                                },
                            },
                        },
                    },
                },
            },
            r: {
                i: {
                    n: {
                        t: {
                            " ": {
                                b: {
                                    o: {
                                        o: {
                                            k: "Print book",
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
};
