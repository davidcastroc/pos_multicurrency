# -*- coding: utf-8 -*-
"""Bridge between La Leona POS multicurrency and Costa Rica FE POS.

Accounting stays in company currency (CRC).  The fiscal document uses the
single commercial currency stored on POS lines.  This file deliberately does
not replace the FE serializers: it lets l10n_cr_invoice generate its normal
XML and converts the monetary layer to the commercial currency afterwards.
"""
from odoo import api, models
from odoo.exceptions import ValidationError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _mc_fiscal_context(self):
        self.ensure_one()
        lines = self.lines.filtered(lambda l: l.qty and not getattr(l, "combo_parent_id", False))
        if not lines:
            return False
        valid = lines.filtered(lambda l: l.sale_currency_id and l.exchange_rate_snapshot > 0)
        if len(valid) != len(lines):
            return False
        currencies = valid.mapped("sale_currency_id")
        if len(currencies) != 1:
            raise ValidationError(
                "La orden POS mezcla monedas comerciales. Hacienda requiere una sola moneda por comprobante."
            )
        # A single order must keep a single frozen rate. Small float differences
        # are tolerated, but materially different snapshots are rejected.
        rates = [float(l.exchange_rate_snapshot or 0.0) for l in valid]
        rate = rates[0]
        if any(abs(r - rate) > 0.000001 for r in rates[1:]):
            raise ValidationError(
                "La orden POS contiene tipos de cambio distintos. No se generará un comprobante fiscal inconsistente."
            )
        currency = currencies[0]
        company_currency = self.company_id.currency_id
        return {
            "currency": currency,
            "currency_id": currency.id,
            "company_currency": company_currency,
            "rate": 1.0 if currency == company_currency else rate,
            "is_company": currency == company_currency,
        }

    @api.model
    def _load_pos_data_fields(self, config_id):
        result = super()._load_pos_data_fields(config_id)
        # These fields are supplied by l10n_cr_invoice_pos after sync, but also
        # loading them makes reprints/TicketScreen/reopened orders deterministic.
        fiscal = [
            # Native invoicing relation. Odoo PaymentScreen checks
            # currentOrder.raw.account_move immediately after syncAllOrders().
            # If this field is absent from read_pos_data(), Odoo throws the
            # special {code: 401, message: "Backend Invoice"} object even
            # though the invoice was successfully created on the server.
            "account_move", "is_invoiced", "to_invoice",

            # Costa Rica electronic-document fields used by the FE receipt.
            "document_id", "voucher_type_id", "voucher_number", "date_issue",
            "number", "clave_cr", "ind_state", "reference_nc", "QR_code",
        ]
        available = self._fields
        return list(dict.fromkeys(result + [name for name in fiscal if name in available]))


