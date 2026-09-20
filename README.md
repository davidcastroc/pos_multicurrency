# La Leona POS Multimoneda PRO — Odoo 18

Versión 18.0.2.1.1.

## Flujo funcional
- Venta comercial USD: producto, impuestos, total y pendiente permanecen visibles en USD.
- Venta comercial CRC: producto, impuestos, total y pendiente permanecen visibles en CRC.
- Cobro físico: Efectivo CRC/USD, SINPE, Tarjeta CRC/USD y Transferencia CRC/USD.
- Si la moneda de pago difiere de la venta, el panel muestra la conversión.
- El vuelto físico puede elegirse CRC o USD independientemente de si la venta nació en CRC o USD.
- Cada pago conserva moneda física, monto nativo y snapshot del tipo de cambio.
- La contabilidad continúa en moneda de compañía (CRC).
- Arqueo físico separado por moneda.

## Tipo de cambio
La fuente predeterminada es `res.currency`, alimentada por `l10n_cr_currency_rate_live` (BCCR), el mismo componente de localización usado por Facturación Electrónica. El POS muestra fuente y fecha en la pantalla de pago. Para USD/CRC el snapshot se toma al cargar/usar el POS y se conserva en líneas/pagos.

## Despliegue
1. Reemplazar el módulo `pos_multicurrency`.
2. Actualizar: `odoo-update pos_multicurrency`.
3. Reiniciar assets/servicio si Odoo.sh no lo hace automáticamente.
4. Hacer recarga dura del navegador y limpiar `sessionStorage` si se arrastra un cajero viejo.

## Validación local realizada
- Compilación Python.
- Parseo XML.
- Parseo del manifest.
- Sintaxis JavaScript con Node.

La validación funcional final requiere ejecutarlo contra la base staging real de Odoo 18, porque este entorno no puede ejecutar esa base ni sus módulos Enterprise/localización.
