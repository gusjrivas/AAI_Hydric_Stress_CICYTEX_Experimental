## 1. Contrato y aislamiento

- [x] 1.1 Especificar con TDD el puerto y el caso de uso consultivo.
- [x] 1.2 Exigir revisión humana y abstención por baja confianza.
- [x] 1.3 Probar fallback no bloqueante ante motor deshabilitado o no disponible.

## 2. Adaptador y API

- [x] 2.1 Especificar antes de implementar el contrato HTTP de Laya.
- [x] 2.2 Implementar timeout, validación fail-closed y revisión trazable.
- [x] 2.3 Exponer una ruta v2 aditiva, inyectable y sin persistencia ni mutaciones.
- [x] 2.4 Mantener Laya desactivada por defecto.

## 3. Suministro y verificación

- [x] 3.1 Fijar y verificar Laya 0.4.2 y PyTorch CPU en runtime aislado.
- [x] 3.2 Fijar revisión y SHA-256 del checkpoint y tokenizer multilingüe.
- [x] 3.3 Ejecutar inferencia de humo con el checkpoint fijado.
- [x] 3.4 Ejecutar regresiones dirigidas de CICYTEX, Pergamino, Melchor Romero,
      laboratorio y frontend.
- [ ] 3.5 Construir un corpus etiquetado de comentarios del dominio, separado por sitio.
- [ ] 3.6 Medir exactitud, calibración, cobertura y costo de abstención fuera de muestra.
- [ ] 3.7 Autorizar la visualización de sugerencias sólo si el gate 3.6 es aprobado;
      mantener siempre revisión humana y rollback por configuración.

