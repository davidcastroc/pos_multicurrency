# -*- coding: utf-8 -*-
import html
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_BCCR_ENDPOINT = (
    "https://gee.bccr.fi.cr/Indicadores/Suscripciones/WS/"
    "wsindicadoreseconomicos.asmx/ObtenerIndicadoresEconomicosXML"
)


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_pos_multicurrency = fields.Boolean(
        string="Habilitar multimoneda",
        default=True,
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
            ("odoo", "BCCR - Facturación Electrónica (res.currency)"),
            ("bccr", "BCCR directo (alternativo)"),
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

    bccr_user_name = fields.Char(
        string="Nombre de usuario BCCR",
        default="LA LEONA POS",
    )
    bccr_email = fields.Char(string="Correo BCCR")
    bccr_token = fields.Char(string="Token BCCR")
    bccr_buy_indicator = fields.Integer(
        string="Indicador compra",
        default=317,
    )
    bccr_sell_indicator = fields.Integer(
        string="Indicador venta",
        default=318,
    )
    mc_usd_buy_rate = fields.Float(
        string="Compra USD (CRC por USD)",
        digits=(16, 8),
        readonly=True,
    )
    mc_usd_sell_rate = fields.Float(
        string="Venta USD (CRC por USD)",
        digits=(16, 8),
        readonly=True,
    )
    mc_rate_date = fields.Date(
        string="Fecha del tipo de cambio",
        readonly=True,
    )
    mc_rate_source_label = fields.Char(
        string="Origen de tasa",
        readonly=True,
    )

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
                    _("Seleccione al menos una moneda aceptada.")
                )
            if (
                config.default_change_currency_id
                and config.default_change_currency_id
                not in config.allowed_currency_ids
            ):
                raise ValidationError(
                    _("La moneda del vuelto debe estar entre las monedas aceptadas.")
                )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Load the complete POS configuration payload safely.

        In Odoo 18 ``pos.config`` does not define a complete base field list in
        ``point_of_sale`` itself; the generic ``pos.load.mixin`` starts with an
        empty list and installed addons extend it. A custom override that only
        appends a handful of fields can therefore remove keys required by other
        POS loaders (company_id, use_pricelist, printer_ids, etc.).

        A POS session loads only one configuration record, so loading all
        non-binary fields is both robust and inexpensive, and keeps this module
        compatible with point_of_sale, pos_hr, restaurant and other extensions.
        """
        fields_list = []

        for name, field in self._fields.items():
            # Binary configuration assets are not needed by downstream model
            # domains and can be large. Everything else is safe for the single
            # pos.config record loaded by a session.
            if field.type == "binary":
                continue
            fields_list.append(name)

        return fields_list


    @api.constrains(
        "pricelist_id",
        "use_pricelist",
        "available_pricelist_ids",
        "journal_id",
        "invoice_journal_id",
        "payment_method_ids",
    )
    def _check_currencies(self):
        """
        Permite listas de precios en las monedas habilitadas por
        POS Multimoneda, manteniendo las demás validaciones nativas.
        """
        for config in self:
            # La lista predeterminada debe seguir estando entre las disponibles.
            if (
                config.use_pricelist
                and config.pricelist_id
                and config.pricelist_id not in config.available_pricelist_ids
            ):
                raise ValidationError(
                    _("The default pricelist must be included in the available pricelists.")
                )

            # Mantener validación nativa de métodos de pago.
            for pm in config.payment_method_ids:
                if (
                    pm.journal_id
                    and pm.journal_id.currency_id
                    and pm.journal_id.currency_id != config.currency_id
                ):
                    raise ValidationError(
                        _(
                            "All payment methods must be in the same currency as "
                            "the Sales Journal or the company currency if that is not set."
                        )
                    )

            if config.use_pricelist:
                if config.enable_pos_multicurrency:
                    # Multimoneda:
                    # permitir únicamente monedas expresamente habilitadas,
                    # además de la moneda propia del POS.
                    allowed_currencies = (
                        config.allowed_currency_ids | config.currency_id
                    )

                    invalid_pricelists = config.available_pricelist_ids.filtered(
                        lambda pricelist:
                            pricelist.currency_id not in allowed_currencies
                    )

                    if invalid_pricelists:
                        raise ValidationError(
                            _(
                                "Las siguientes listas de precios usan una moneda "
                                "no habilitada para este POS: %s"
                            )
                            % ", ".join(
                                invalid_pricelists.mapped("display_name")
                            )
                        )

                else:
                    # POS normal: comportamiento estándar de Odoo.
                    if any(
                        config.available_pricelist_ids.mapped(
                            lambda pricelist:
                                pricelist.currency_id != config.currency_id
                        )
                    ):
                        raise ValidationError(
                            _(
                                "All available pricelists must be in the same currency "
                                "as the company or as the Sales Journal set on this "
                                "point of sale if you use the Accounting application."
                            )
                        )

            # Mantener validación nativa del diario de facturación.
            if (
                config.invoice_journal_id.currency_id
                and config.invoice_journal_id.currency_id != config.currency_id
            ):
                raise ValidationError(
                    _(
                        "The invoice journal must be in the same currency as "
                        "the Sales Journal or the company currency if that is not set."
                    )
                )

    def open_ui(self):
        for config in self:
            config._ensure_exchange_rates(silent=True)
        return super().open_ui()

    def _bccr_indicator_value(self, indicator, date):
        self.ensure_one()
        if not self.bccr_email or not self.bccr_token:
            raise UserError(
                _("Configure el correo y token de suscripción del BCCR.")
            )

        payload = urllib.parse.urlencode(
            {
                "Indicador": int(indicator),
                "FechaInicio": date.strftime("%d/%m/%Y"),
                "FechaFinal": date.strftime("%d/%m/%Y"),
                "Nombre": self.bccr_user_name or "LA LEONA POS",
                "SubNiveles": "N",
                "CorreoElectronico": self.bccr_email,
                "Token": self.bccr_token,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            _BCCR_ENDPOINT,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Odoo-POS-Multicurrency/18.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read()

        outer = ET.fromstring(body)
        inner_xml = html.unescape(outer.text or "").strip()
        if not inner_xml:
            raise UserError(_("El BCCR no devolvió información."))

        inner = ET.fromstring(inner_xml)
        for node in inner.iter():
            if node.tag.split("}")[-1].upper() == "NUM_VALOR":
                return float((node.text or "0").replace(",", "."))

        raise UserError(
            _("No fue posible localizar NUM_VALOR en la respuesta del BCCR.")
        )

    def _odoo_usd_rate(self):
        self.ensure_one()
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd:
            usd = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        if not usd:
            return 0.0

        company = self.company_id
        company_currency = company.currency_id
        date = fields.Date.context_today(self)
        return usd._convert(
            1.0,
            company_currency,
            company,
            date,
            round=False,
        )

    def _ensure_exchange_rates(self, silent=False, force=False):
        today = fields.Date.context_today(self)
        for config in self:
            try:
                if (
                    not force
                    and config.mc_rate_date == today
                    and config.mc_usd_buy_rate > 0
                    and config.mc_usd_sell_rate > 0
                ):
                    continue

                if config.exchange_rate_source == "bccr":
                    buy = config._bccr_indicator_value(
                        config.bccr_buy_indicator or 317,
                        today,
                    )
                    sell = config._bccr_indicator_value(
                        config.bccr_sell_indicator or 318,
                        today,
                    )
                    config.write(
                        {
                            "mc_usd_buy_rate": buy,
                            "mc_usd_sell_rate": sell,
                            "mc_rate_date": today,
                            "mc_rate_source_label": "BCCR",
                        }
                    )

                elif config.exchange_rate_source == "odoo":
                    rate = config._odoo_usd_rate()
                    if rate > 0:
                        config.write(
                            {
                                "mc_usd_buy_rate": rate,
                                "mc_usd_sell_rate": rate,
                                "mc_rate_date": today,
                                "mc_rate_source_label": "BCCR / Facturación Electrónica",
                            }
                        )

                elif config.exchange_rate_source == "manual":
                    usd = self.env.ref("base.USD", raise_if_not_found=False)
                    line = config.currency_rate_ids.filtered(
                        lambda r: r.currency_id == usd
                    )[:1]
                    if line:
                        config.write(
                            {
                                "mc_usd_buy_rate": line.company_per_unit_buy
                                or line.company_per_unit,
                                "mc_usd_sell_rate": line.company_per_unit_sell
                                or line.company_per_unit,
                                "mc_rate_date": today,
                                "mc_rate_source_label": "Manual",
                            }
                        )

            except Exception as exc:
                _logger.warning(
                    "No se pudo actualizar la tasa para POS %s: %s",
                    config.display_name,
                    exc,
                )
                if not silent:
                    raise

        return True

    def action_refresh_exchange_rates(self):
        self._ensure_exchange_rates(silent=False, force=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Tipo de cambio actualizado"),
                "message": _(
                    "Compra USD: %(buy).4f | Venta USD: %(sell).4f",
                    buy=self.mc_usd_buy_rate,
                    sell=self.mc_usd_sell_rate,
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def cron_refresh_exchange_rates(self):
        configs = self.search(
            [
                ("enable_pos_multicurrency", "=", True),
                ("exchange_rate_source", "in", ["bccr", "odoo"]),
            ]
        )
        configs._ensure_exchange_rates(silent=True, force=True)
        return True

    def _mc_existing_journal(
        self,
        company,
        journal_type,
        preferred_currency=False,
    ):
        Journal = self.env["account.journal"].sudo()
        journals = Journal.search(
            [
                ("company_id", "=", company.id),
                ("type", "=", journal_type),
                ("active", "=", True),
            ],
            order="sequence, id",
        )
        if not journals:
            raise UserError(
                _(
                    "No existe un diario activo de tipo %(type)s para %(company)s.",
                    type=journal_type,
                    company=company.display_name,
                )
            )
        # POS core requires payment journals to be in company/POS currency.
        company_currency = company.currency_id
        compatible = journals.filtered(
            lambda j: not j.currency_id or j.currency_id == company_currency
        )
        return compatible[:1] or journals[:1]

    def _mc_get_or_create_cash_journal(self, company, name, code):
        """Return or create a cash journal dedicated to this POS.

        Cash payment methods cannot be shared between POS configurations.
        Each POS therefore receives its own CRC/USD cash journals.
        """
        self.ensure_one()

        Journal = self.env["account.journal"].sudo()

        # Preserve the historical journal names for the original POS.
        # Every additional POS gets deterministic names based on its ID.
        if self.id == 1:
            journal_name = name
            journal_code = code
        else:
            journal_name = f"{name} - POS {self.id}"
            journal_code = f"{code[:3]}{self.id}"[:5]

        journal = Journal.search(
            [
                ("company_id", "=", company.id),
                ("type", "=", "cash"),
                ("name", "=", journal_name),
            ],
            limit=1,
        )

        if journal:
            if journal.currency_id:
                journal.write({"currency_id": False})
            return journal

        base = self._mc_existing_journal(company, "cash")

        if not base.default_account_id:
            raise UserError(
                _("El diario de efectivo base no tiene una cuenta por defecto.")
            )

        # account.journal.code must remain unique inside the company.
        candidate_code = journal_code
        counter = 1

        while Journal.search_count([
            ("company_id", "=", company.id),
            ("code", "=", candidate_code),
        ]):
            suffix = str(counter)
            candidate_code = (
                f"{journal_code[:5 - len(suffix)]}{suffix}"
            )
            counter += 1

        return Journal.create({
            "name": journal_name,
            "code": candidate_code,
            "type": "cash",
            "company_id": company.id,
            # Keep journal in company/POS currency.
            "default_account_id": base.default_account_id.id,
            "profit_account_id": base.profit_account_id.id,
            "loss_account_id": base.loss_account_id.id,
        })


    def _mc_get_or_create_cash_payment_method(
        self,
        company,
        name,
        journal,
        currency,
        kind,
        allow_change=True,
        sequence=10,
    ):
        """Return/create a cash payment method dedicated to this POS."""
        self.ensure_one()

        PaymentMethod = self.env["pos.payment.method"].sudo()

        # First try to find a cash method already assigned to THIS POS.
        method = self.payment_method_ids.filtered(
            lambda pm: pm.is_cash_count and pm.mc_kind == kind
        )[:1]

        # Preserve the historical names for the original POS.
        if self.id == 1:
            method_name = name
        else:
            method_name = f"{name} - {self.name}"

        # If this POS does not have one yet, search by its deterministic name.
        if not method:
            method = PaymentMethod.search(
                [
                    ("company_id", "=", company.id),
                    ("name", "=", method_name),
                ],
                limit=1,
            )

        vals = {
            "company_id": company.id,
            "journal_id": journal.id,
            "payment_currency_id": currency.id if currency else False,
            "allow_change_in_currency": allow_change,
            "mc_kind": kind,
            "sequence": sequence,
        }

        if method:
            if not method.open_session_ids:
                method.write(vals)
            return method

        vals["name"] = method_name
        return PaymentMethod.create(vals)


    def _mc_get_or_create_payment_method(
        self,
        company,
        name,
        journal,
        currency,
        kind,
        allow_change=True,
        sequence=10,
    ):
        PaymentMethod = self.env["pos.payment.method"].sudo()
        method = PaymentMethod.search(
            [
                ("company_id", "=", company.id),
                ("name", "=", name),
            ],
            limit=1,
        )
        vals = {
            "company_id": company.id,
            "journal_id": journal.id if journal else False,
            "payment_currency_id": currency.id if currency else False,
            "allow_change_in_currency": allow_change,
            "mc_kind": kind,
            "sequence": sequence,
        }
        if method:
            if not method.open_session_ids:
                method.write(vals)
            return method
        vals["name"] = name
        return PaymentMethod.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Create new POS configurations ready for multicurrency from birth.

        The multicurrency constraint runs during super().create(), therefore
        allowed currencies must already be present in vals before creating the
        record. The full payment-method setup is completed afterwards.
        """
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd:
            usd = self.env["res.currency"].search(
                [("name", "=", "USD")],
                limit=1,
            )

        if usd and not usd.active:
            usd.active = True

        prepared_vals_list = []

        for original_vals in vals_list:
            vals = dict(original_vals)

            company = self.env["res.company"].browse(
                vals.get("company_id") or self.env.company.id
            )
            company_currency = company.currency_id

            if not self.env.context.get("skip_mc_auto_setup"):
                allowed = company_currency | usd if usd else company_currency

                vals.update({
                    "enable_pos_multicurrency": True,
                    "allowed_currency_ids": [Command.set(allowed.ids)],
                    "default_change_currency_id": company_currency.id,
                    "cash_control": True,
                })

            prepared_vals_list.append(vals)

        configs = super().create(prepared_vals_list)

        if not self.env.context.get("skip_mc_auto_setup"):
            for config in configs:
                try:
                    config.with_context(
                        skip_mc_auto_setup=True
                    )._mc_setup_multicurrency()
                except Exception:
                    _logger.exception(
                        "No se pudo configurar automáticamente multimoneda para POS %s",
                        config.display_name,
                    )
                    raise

        return configs

    def _mc_setup_multicurrency(self):
        """Install/normalize the complete multicurrency configuration.

        Cash methods are exclusive per POS because Odoo does not allow a cash
        payment method to be shared between configurations.

        Existing non-cash multicurrency methods are reused at company level.
        This preserves commercial methods such as BCR/LAFISE cards and avoids
        creating generic duplicates every time a POS is created.
        """
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if not usd:
            usd = self.env["res.currency"].search(
                [("name", "=", "USD")],
                limit=1,
            )

        if usd and not usd.active:
            usd.active = True

        PaymentMethod = self.env["pos.payment.method"].sudo()

        for config in self:
            company = config.company_id
            company_currency = company.currency_id

            # ------------------------------------------------------------
            # 1. Dedicated cash journals/methods for THIS POS
            # ------------------------------------------------------------
            cash_crc_journal = config._mc_get_or_create_cash_journal(
                company,
                "Efectivo CRC POS",
                "ECRC",
            )

            cash_usd_journal = False
            if usd:
                cash_usd_journal = config._mc_get_or_create_cash_journal(
                    company,
                    "Efectivo USD POS",
                    "EUSD",
                )

            cash_methods = self.env["pos.payment.method"]

            cash_methods |= config._mc_get_or_create_cash_payment_method(
                company,
                "Efectivo CRC",
                cash_crc_journal,
                company_currency,
                "cash_crc",
                True,
                10,
            )

            if usd:
                cash_methods |= config._mc_get_or_create_cash_payment_method(
                    company,
                    "Efectivo USD",
                    cash_usd_journal,
                    usd,
                    "cash_usd",
                    True,
                    20,
                )

            # ------------------------------------------------------------
            # 2. Reuse existing company-level NON-CASH methods
            #
            # Cards:
            #   Keep all real commercial card methods (BCR, LAFISE, etc.).
            #
            # SINPE:
            #   Keep one method.
            #
            # Transfers:
            #   Keep one CRC and one USD method. Prefer the oldest existing
            #   method, which preserves the original production setup.
            # ------------------------------------------------------------
            company_methods = PaymentMethod.search(
                [
                    ("company_id", "=", company.id),
                    (
                        "mc_kind",
                        "in",
                        [
                            "card_crc",
                            "card_usd",
                            "sinpe",
                            "transfer_crc",
                            "transfer_usd",
                        ],
                    ),
                ],
                order="id",
            )

            selected_non_cash = self.env["pos.payment.method"]

            # Keep commercial card methods, excluding generic methods created
            # by an earlier version of this automatic setup.
            for kind in ("card_crc", "card_usd"):
                candidates = company_methods.filtered(
                    lambda pm, k=kind: pm.mc_kind == k
                )

                commercial = candidates.filtered(
                    lambda pm: pm.name not in ("Tarjeta CRC", "Tarjeta USD")
                )

                # Prefer named commercial methods. If none exist, retain one
                # generic method as a safe fallback.
                if commercial:
                    selected_non_cash |= commercial
                elif candidates:
                    selected_non_cash |= candidates[:1]

            # Exactly one SINPE method.
            sinpe = company_methods.filtered(
                lambda pm: pm.mc_kind == "sinpe"
            )[:1]

            if sinpe:
                selected_non_cash |= sinpe

            # Exactly one transfer per currency.
            for kind in ("transfer_crc", "transfer_usd"):
                transfer = company_methods.filtered(
                    lambda pm, k=kind: pm.mc_kind == k
                )[:1]

                if transfer:
                    selected_non_cash |= transfer

            # ------------------------------------------------------------
            # 3. Fallbacks
            #
            # These should normally never be necessary in La Leona because
            # the commercial methods already exist. They make fresh database
            # installations self-contained.
            # ------------------------------------------------------------
            bank_journal = config._mc_existing_journal(
                company,
                "bank",
                company_currency,
            )

            if not selected_non_cash.filtered(
                lambda pm: pm.mc_kind == "sinpe"
            ):
                selected_non_cash |= config._mc_get_or_create_payment_method(
                    company,
                    "SINPE Móvil",
                    bank_journal,
                    company_currency,
                    "sinpe",
                    False,
                    30,
                )

            if not selected_non_cash.filtered(
                lambda pm: pm.mc_kind == "card_crc"
            ):
                selected_non_cash |= config._mc_get_or_create_payment_method(
                    company,
                    "Tarjeta CRC",
                    bank_journal,
                    company_currency,
                    "card_crc",
                    False,
                    40,
                )

            if (
                usd
                and not selected_non_cash.filtered(
                    lambda pm: pm.mc_kind == "card_usd"
                )
            ):
                selected_non_cash |= config._mc_get_or_create_payment_method(
                    company,
                    "Tarjeta USD",
                    bank_journal,
                    usd,
                    "card_usd",
                    False,
                    50,
                )

            if not selected_non_cash.filtered(
                lambda pm: pm.mc_kind == "transfer_crc"
            ):
                selected_non_cash |= config._mc_get_or_create_payment_method(
                    company,
                    "Transferencia CRC",
                    bank_journal,
                    company_currency,
                    "transfer_crc",
                    False,
                    60,
                )

            if (
                usd
                and not selected_non_cash.filtered(
                    lambda pm: pm.mc_kind == "transfer_usd"
                )
            ):
                selected_non_cash |= config._mc_get_or_create_payment_method(
                    company,
                    "Transferencia USD",
                    bank_journal,
                    usd,
                    "transfer_usd",
                    False,
                    70,
                )

            # ------------------------------------------------------------
            # 4. Final deterministic configuration
            #
            # SET, not LINK:
            # replace the POS selection with exactly the intended methods.
            # Historical pos.payment records are not modified.
            # ------------------------------------------------------------
            methods = cash_methods | selected_non_cash

            allowed = (
                company_currency | usd
                if usd
                else company_currency
            )

            config.write(
                {
                    "enable_pos_multicurrency": True,
                    "allowed_currency_ids": [Command.set(allowed.ids)],
                    "default_change_currency_id": company_currency.id,
                    "cash_control": True,
                    "payment_method_ids": [Command.set(methods.ids)],
                }
            )

            config._ensure_exchange_rates(
                silent=True,
                force=False,
            )

        return True

    def action_install_cr_payment_methods(self):
        self._mc_setup_multicurrency()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Métodos de pago instalados"),
                "message": _(
                    "Se configuraron Efectivo CRC/USD, SINPE Móvil, "
                    "Tarjeta CRC/USD y Transferencia CRC/USD."
                ),
                "type": "success",
                "sticky": False,
            },
        }




class PosConfigCurrencyRate(models.Model):
    _name = "pos.config.currency.rate"
    _description = "Tipo de cambio manual del POS"
    _order = "currency_id"

    config_id = fields.Many2one(
        "pos.config",
        required=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        domain=[("active", "=", True)],
    )
    company_per_unit = fields.Float(
        string="Tasa general",
        digits=(16, 8),
        required=True,
        default=1.0,
    )
    company_per_unit_buy = fields.Float(
        string="Tasa compra",
        digits=(16, 8),
        help="Moneda compañía recibida por 1 unidad extranjera.",
    )
    company_per_unit_sell = fields.Float(
        string="Tasa venta",
        digits=(16, 8),
        help="Moneda compañía necesaria para comprar 1 unidad extranjera.",
    )

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
