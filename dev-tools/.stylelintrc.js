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
        "indentation": 4,
        "property-no-vendor-prefix": null,
        "color-function-notation": null,
        "declaration-block-no-redundant-longhand-properties": null,
        "no-descending-specificity": null,
        "alpha-value-notation": null
    }
};
