# Change: Triaje consultivo de observaciones con Laya

Estado: implementación en sombra; activación funcional pendiente de evaluación de dominio.

## Why

Las observaciones humanas pueden crecer y requieren una clasificación consistente para
priorizar su revisión, pero la evidencia disponible no autoriza que un modelo externo
modifique validaciones, predicciones o recalibraciones. Laya permite experimentar con
decisiones tipadas locales sin enviar comentarios a un servicio hospedado.

## What Changes

- Caso de uso de triaje con un puerto `DecisionPolicyEngine` independiente del proveedor.
- Adaptador HTTP de Laya con timeout, validación de esquema y trazabilidad de revisión.
- Abstención por baja confianza y fallback determinista ante indisponibilidad.
- Endpoint aditivo `POST /api/v2/feedback/triage`, siempre consultivo y con revisión
  humana obligatoria.
- Laya desactivada por defecto; código, runtime y checkpoint fijados y documentados.

## Impact

HU5 (`human-feedback`) y UI (`alerting-ui`), con soporte de HU6 para integración.
CRISP-DM: despliegue e integración experimental. No modifica ninguna configuración
base / +sintéticos / +anomalías / completa, ni hipótesis, datasets, targets, ventanas,
modelos predictivos, recalibración o resultados históricos. HU7/HU8 permanecen fuera
de alcance. Aporta material justificable al capítulo 3; no acredita mejora científica.

