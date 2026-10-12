## 1. Contrato TDD

- [x] 1.1 Registrar un commit RED con tests y fixture sintética únicamente.
- [x] 1.2 Fijar identidad de Laya 0.4.2 y checkpoint multilingüe en el contrato.
- [x] 1.3 Exigir salida canónica, determinista y sin comentarios humanos.

## 2. Evaluación offline

- [x] 2.1 Implementar verificación local de hashes y rechazo de punteros Git LFS.
- [x] 2.2 Implementar baseline por reglas sin condiciones de sitio.
- [x] 2.3 Medir accuracy, selective accuracy, macro-F1, Brier, ECE, coverage, costo y latencia.
- [x] 2.4 Desglosar por sitio y bloquear una degradación local.
- [x] 2.5 Mantener siempre desautorizada la activación productiva.

## 3. Aislamiento y regresión

- [x] 3.1 Proveer una CLI sin red ni variables `LAYA_*`.
- [x] 3.2 Prohibir dependencias desde backend y pipelines al evaluador offline.
- [x] 3.3 Ejecutar regresiones de Laya, CICYTEX, Pergamino, Melchor Romero y laboratorio mock.
- [ ] 3.4 Evaluar un corpus humano adjudicado, cross-site y fuera de muestra.
- [ ] 3.5 Agregar intervalos de confianza y delta pareado frente al baseline antes de shadow review.
