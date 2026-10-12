## 1. Contrato estructural TDD

- [x] 1.1 Registrar tests RED para manifest, registros y cohorte humana adjudicada.
- [x] 1.2 Implementar un loader fail-closed con schema cerrado y JSON canónico.
- [x] 1.3 Endurecer por TDD metadata de procedencia, attestations y construcción directa.

## 2. Procedencia, privacidad y adjudicación

- [x] 2.1 Ligar el manifest a los registros privados mediante conteo y SHA-256 canónico.
- [x] 2.2 Exigir sitios exactos y prohibir que un `group_id` cruce sitios.
- [x] 2.3 Exigir anotadores distintos y adjudicación trazable por un tercero ante desacuerdo.
- [x] 2.4 Publicar un summary determinista sin payload privado ni identificadores humanos.
- [x] 2.5 Mantener el corpus real fuera del repositorio.

## 3. Límites de seguridad

- [x] 3.1 Mantener `scientifically_sufficient=false` y producción desautorizada.
- [x] 3.2 Aislar el contrato del gate, backend y pipelines científicos u operacionales.
- [x] 3.3 Documentar que digests de protocolos, custodia y flags de privacidad son attestations, no prueba automática.

## 4. Trabajo diferido

- [ ] 4.1 Preregistrar N mínimo, acuerdo interanotador y balance de clases/sitios.
- [ ] 4.2 Implementar LOSO por sitio/grupo y un split independiente de calibración.
- [ ] 4.3 Ejecutar baseline en los mismos folds, delta pareado e intervalos bootstrap.
- [ ] 4.4 Verificar artefactos externos de protocolos y cadena de custodia.
- [ ] 4.5 Evaluar elegibilidad para shadow review en un cambio separado.
