# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    # ============================================================
    # CONFIGURACIÓN MULTIMONEDA
    # ============================================================

    enable_pos_multicurrency = fields.Boolean(
        string="Habilitar multimoneda"
    )

    allowed_currency_ids = fields.Many2many(
        "res.currency",
        "pos_config_allowed_currency_rel",
        "config_id",
        "currency_id",
        string="Monedas aceptadas",
        domain=[("active", "=", True)],
    )

    default_change_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda predeterminada del vuelto",
        domain=[("active", "=", True)],
    )

    exchange_rate_source = fields.Selection(
        [
            ("odoo", "Tasas de Odoo/BCCR"),
            ("manual", "Tasas manuales del POS"),
        ],
        string="Fuente del tipo de cambio",
        default="odoo",
        required=True,
    )

    currency_rate_ids = fields.One2many(
        "pos.config.currency.rate",
        "config_id",
        string="Tasas manuales",
    )

    show_native_product_prices = fields.Boolean(
        string="Mostrar precios nativos",
        default=True,
    )

    show_company_equivalent = fields.Boolean(
        string="Mostrar equivalente contable",
        default=True,
    )

    # ============================================================
    # VALIDACIONES
    # ============================================================

    @api.constrains(
        "enable_pos_multicurrency",
        "allowed_currency_ids",
        "default_change_currency_id",
    )
    def _check_multicurrency(self):
        for config in self:

            if not config.enable_pos_multicurrency:
                continue

            if not config.allowed_currency_ids:
                raise ValidationError(
                    "Seleccione al menos una moneda aceptada."
                )

            if (
                config.default_change_currency_id
                and config.default_change_currency_id
                not in config.allowed_currency_ids
            ):
                raise ValidationError(
                    "La moneda del vuelto debe estar entre "
                    "las monedas aceptadas."
                )

    # ============================================================
    # CAMPOS QUE DEBE CARGAR EL POS
    # ============================================================

    @api.model
    def _load_pos_data_fields(self, config_id):
        """
        Extiende la carga estándar de pos.config.

        IMPORTANTE:

        1. Conservamos SIEMPRE los campos que devuelve super().
        2. Garantizamos los campos estándar que otros loaders
           de Odoo 18 consultan directamente.
        3. Solo agregamos campos que realmente existen en
           self._fields.
        4. Evitamos duplicados.

        Esto previene errores como:

            KeyError: 'use_pricelist'
            KeyError: 'printer_ids'
            KeyError: 'group_pos_manager_id'
            KeyError: 'company_id'

        sin sustituir la carga estándar de Odoo.
        """

        fields_list = list(
            super()._load_pos_data_fields(config_id) or []
        )

        # ========================================================
        # CAMPOS BASE / IDENTIFICACIÓN
        # ========================================================

        standard_pos_fields = [

            "id",
            "name",

            # ----------------------------------------------------
            # COMPAÑÍA
            # ----------------------------------------------------

            "company_id",

            # ----------------------------------------------------
            # GRUPOS / PERMISOS
            # ----------------------------------------------------

            "group_pos_manager_id",
            "group_pos_user_id",

            # ----------------------------------------------------
            # MONEDA
            # ----------------------------------------------------

            "currency_id",

            # ----------------------------------------------------
            # DIARIOS
            # ----------------------------------------------------

            "journal_id",
            "invoice_journal_id",

            # ----------------------------------------------------
            # MÉTODOS DE PAGO
            # ----------------------------------------------------

            "payment_method_ids",

            # ----------------------------------------------------
            # LISTAS DE PRECIOS
            # ----------------------------------------------------

            "pricelist_id",
            "available_pricelist_ids",
            "use_pricelist",

            # ----------------------------------------------------
            # IMPRESORAS
            # ----------------------------------------------------

            "printer_ids",
            "is_order_printer",

            # ----------------------------------------------------
            # INVENTARIO
            # ----------------------------------------------------

            "picking_type_id",
            "warehouse_id",

            # ----------------------------------------------------
            # INTERFAZ
            # ----------------------------------------------------

            "iface_tax_included",
            "iface_big_scrollbars",
            "iface_print_auto",
            "iface_print_skip_screen",
            "iface_print_via_proxy",
            "iface_scan_via_proxy",
            "iface_electronic_scale",
            "iface_cashdrawer",
            "iface_available_categ_ids",

            # ----------------------------------------------------
            # POSBOX
            # ----------------------------------------------------

            "is_posbox",
            "other_devices",

            # ----------------------------------------------------
            # ENCABEZADO / PIE
            # ----------------------------------------------------

            "is_header_or_footer",
            "receipt_header",
            "receipt_footer",
            "basic_receipt",

            # ----------------------------------------------------
            # CONTROL DE CAJA
            # ----------------------------------------------------

            "cash_control",
            "set_maximum_difference",
            "amount_authorized_diff",

            # ----------------------------------------------------
            # REDONDEO
            # ----------------------------------------------------

            "rounding_method",
            "cash_rounding",
            "only_round_cash_method",

            # ----------------------------------------------------
            # PRECIOS
            # ----------------------------------------------------

            "restrict_price_control",

            # ----------------------------------------------------
            # POSICIONES FISCALES
            # ----------------------------------------------------

            "fiscal_position_ids",
            "default_fiscal_position_id",

            # ----------------------------------------------------
            # BILLETES / MONEDAS
            # ----------------------------------------------------

            "default_bill_ids",

            # ----------------------------------------------------
            # PROPINA
            # ----------------------------------------------------

            "iface_tipproduct",
            "tip_product_id",

            # ----------------------------------------------------
            # DESCUENTOS
            # ----------------------------------------------------

            "manual_discount",

            # ----------------------------------------------------
            # ENVÍOS
            # ----------------------------------------------------

            "ship_later",
            "route_id",
            "picking_policy",

            # ----------------------------------------------------
            # TERMINAL
            # ----------------------------------------------------

            "auto_validate_terminal_payment",

            # ----------------------------------------------------
            # DISPLAY CLIENTE
            # ----------------------------------------------------

            "customer_display_type",

            # ----------------------------------------------------
            # DISPOSITIVOS / SINCRONIZACIÓN
            # ----------------------------------------------------

            "trusted_config_ids",

            # ----------------------------------------------------
            # IMÁGENES
            # ----------------------------------------------------

            "show_product_images",
            "show_category_images",

            # ----------------------------------------------------
            # EDICIÓN DE ÓRDENES
            # ----------------------------------------------------

            "order_edit_tracking",
        ]

        # ========================================================
        # CAMPOS OPCIONALES SEGÚN BUILD / MÓDULOS DE ODOO 18
        # ========================================================

        optional_standard_fields = [

            # Pago rápido
            "use_fast_payment",
            "fast_payment_method_ids",

            # Presets
            "use_presets",
            "default_preset_id",
            "available_preset_ids",

            # Restaurante
            "module_pos_restaurant",

            # Descuento
            "module_pos_discount",

            # Empleados
            "module_pos_hr",

            # SMS
            "module_pos_sms",

            # Avatax
            "module_pos_avatax",

            # Categorías
            "limit_categories",
            "iface_group_by_categ",

            # Régimen fiscal
            "tax_regime_selection",

            # Notas
            "note_ids",

            # Contabilidad
            "is_closing_entry_by_product",

            # Orden de líneas
            "orderlines_sequence_in_cart_by_category",

            # Display cliente
            "customer_display_bg_img_name",

            # Márgenes
            "is_margins_costs_accessible_to_every_user",

            # Sesión
            "has_active_session",

            # Impresión
            "proxy_ip",

            # Secuencias / configuración
            "uuid",
            "active",
        ]

        # ========================================================
        # CAMPOS DE POS_MULTICURRENCY
        # ========================================================

        multicurrency_fields = [

            "enable_pos_multicurrency",

            "allowed_currency_ids",

            "default_change_currency_id",

            "exchange_rate_source",

            "show_native_product_prices",

            "show_company_equivalent",
        ]

        # ========================================================
        # UNIR CAMPOS
        # ========================================================

        required_fields = (
            standard_pos_fields
            + optional_standard_fields
            + multicurrency_fields
        )

        for field_name in required_fields:

            # El campo tiene que existir realmente en esta versión
            # del modelo.
            if field_name not in self._fields:
                continue

            # Evitar duplicados.
            if field_name in fields_list:
                continue

            fields_list.append(field_name)

        return fields_list

    # ============================================================
    # DIARIOS DE EFECTIVO
    # ============================================================

    def _mc_unique_cash_journal(self, name, code):
        """
        Obtiene o crea un diario de efectivo para el POS.

        IMPORTANTE:

        El diario permanece contablemente en moneda de compañía.

        La moneda física CRC/USD se maneja mediante
        payment_currency_id en pos.payment.method.
        """

        self.ensure_one()

        Journal = self.env["account.journal"].sudo()

        # --------------------------------------------------------
        # BUSCAR DIARIO EXISTENTE
        # --------------------------------------------------------

        journal = Journal.search(
            [
                (
                    "company_id",
                    "=",
                    self.company_id.id,
                ),
                (
                    "name",
                    "=",
                    name,
                ),
            ],
            limit=1,
        )

        if journal:

            # No queremos que el diario quede configurado
            # contablemente en USD.
            #
            # La contabilidad continúa en moneda compañía.
            if journal.currency_id:
                journal.currency_id = False

            return journal

        # --------------------------------------------------------
        # BUSCAR DIARIO DE EFECTIVO BASE
        # --------------------------------------------------------

        base = Journal.search(
            [
                (
                    "company_id",
                    "=",
                    self.company_id.id,
                ),
                (
                    "type",
                    "=",
                    "cash",
                ),
                (
                    "default_account_id",
                    "!=",
                    False,
                ),
            ],
            limit=1,
        )

        # --------------------------------------------------------
        # VALORES DEL NUEVO DIARIO
        # --------------------------------------------------------

        vals = {
            "name": name,
            "code": code,
            "type": "cash",
            "company_id": self.company_id.id,

            # False = moneda de la compañía.
            "currency_id": False,
        }

        # --------------------------------------------------------
        # REUTILIZAR CUENTAS
        # --------------------------------------------------------

        if base:

            vals["default_account_id"] = (
                base.default_account_id.id
            )

            if (
                "profit_account_id" in base._fields
                and base.profit_account_id
            ):
                vals["profit_account_id"] = (
                    base.profit_account_id.id
                )

            if (
                "loss_account_id" in base._fields
                and base.loss_account_id
            ):
                vals["loss_account_id"] = (
                    base.loss_account_id.id
                )

        return Journal.create(vals)

    # ============================================================
    # INSTALAR MÉTODOS DE PAGO CRC / USD
    # ============================================================

    def action_install_cr_payment_methods(self):
        """
        Crea o actualiza:

        - Efectivo CRC
        - Efectivo USD
        - SINPE Móvil
        - Tarjeta CRC
        - Tarjeta USD
        - Transferencia CRC
        - Transferencia USD
        """

        Method = self.env["pos.payment.method"].sudo()
        Currency = self.env["res.currency"].sudo()
        Journal = self.env["account.journal"].sudo()

        for config in self:

            # ====================================================
            # CRC
            # ====================================================

            crc = config.company_id.currency_id

            # ====================================================
            # USD
            # ====================================================

            usd = Currency.search(
                [
                    ("name", "=", "USD"),
                    ("active", "=", True),
                ],
                limit=1,
            )

            if not usd:
                raise ValidationError(
                    "No se encontró la moneda USD activa en Odoo."
                )

            # ====================================================
            # DIARIO EFECTIVO CRC
            # ====================================================

            cash_crc_journal = (
                config._mc_unique_cash_journal(
                    "Efectivo CRC POS",
                    "ECRC",
                )
            )

            # ====================================================
            # DIARIO EFECTIVO USD
            # ====================================================

            cash_usd_journal = (
                config._mc_unique_cash_journal(
                    "Efectivo USD POS",
                    "EUSD",
                )
            )

            # ====================================================
            # DIARIO BANCARIO
            # ====================================================

            bank = Journal.search(
                [
                    (
                        "company_id",
                        "=",
                        config.company_id.id,
                    ),
                    (
                        "type",
                        "=",
                        "bank",
                    ),
                ],
                limit=1,
            )

            # ====================================================
            # DEFINICIÓN DE MÉTODOS
            # ====================================================

            specs = [

                (
                    "Efectivo CRC",
                    "cash_crc",
                    crc,
                    cash_crc_journal,
                ),

                (
                    "Efectivo USD",
                    "cash_usd",
                    usd,
                    cash_usd_journal,
                ),

                (
                    "SINPE Móvil",
                    "sinpe",
                    crc,
                    bank,
                ),

                (
                    "Tarjeta CRC",
                    "card_crc",
                    crc,
                    bank,
                ),

                (
                    "Tarjeta USD",
                    "card_usd",
                    usd,
                    bank,
                ),

                (
                    "Transferencia CRC",
                    "transfer_crc",
                    crc,
                    bank,
                ),

                (
                    "Transferencia USD",
                    "transfer_usd",
                    usd,
                    bank,
                ),
            ]

            methods = Method.browse()

            # ====================================================
            # CREAR / ACTUALIZAR
            # ====================================================

            for (
                name,
                kind,
                currency,
                journal,
            ) in specs:

                method = Method.search(
                    [
                        (
                            "company_id",
                            "=",
                            config.company_id.id,
                        ),
                        (
                            "mc_kind",
                            "=",
                            kind,
                        ),
                    ],
                    limit=1,
                )

                vals = {
                    "name": name,
                    "mc_kind": kind,
                    "payment_currency_id": currency.id,
                }

                if journal:
                    vals["journal_id"] = journal.id

                # -----------------------------------------------
                # ACTUALIZAR
                # -----------------------------------------------

                if method:

                    method.write(vals)

                # -----------------------------------------------
                # CREAR
                # -----------------------------------------------

                else:

                    vals["company_id"] = (
                        config.company_id.id
                    )

                    method = Method.create(vals)

                methods |= method

            # ====================================================
            # ACTIVAR MULTIMONEDA
            # ====================================================

            config.write(
                {
                    "enable_pos_multicurrency": True,

                    "allowed_currency_ids": [
                        (
                            6,
                            0,
                            (crc | usd).ids,
                        )
                    ],

                    "default_change_currency_id": (
                        crc.id
                    ),

                    "payment_method_ids": [
                        (
                            4,
                            method.id,
                        )
                        for method in methods
                    ],
                }
            )

        # ========================================================
        # NOTIFICACIÓN
        # ========================================================

        return {
            "type": "ir.actions.client",

            "tag": "display_notification",

            "params": {

                "title": "POS multimoneda",

                "message": (
                    "Métodos CRC/USD creados y asignados."
                ),

                "type": "success",

                "sticky": False,
            },
        }


# ================================================================
# TIPO DE CAMBIO MANUAL
# ================================================================


class PosConfigCurrencyRate(models.Model):

    _name = "pos.config.currency.rate"

    _description = "Tipo de cambio manual del POS"

    _order = "currency_id"

    # ============================================================
    # POS
    # ============================================================

    config_id = fields.Many2one(
        "pos.config",
        required=True,
        ondelete="cascade",
    )

    # ============================================================
    # MONEDA
    # ============================================================

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        domain=[("active", "=", True)],
    )

    # ============================================================
    # TASA
    # ============================================================

    company_per_unit = fields.Float(
        string="Moneda compañía por 1 unidad",
        digits=(16, 8),
        required=True,
        help=(
            "Ejemplo: si la compañía usa CRC y "
            "1 USD equivale a 520 CRC, escriba 520."
        ),
    )

    # ============================================================
    # RESTRICCIONES SQL
    # ============================================================

    _sql_constraints = [

        (
            "config_currency_unique",

            "unique(config_id, currency_id)",

            "Solo puede existir una tasa por moneda y POS.",
        ),

        (
            "positive_rate",

            "check(company_per_unit > 0)",

            "El tipo de cambio debe ser mayor que cero.",
        ),
    ]