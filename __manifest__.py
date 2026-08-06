# -*- coding: utf-8 -*-
{
    "name": "La Leona | POS Multimoneda",
    "version": "18.0.1.0.0",
    "summary": "Productos, cobros, vuelto y cierres de caja en CRC y USD para Punto de Venta.",
    "category": "Point of Sale",
    "author": "Castro Li",
    "website": "https://castrolicr.com",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "stock", "account"],
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
            "la_leona_pos_multicurrency/static/src/js/multicurrency_models.js",
            "la_leona_pos_multicurrency/static/src/js/payment_screen.js",
            "la_leona_pos_multicurrency/static/src/xml/payment_screen.xml",
            "la_leona_pos_multicurrency/static/src/scss/multicurrency.scss",
        ],
    },
    "installable": True,
    "application": False,
}
