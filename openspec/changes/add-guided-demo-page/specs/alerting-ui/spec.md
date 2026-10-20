# Spec delta: alerting-ui

## ADDED Requirements

### Requirement: Recorrido guiado de cuatro sitios

La interfaz DEBE ofrecer la ruta `#demo-guiada` con un recorrido secuencial de cuatro sitios (CICYTEX, Pergamino, Melchor Romero y Sensores simulados) que muestre «Paso N de 4» con una barra de progreso y, por sitio, únicamente: el semáforo «Sin alerta» / «Alerta prevista» con «N de 3 modelos coinciden con este resultado», el botón «Avanzar un día», una línea «De dónde sale» y un `<details>` «Ver detalle técnico». La ruta DEBE reutilizar los clientes existentes, NO DEBE requerir endpoints nuevos y NO DEBE alterar `#demo` ni las pantallas de cada sitio. El recorrido DEBE declarar que es un recorrido y no una evaluación, que es apoyo a la decisión y que no riega ni decide cuánto regar; NO DEBE mostrar probabilidades ni atribuir resultados de un sitio a otro, y NO DEBE mencionar a Laya.

#### Scenario: Semáforo y acuerdo entre modelos

- **GIVEN** un sitio con una emisión y un ensamble de tres modelos
- **WHEN** se muestra el paso
- **THEN** se ve «Alerta prevista» o «Sin alerta» según la decisión combinada
- **AND** «N de 3 modelos coinciden con este resultado» cuenta los modelos cuyo resultado es el mostrado.

#### Scenario: Avanzar un día revela lo observado

- **GIVEN** un sitio con el resultado oculto
- **WHEN** la persona pulsa «Avanzar un día»
- **THEN** se muestra el valor observado del día objetivo y si hubo o no humedad baja
- **AND** antes de pulsar no se muestra ningún valor observado ni conclusión
- **AND** el foco pasa a la región del resultado y el botón queda deshabilitado.

#### Scenario: Observación no independiente

- **GIVEN** que el valor del día objetivo está imputado, no verificado o ausente en la fuente
- **WHEN** se revela el día
- **THEN** se declara que no es una observación independiente o que no hay observación
- **AND** no se afirma que hubo o no humedad baja ni que el pronóstico coincidió.

#### Scenario: Laboratorio simulado

- **GIVEN** el cuarto paso
- **WHEN** se muestra
- **THEN** figura rotulado «SIMULACIÓN» y «sin sensor físico conectado»
- **AND** el semáforo aparece sólo después del escenario A (lecturas normales)
- **AND** «Avanzar un día» muestra el escenario B como anomalía de medición, no como humedad baja
- **AND** se declara que la comparación entre modelos no está disponible en el laboratorio.

#### Scenario: Detalle técnico honesto

- **GIVEN** un sitio con o sin hashes y commit registrados
- **WHEN** se abre «Ver detalle técnico» (cerrado por defecto)
- **THEN** se muestran el SHA-256 del dataset y el commit sólo si existen
- **AND** lo ausente figura «no disponible» o «no registrado», sin inferirlo del repositorio actual.

#### Scenario: Error recuperable

- **GIVEN** que falla la carga o el avance de un paso
- **WHEN** ocurre el error
- **THEN** se muestra un mensaje en español con `role="alert"` y un botón «Reintentar»
- **AND** no queda un semáforo vigente ni un resultado de la consulta fallida.

#### Scenario: Navegación accesible

- **GIVEN** el recorrido abierto
- **WHEN** se cambia de sitio con «Siguiente sitio» o «Sitio anterior»
- **THEN** el foco pasa al título del paso y «Paso N de 4» se actualiza
- **AND** los botones y el resumen del detalle miden al menos 44 px de alto
- **AND** volver a un sitio lo reinicia sin conservar el resultado revelado.
