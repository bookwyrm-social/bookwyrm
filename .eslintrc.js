/* global module */

module.exports = {
    "env": {
        "browser": true,
        "es6": true
    },

    "extends": "eslint:recommended",

    "rules": {
        // Possible Errors
        "no-async-promise-executor": "error",
        "no-await-in-loop": "error",
        "no-class-assign": "error",
        "no-confusing-arrow": "error",
        "no-const-assign": "error",
        "no-dupe-class-members": "error",
        "no-duplicate-imports": "error",
        "no-template-curly-in-string": "error",
        "no-useless-computed-key": "error",
        "no-useless-constructor": "error",
        "no-useless-rename": "error",
        "require-atomic-updates": "error",

        // Best practices
        "strict": "error",
        "no-var": "error",

        // Stylistic Issues
        "arrow-spacing": "error",
        "capitalized-comments": [
            "warn",
            "always",
            {
                "ignoreConsecutiveComments": true
            },
        ],
        "keyword-spacing": "error",
        "lines-around-comment": [
            "error",
            {
                "beforeBlockComment": true,
                "beforeLineComment": true,
                "allowBlockStart": true,
                "allowClassStart": true,
                "allowObjectStart": true,
                "allowArrayStart": true,
            },
        ],
        "no-multiple-empty-lines": [
            "error",
            {
                "max": 1,
            },
        ],
        "padded-blocks": [
            "error",
            "never",
        ],
        "padding-line-between-statements": [
            "error",
            {
                // always before return
                "blankLine": "always",
                "prev": "*",
                "next": "return",
            },
            {
                // always before block-like expressions
                "blankLine": "always",
                "prev": "*",
                "next": "block-like",
            },
            {
                // always after variable declaration
                "blankLine": "always",
                "prev": [ "const", "let", "var" ],
                "next": "*",
            },
            {
                // not necessary between variable declaration
                "blankLine": "any",
                "prev": [ "const", "let", "var" ],
                "next": [ "const", "let", "var" ],
            },
        ],
        "space-before-blocks": "error",
    }
};
