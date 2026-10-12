## 1. Contrato TDD

- [x] 1.1 Registrar tests RED de binding, cobertura outer-test, identidad y estados fail-closed.
- [x] 1.2 Registrar tests RED de validación numérica, canonicalización y privacidad.
- [x] 1.3 Implementar el contrato GREEN sin modificar los tests de aceptación.
- [x] 1.4 Endurecer por RED/GREEN commitments privados, attestations no verificadas y proveedor/revisión cerrados.

## 2. Contrato y evidencia

- [x] 2.1 Ligar internamente el contrato a plan y corpus, y declarar referencia de runtime, protocolo, proveedor y revisión.
- [x] 2.2 Exigir una predicción por cada registro outer-test y rechazar cualquier otra cobertura.
- [x] 2.3 Validar probabilidades, argmax, confidence y latencia sin estados ambiguos.
- [x] 2.4 Canonicalizar el lote independientemente del orden de entrada y de representaciones numéricas equivalentes.
- [x] 2.5 Sellar todo el contenido con un commitment privado y revalidarlo ante reemplazos.

## 3. Privacidad, estado y aislamiento

- [x] 3.1 Excluir filas, IDs, categorías, probabilidades, commitments y bindings de plan/corpus de `repr` y summary.
- [x] 3.2 Probar que claves y valores de `loso_plan_sha256` y `evaluation_corpus_sha256` no aparecen públicamente.
- [x] 3.3 Publicar sólo identidades no derivadas del corpus, conteo, agregado de latencia y flags fail-closed.
- [x] 3.4 Mantener no verificadas las attestations de runtime, origen, gold-blind y supply.
- [x] 3.5 Mantener ejecución, suficiencia, shadow review y producción en falso.
- [x] 3.6 Mantener el módulo aislado de flujos científicos y operacionales existentes.

## 4. Trabajo diferido

- [ ] 4.1 Materializar y verificar identidad de runtime, lockfile y SBOM en PR15.
- [ ] 4.2 Verificar origen y supply chain contra artefactos externos.
- [ ] 4.3 Implementar el executor/adapter real de Laya mediante otro cambio TDD.
- [ ] 4.4 Atestiguar ejecución gold-blind y ejecutar el protocolo preregistrado.
- [ ] 4.5 Calcular calibración, métricas, baseline pareado e intervalos bootstrap.
- [ ] 4.6 Evaluar readiness, shadow review y producción sólo tras revisión científica independiente.
