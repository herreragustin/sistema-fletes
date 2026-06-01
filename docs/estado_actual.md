# Estado actual del proyecto

## Estado general

El proyecto se encuentra funcional y usable para operacion diaria en entorno local.

Base tecnica actual:
- Django
- SQLite
- entorno virtual local
- Git y GitHub configurados
- trabajo posible entre PC y notebook usando el mismo repo

## Modulos existentes

- Clientes
- Choferes
- Fletes
- Facturacion
- Cuenta corriente de clientes
- Liquidacion de choferes
- Reportes
- Importadores DBF aislados

## Funcionalidades implementadas

### Operacion
- alta y edicion de clientes
- alta y edicion de choferes
- alta y edicion de fletes
- filtros en listados
- estados de flete:
  - pendiente
  - en_curso
  - finalizado
  - cancelado

### Tiempos del flete
- guarda inicio real al pasar a `en_curso`
- guarda finalizacion real al pasar a `finalizado`
- calcula duracion

### Cobro a clientes
- facturacion basada en fletes finalizados
- efectivo se cobra automaticamente
- cuenta corriente queda pendiente de cobro

### Cuenta corriente
- solo incluye viajes con `forma_de_pago = cuenta_corriente`
- resumen por cliente
- detalle por cliente
- ficha de cliente con historial operativo
- filtros por periodo
- cierre simple de cobranza
- indicadores visuales de cierre disponible

### Liquidacion de choferes
- tipo de liquidacion por chofer:
  - semanal
  - quincenal
  - mensual
- porcentaje de liquidacion por chofer
- importe del chofer calculado dinamicamente
- ficha de chofer con historial operativo
- cierre simple de liquidacion
- fallback al ultimo periodo con movimientos
- indicadores visuales de cierre disponible

### Home
- simple y operativa
- cobranzas pendientes
- liquidaciones pendientes
- fletes de hoy
- ultimos fletes cargados
- accesos rapidos

### Reportes
- totales por periodo
- cobrado / pendiente cliente
- pagado / pendiente chofer
- resultado estimado general

## Partes mas consolidadas

- flujo operativo de fletes
- cuenta corriente de clientes
- liquidacion de choferes
- cierres simples
- navegacion principal

## Partes pendientes o mejorables

- reportes mas detallados por cliente y chofer
- exportaciones
- validaciones adicionales
- cierres mas formales o historicos
- mejoras administrativas y de UX fina
