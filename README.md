# Préstamos 💰

Una pequeña **calculadora** de préstamos escrita en PowerShell. Calcula la cuota
mensual de un préstamo usando el sistema de amortización francesa (cuota fija).

## Requisitos

- Windows con PowerShell (ya viene instalado).

## Uso

```powershell
# Cargar la función en la sesión actual
. .\prestamos.ps1

# Cuota de un préstamo de 12000 al 12% anual a 12 meses
Get-CuotaMensual -Capital 12000 -TasaAnual 0.12 -Meses 12
```

## Parámetros

| Parámetro    | Descripción                                |
|--------------|--------------------------------------------|
| `-Capital`   | Monto del préstamo.                        |
| `-TasaAnual` | Tasa de interés anual (ej. `0.12` = 12%).  |
| `-Meses`     | Número de cuotas mensuales.                |

## Pruebas

```powershell
powershell -File .\test-prestamos.ps1
```

## Licencia

MIT
