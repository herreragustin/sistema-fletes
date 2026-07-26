# Estado actual del proyecto

## Estado general

El proyecto se encuentra funcional y usable para operacion diaria en entorno local.
Quedo preparado para comenzar carga de datos reales luego de limpiar la base demo.

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
- Sistema anterior - solo consulta

## Funcionalidades implementadas

### Operacion
- alta y edicion de clientes
- alta y edicion de choferes
- alta y edicion de fletes
- generacion de reservas recurrentes semanales y mensuales desde nuevo flete
- filtros en listados
- listado de Fletes como historico operativo por defecto:
  - muestra fletes finalizados hasta hoy
  - permite filtrar por rango Desde/Hasta
  - permite ver otros estados al elegir un filtro explicito
- listado de Clientes con busqueda por nombre, telefono o direccion
- listado de Fletes con informacion operativa ampliada:
  - horarios reales
  - duracion
  - estado de cobro
  - fecha de cobro
- estados de flete:
  - pendiente, mostrado al usuario como Reserva
  - en_curso
  - finalizado
  - cancelado

### Tiempos del flete
- guarda inicio real al pasar a `en_curso`
- guarda finalizacion real al pasar a `finalizado`
- calcula duracion
- permite cargar manualmente hora de comienzo y finalizacion cuando un flete se registra despues de haber sido realizado
- los fletes en curso ya muestran la hora de inicio real en los listados operativos

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
- porcentaje estandar de liquidacion: 80%
- porcentajes distintos de 80% se muestran como excepciones
- importe del chofer calculado dinamicamente
- ficha de chofer con historial operativo
- cierre simple de liquidacion
- fallback al ultimo periodo con movimientos
- indicadores visuales de cierre disponible

### Home
- redisenada como panel operativo diario
- muestra fletes del dia con datos operativos completos
- muestra reservas futuras de los proximos 7 dias por separado
- los fletes en curso muestran hora de inicio real
- mantiene accesos rapidos utiles
- la version anterior quedo respaldada en `core/templates/core/panel_inicio_anterior.html`

### Reportes
- totales por periodo
- cobrado / pendiente cliente
- pagado / pendiente chofer
- resultado estimado general

### Sistema anterior
- se importaron datos historicos del sistema anterior en tablas separadas del modulo `importadores`
- la seccion historica es solo consulta y se navega desde `Sistema anterior`
- incluye clientes historicos, choferes historicos, viajes historicos y reservas historicas
- los datos historicos no se mezclan con clientes, choferes ni fletes operativos actuales
- la importacion usa parser con fallback de aliases para recuperar correctamente origen y destino
- el mapeo de choferes historicos fue corregido inspeccionando `CHOFERES.DBF` para usar apellido real desde `APELL` y nombre desde `NOMBRE`
- la importacion historica ahora guarda `usuario_carga`, `tipo_probable`, `motivo_clasificacion` y `vehiculo_chofer` para ayudar a distinguir posibles fletes
- la clasificacion historica es probable y se basa principalmente en chofer/vehiculo, no en una decision operativa definitiva
- la interfaz historica agrega filtros por usuario de carga, tipo probable, chofer y la vista `solo posibles fletes`

## Partes mas consolidadas

- flujo operativo de fletes
- cuenta corriente de clientes
- liquidacion de choferes
- cierres simples
- navegacion principal
- backup previo a limpieza de datos demo
- consulta historica del sistema anterior separada de la operacion actual

## Partes pendientes o mejorables

- reportes mas detallados por cliente y chofer
- exportaciones
- validaciones adicionales
- cierres mas formales o historicos
- mejoras administrativas y de UX fina
