/* global module */

module.exports = {
    "extends": "stylelint-config-standard-scss",

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
    },
    "overrides": [
        {
            "files": [ "../**/themes/bookwyrm-*.scss" ],
            "rules": {
                "no-invalid-position-at-import-rule": null
            }
        }
    ]
};
