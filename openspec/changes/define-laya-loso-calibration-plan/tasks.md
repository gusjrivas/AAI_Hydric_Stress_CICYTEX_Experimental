## 1. Contrato TDD

- [x] 1.1 Registrar tests RED para folds LOSO exhaustivos, disjuntos y group-safe.
- [x] 1.2 Fijar schema y política hash de calibración como identidades versionadas.
- [x] 1.3 Probar determinismo, independencia del orden y ceguera a labels/payload.

## 2. Plan estructural

- [x] 2.1 Construir un fold ordenado por cada uno de los tres sitios requeridos.
- [x] 2.2 Retener el sitio completo de test y repartir los sitios restantes entre ajuste y calibración sin dividir grupos.
- [x] 2.3 Reservar `ceil(20%)` de grupos por sitio mediante hash versionado, sin RNG ni seed.
- [x] 2.4 Reutilizar la misma cohorte de calibración de cada sitio en todos los folds donde entrena.
- [x] 2.5 Fallar de forma cerrada con menos de dos grupos en cualquier sitio.
- [x] 2.6 Validar construcción directa, reemplazos, exhaustividad y commitment de asignación.

## 3. Privacidad y estado

- [x] 3.1 Mantener registros de cada partición y `assignment_sha256` fuera de `repr`.
- [x] 3.2 Excluir del summary el commitment, IDs privados y payload humano; publicar sólo identidad segura, conteos y flags.
- [x] 3.3 Mantener evaluación, calibración, suficiencia, shadow review y producción en falso.
- [x] 3.4 Mantener el módulo aislado de flujos científicos y operacionales existentes.

## 4. Protocolo pendiente

- [ ] 4.1 Verificar externamente que corpus y nombres de grupos fueron congelados antes de construir o inspeccionar el plan.
- [ ] 4.2 Preregistrar N, balance y criterios de suficiencia de la muestra real.
- [ ] 4.3 Implementar runner, tuning y calibrador sobre estas particiones mediante un cambio TDD separado.
- [ ] 4.4 Calcular métricas y comparación pareada contra baseline con intervalos bootstrap.
- [ ] 4.5 Integrar readiness y runtime sólo después de revisión científica independiente.
