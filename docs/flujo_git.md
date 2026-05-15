# Flujo Git recomendado

## Objetivo

Poder trabajar entre la PC principal y la notebook sin perder contexto ni pisar cambios.

## Flujo sugerido

### Antes de empezar en una maquina

```bash
git pull origin main
```

Esto trae:
- codigo actualizado
- documentacion
- handoff

## Durante el trabajo

Hacer cambios chicos y enfocados.

Recomendacion:
- una funcionalidad o mejora por commit
- evitar mezclar cambios de UI con cambios grandes de logica si no hace falta

## Antes de confirmar

Verificar:

```bash
git status
git diff
```

## Confirmar cambios

```bash
git add .
git commit -m "Descripcion clara del cambio"
```

Ejemplos de mensajes:
- `Mejoro home operativa`
- `Agrego cierre simple de cobranza`
- `Documento estado actual del proyecto`

## Subir cambios

```bash
git push origin main
```

## En la otra maquina

Antes de seguir trabajando:

```bash
git pull origin main
```

## Recomendacion general

- hacer pull antes de empezar
- hacer commit cuando algo ya funciona
- hacer push al terminar un bloque importante
- preferir commits chicos y claros

