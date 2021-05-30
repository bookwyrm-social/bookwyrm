/* global module */

module.exports = {
    "extends": "stylelint-config-sass-guidelines",

    "plugins": [
        "stylelint-order"
    ],

    "rules": {
        "order/order": [
            "custom-properties",
            "declarations"
        ],
        "indentation": 4
    }
};
