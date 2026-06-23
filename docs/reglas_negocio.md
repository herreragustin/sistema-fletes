# Reglas de negocio

## Flujo de fletes

Flujo actual:
- pendiente
- en_curso
- finalizado
- cancelado

Cuando pasa a `en_curso`:
- guarda fecha y hora real de inicio
- si se vuelve a poner en `en_curso`, reinicia ese horario real con el ultimo cambio valido
- al volver a `en_curso`, limpia la fecha y hora de finalizacion anterior

Cuando pasa a `finalizado`:
- guarda fecha y hora real de finalizacion
- queda disponible en Facturacion
- si se vuelve a finalizar despues de una correccion, actualiza nuevamente la finalizacion y recalcula la duracion

Cuando vuelve a `pendiente`:
- limpia fecha y hora real de inicio
- limpia fecha y hora real de finalizacion
- deja la duracion sin datos

Carga operativa:
- si el flete se carga en tiempo real, el sistema sigue guardando los horarios automaticamente al cambiar de estado
- si el flete ya fue realizado y se carga directamente como `finalizado`, el usuario debe ingresar:
  - hora de comienzo
  - hora de finalizacion
- en ese caso ambos horarios se guardan sobre la fecha del flete y se usan para calcular la duracion
- la hora de finalizacion debe ser posterior a la hora de comienzo

## Cobro a clientes

Cada flete tiene:
- precio al cliente
- forma de pago

Formas de pago:
- efectivo
- cuenta_corriente

Reglas:
- si es efectivo, al finalizar queda cobrado
- si es cuenta corriente, al finalizar queda pendiente de cobro
- al marcar un cobro como `pendiente`, se limpia la fecha de cobro
- al volver a marcarlo como `cobrado`, se registra una nueva fecha y hora actual
- un flete solo conserva informacion de cobro mientras esta `finalizado`
- si vuelve a `pendiente`, `en_curso` o `cancelado`, se limpia la fecha de cobro del cliente
- al finalizar nuevamente, el cobro se vuelve a generar segun la forma de pago

## Cuenta corriente

La cuenta corriente de clientes:
- solo muestra viajes de `cuenta_corriente`
- no incluye efectivo

Permite:
- ver deuda pendiente
- ver viajes cobrados
- filtrar por periodo
- cerrar cobranza simple por periodo

## Liquidacion de choferes

La liquidacion del chofer es independiente del cobro al cliente.

Cada chofer tiene:
- `tipo_liquidacion`
- `porcentaje_liquidacion`

Tipos de liquidacion:
- semanal
- quincenal
- mensual

El importe del chofer:
- no usa un valor fijo global
- se calcula desde `porcentaje_liquidacion`

Formula conceptual:
- `importe_chofer = precio * porcentaje_liquidacion / 100`

## Logica de pendientes

### Pendientes de cobro cliente
Un flete entra como pendiente si:
- esta finalizado
- es cuenta corriente
- aun no fue cobrado

### Pendientes de pago chofer
Un flete entra como pendiente si:
- esta finalizado
- aun no fue liquidado al chofer

## Cierres simples

### Cierre de cobranza
Desde el detalle del cliente:
- toma los viajes pendientes visibles del periodo
- los marca como cobrados
- guarda fecha de cobro

### Cierre de liquidacion
Desde el detalle del chofer:
- toma los viajes pendientes visibles del periodo
- los marca como pagados al chofer
- guarda fecha de pago

## Home operativa

La Home responde a:
- que cobranzas hay pendientes
- que liquidaciones hay pendientes
- que fletes hay hoy
- cuales fueron los ultimos fletes cargados

No busca ser un dashboard complejo.