class CEDocument(models.Model):
    _inherit = "ce.document"

    def _mc_pos_fiscal_context(self):
        self.ensure_one()
        if not getattr(self, "order_id", False):
            return False
        return self.order_id._mc_fiscal_context()

    def action_gen_xml(self, *args, **kwargs):
        # Set CE currency BEFORE the normal FE engine builds/signs the XML.
        for doc in self:
            ctx = doc._mc_pos_fiscal_context()
            if ctx and doc.currency_id != ctx["currency"]:
                doc.currency_id = ctx["currency"]
        return super().action_gen_xml(*args, **kwargs)

    @api.depends("invoice_id", "order_id")
    def _amount_total(self):
        super()._amount_total()
        for doc in self:
            if not getattr(doc, "order_id", False):
                continue
            ctx = doc._mc_pos_fiscal_context()
            if not ctx:
                continue
            rate = ctx["rate"] or 1.0
            doc.xml_amount_total = abs((doc.order_id.amount_total or 0.0) / rate)
            doc.xml_amount_tax = abs((doc.order_id.amount_tax or 0.0) / rate)

    def get_payment_way(self, cedoc=None, classdoc=None):
        self.ensure_one()
        if not getattr(self, "order_id", False):
            return super().get_payment_way(cedoc, classdoc)

        ctx = self._mc_pos_fiscal_context()
        if not ctx:
            return super().get_payment_way(cedoc, classdoc)

        # MedioPago is expressed in the DOCUMENT currency, never necessarily in
        # the physical tender currency. pos.payment.amount is the accounting CRC
        # equivalent, therefore dividing by the fiscal snapshot is deterministic.
        rate = ctx["rate"] or 1.0
        remaining = abs((self.order_id.amount_total or 0.0) / rate)
        result = []
        payments = self.order_id.payment_ids.filtered(lambda p: not p.is_change)
        for index, pay in enumerate(payments, 1):
            if remaining <= 0:
                break
            fiscal_amount = abs((pay.amount or 0.0) / rate)
            amount = min(remaining, fiscal_amount)
            method = pay.payment_method_id.l10n_cr_payment_method_id
            code = method.code if method else "99"
            payment_way = classdoc.MedioPago(TipoMedioPago=code, TotalMedioPago=amount)
            if code == "99":
                payment_way.set_MedioPagoOtros(self.limit(pay.payment_method_id.name, 100))
            result.append(payment_way)
            remaining = max(0.0, self.currency_id.round(remaining - amount))
            if index >= 4:
                break
        return result

    @staticmethod
    def _mc_scale(obj, getter, setter, divisor):
        get = getattr(obj, "get_" + getter, None)
        set_ = getattr(obj, "set_" + setter, None)
        if not get or not set_:
            return
        value = get()
        if value is not None:
            set_(abs(float(value) / divisor))

    def _mc_convert_generated_pos_xml(self, cedoc, classdoc, ctx):
        """Convert monetary values generated from CRC accounting into native fiscal currency."""
        rate = float(ctx["rate"] or 1.0)
        if ctx["is_company"] or rate == 1.0:
            # Still force the explicit official representation.
            summary = cedoc.get_ResumenFactura()
            code = classdoc.CodigoMonedaType(CodigoMoneda=ctx["currency"].name)
            code.set_TipoCambio(1.0)
            summary.set_CodigoTipoMoneda(code)
            return cedoc

        detail = cedoc.get_DetalleServicio()
        for line in detail.get_LineaDetalle():
            for field in ("PrecioUnitario", "MontoTotal", "SubTotal", "BaseImponible", "ImpuestoNeto", "MontoTotalLinea"):
                self._mc_scale(line, field, field, rate)
            for discount in (line.get_Descuento() or []):
                self._mc_scale(discount, "MontoDescuento", "MontoDescuento", rate)
            for tax in (line.get_Impuesto() or []):
                self._mc_scale(tax, "Monto", "Monto", rate)
                ex = tax.get_Exoneracion() if hasattr(tax, "get_Exoneracion") else None
                if ex:
                    self._mc_scale(ex, "MontoExoneracion", "MontoExoneracion", rate)

        summary = cedoc.get_ResumenFactura()
        summary_fields = (
            "TotalServGravados", "TotalServExentos", "TotalServExonerado",
            "TotalMercanciasGravadas", "TotalMercanciasExentas", "TotalMercExonerada",
            "TotalGravado", "TotalExento", "TotalExonerado", "TotalVenta",
            "TotalDescuentos", "TotalVentaNeta", "TotalImpuesto", "TotalOtrosCargos",
            "TotalComprobante",
        )
        for field in summary_fields:
            self._mc_scale(summary, field, field, rate)

        # Tax breakdown is monetary too.
        getter = getattr(summary, "get_TotalDesgloseImpuesto", None)
        if getter:
            for tax_total in (getter() or []):
                self._mc_scale(tax_total, "TotalMontoImpuesto", "TotalMontoImpuesto", rate)

        code = classdoc.CodigoMonedaType(CodigoMoneda=ctx["currency"].name)
        code.set_TipoCambio(abs(rate))
        summary.set_CodigoTipoMoneda(code)
        cedoc.set_ResumenFactura(summary)
        return cedoc

    def _gen_detail_and_summary(self, cedoc, classdoc):
        result = super()._gen_detail_and_summary(cedoc, classdoc)
        self.ensure_one()
        ctx = self._mc_pos_fiscal_context()
        if ctx:
            return self._mc_convert_generated_pos_xml(result, classdoc, ctx)
        return result
