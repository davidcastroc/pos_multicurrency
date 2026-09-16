# La Leona | POS Multimoneda PRO (Odoo 18)

Incluye:

- Efectivo CRC
- Efectivo USD
- SINPE Móvil
- Tarjeta CRC
- Tarjeta USD
- Transferencia CRC
- Transferencia USD
- Productos con precio comercial CRC/USD
- PaymentScreen que conserva la moneda comercial
- Conversión CRC ↔ USD
- Compra/venta de tipo de cambio
- Vuelto seleccionable CRC/USD
- Snapshot del tipo de cambio en cada pago
- Recibo multimoneda
- Arqueo por moneda
- BCCR / Odoo / tasa manual
- Cron de actualización de tasa
- CABYS, impuestos, inventario y contabilidad quedan en moneda compañía

## Después de instalar/actualizar

1. Actualizar `pos_multicurrency`.
2. Ir a la configuración del POS.
3. Pulsar **Crear/actualizar métodos de pago CR**.
4. Seleccionar la fuente de tipo de cambio.
5. Si se usa BCCR, configurar correo/token.
6. Cerrar/reabrir el POS.
7. Hacer hard refresh del navegador si conserva assets viejos.

## Flujo esperado de prueba

Producto USD 35 + IVA 13%:
- ProductScreen: USD 35 / total USD 39.55
- PaymentScreen: USD 39.55
- Efectivo USD: recibe USD directo
- Efectivo CRC: muestra conversión y tipo de cambio
- Si entrega USD 50: permite vuelto en USD o CRC


## Nota importante sobre diarios contables

Esta versión NO crea diarios contables automáticamente durante la instalación.
Reutiliza diarios de Efectivo/Banco existentes de la compañía. Esto evita
choques con localizaciones o módulos contables que agregan campos obligatorios
a `account.account`.

Después de actualizar el módulo, entre a la configuración del POS y pulse
**Crear/actualizar métodos de pago CR**. El módulo creará/asignará los métodos
de pago utilizando los diarios existentes.


## 18.0.2.0.5 - Fix relaciones OWL/Related Models

Los datos del bootstrap de monedas son objetos JS de lectura para tasas/formato.
Nunca se deben asignar directamente a campos Many2one de los modelos POS.
Esta versión resuelve el ID contra `res.currency` y guarda el record OWL real
en `payment_currency_id` y `change_currency_id`, evitando errores como
`record.getIndexMaps is not a function` al borrar líneas de pago.


## 18.0.2.0.6 - Fix recibo / export_for_printing

`PosOrder.export_for_printing()` corre sobre el record del modelo POS, no sobre
un componente OWL. Por eso `this.env.utils` no existe ahí. El equivalente
contable del recibo ahora se formatea con `mcFormatCurrency(this.currency, ...)`.


## 18.0.2.0.7 - Cierre multimoneda físico

El popup de cierre ahora agrega un bloque **CIERRE MULTIMONEDA** que muestra:

- Recibido por moneda física.
- Vuelto entregado por moneda.
- Neto físico esperado CRC/USD.
- Detalle por método de pago.
- Equivalente contable en moneda compañía para los métodos extranjeros.

El cierre contable nativo de Odoo se conserva debajo sin modificaciones.


## 18.0.2.0.8 - Fix Owl cierre

Corrige `ctx.mcHasPhysicalData is not a function` en `ClosePosPopup`.
La condición principal del template ya no depende del método helper y se evalúa
directamente desde `props.multicurrency_summary`. También se prioriza la carga
del patch JS del popup de cierre.


## 18.0.2.0.9 - Cierre sin helpers Owl

El popup de cierre ya no llama métodos JS (`mcFormatClosingAmount`,
`mcHasPhysicalData`, etc.) desde el template heredado. Todos los importes del
arqueo multimoneda llegan preformateados desde Python y el XML solo los muestra.
Esto elimina los errores `ctx.<helper> is not a function`.


## 18.0.2.1.0 - Precio USD con impuestos incluidos

Cuando `iface_tax_included = total`, `pos_foreign_price` representa el precio
FINAL al cliente. Ejemplo: USD 35 con IVA 13% queda:

- Total comercial: USD 35.00
- Base aproximada: USD 30.97345
- IVA incluido: USD 4.02655

El módulo calcula la base en CRC utilizando los impuestos reales de la línea
y la posición fiscal, sin asumir un 13% fijo. El mismo cálculo se fuerza en
backend al preparar la base fiscal del POS, de modo que contabilidad, factura
e integración de comprobantes electrónicos reciban el monto correcto.

Nota: este cambio corrige el monto/tax base que alimenta la FE. No modifica
reglas propias del módulo de Facturación Electrónica como la clasificación
Servicio/Mercancía ni los datos geográficos del emisor.
