# Uso basico de Git en este proyecto

## Ver estado actual

```bash
git status
```

## Agregar cambios

```bash
git add .
```

## Crear un commit

```bash
git commit -m "Descripcion del cambio"
```

## Ver historial

```bash
git log --oneline
```

## Ver cambios antes de confirmar

```bash
git diff
```

## Volver al ultimo commit descartando cambios sin confirmar

```bash
git restore .
```

## Volver un archivo puntual al ultimo commit

```bash
git restore ruta/del/archivo.py
```

## Nota sobre la base local

`db.sqlite3` queda ignorada en este proyecto porque hoy contiene datos locales y demo.
Eso evita subir o confirmar datos de prueba por error.
Las migraciones si deben versionarse.
