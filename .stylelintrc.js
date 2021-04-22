/* global module */

module.exports = {
    "extends": "stylelint-config-standard",

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
