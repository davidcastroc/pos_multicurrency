# -*- coding: utf-8 -*-
{
    "name": "La Leona | POS Multimoneda",
    "version": "18.0.2.0.0",
    "summary": "Productos, cobros, vuelto y cierres de caja en CRC y USD para Punto de Venta.",
    "category": "Point of Sale",
    "author": "Castro Li",
    "website": "https://castrolicr.com",
    "license": "LGPL-3",

    "depends": [
        "point_of_sale",
        "stock",
        "account",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/pos_payment_method_views.xml",
        "views/pos_config_views.xml",
        "views/pos_order_views.xml",
        "views/pos_session_views.xml",
    ],

    "assets": {
        "point_of_sale._assets_pos": [
            "pos_multicurrency/static/src/js/multicurrency_models.js",
            "pos_multicurrency/static/src/js/order_summary_multicurrency.js",
            "pos_multicurrency/static/src/js/payment_screen.js",
            "pos_multicurrency/static/src/js/cash_controls.js",

            "pos_multicurrency/static/src/xml/order_summary_multicurrency.xml",
            "pos_multicurrency/static/src/xml/payment_screen.xml",
            "pos_multicurrency/static/src/xml/cash_controls.xml",

            "pos_multicurrency/static/src/scss/multicurrency.scss",
        ],
    },

    "installable": True,
    "application": False,
}