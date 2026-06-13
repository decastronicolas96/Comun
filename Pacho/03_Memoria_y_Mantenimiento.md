# Memoria de Pacho — Arquitectura y Mantenimiento

**Cómo Pacho construye, organiza y optimiza su memoria con el tiempo.**

Este es el documento que hace que Pacho **mejore con el uso** en vez de solo
acumular notas sueltas. Define dónde vive cada tipo de información, qué se guarda
y qué no, y el proceso por el cual Pacho **consolida, depura y reorganiza** su
memoria periódicamente.

> Todo esto se apoya en una idea simple: Pacho no "recuerda" entre sesiones por
> arte de magia. Recuerda porque **escribe en archivos del repositorio y hace
> commit.** El repo es su memoria. Por eso necesita disciplina para escribirla
> bien y mantenerla limpia.

---

## 1. Memoria en tres capas

Pacho organiza su memoria como un sistema de tres niveles, de lo más crudo a lo
más estable:

| Capa | Archivo(s) | Qué guarda | Cómo cambia |
| :--- | :--------- | :--------- | :---------- |
| **1. Trabajo** (cruda) | `memoria/bitacora/AAAA-MM-DD.md` | Lo que pasó hoy: qué hizo Pacho, qué dijo Silvana, observaciones del día. | Append-only. Se escribe todo el día. Es desechable a mediano plazo. |
| **2. Curada** (temática) | `memoria/personas.md`, `memoria/proyectos.md`, `memoria/preferencias.md` | Conocimiento útil para más de una sesión: contactos, proyectos activos, reglas aprendidas. | Se actualiza cuando algo durable aparece. Se mantiene ordenada. |
| **3. Estable** (identidad) | `memoria/perfil.md` | Lo que casi nunca cambia: quién es Silvana, su contexto fijo, sus no-negociables. | Cambia poco. Es lo primero que Pacho lee siempre. |

**El flujo natural de la información es de abajo hacia arriba:** algo aparece en
la bitácora (capa 1) → si resulta durable, Pacho lo **promueve** a un archivo
temático (capa 2) → si resulta fundamental y estable, sube al perfil (capa 3).

```
   día a día          se promueve si           se promueve si
   (efímero)          es durable               es fundamental
 ┌────────────┐   ┌────────────────────┐   ┌──────────────┐
 │  bitácora  │ → │ personas/proyectos │ → │   perfil     │
 │  (capa 1)  │   │ preferencias (c.2) │   │   (capa 3)   │
 └────────────┘   └────────────────────┘   └──────────────┘
```

---

## 2. Estructura de archivos

```
memoria/
├── perfil.md            # Capa 3 — identidad y contexto fijo de Silvana
├── preferencias.md      # Capa 2 — reglas de comportamiento aprendidas
├── personas.md          # Capa 2 — contactos clave (un bloque por persona)
├── proyectos.md         # Capa 2 — temas/proyectos activos (un bloque c/u)
├── indice.md            # Mapa: qué hay en cada archivo (orientación rápida)
├── bitacora/
│   ├── 2026-06-13.md    # Capa 1 — log del día (append-only)
│   └── ...
└── archivo/             # Lo cerrado/obsoleto que ya no es activo pero se guarda
    └── proyectos-cerrados.md
```

Reglas de los archivos:

- **Cada archivo empieza con un encabezado:** propósito + fecha de última
  actualización. Ejemplo: `<!-- Última actualización: 2026-06-13 -->`.
- **Formato consistente por archivo** (ver plantillas en §6).
- **Estado arriba, detalle abajo:** cada bloque arranca con su estado actual en
  1–2 líneas; el historial va después. Así Pacho lee lo importante primero.
- **Tamaño manejable:** si un archivo temático pasa de ~400–500 líneas o se
  vuelve difícil de leer, se divide (ej. `proyectos.md` → carpeta `proyectos/`
  con un archivo por proyecto).
- **Nunca secretos:** ni contraseñas, ni tokens, ni datos sensibles (números de
  documento, tarjetas). La memoria es contexto, no una caja fuerte.

---

## 3. Qué se captura y qué no (reglas de captura)

La pregunta que Pacho se hace ante cualquier dato nuevo: **"¿voy a necesitar esto
en una sesión futura?"**

| Tipo de dato | ¿Va a memoria? | Dónde |
| :----------- | :------------- | :---- |
| Preferencia estable de Silvana ("correos cortos", "no agendar antes de 9") | ✅ Sí | `preferencias.md` |
| Hecho sobre una persona (rol, cómo tratarla, contexto) | ✅ Sí | `personas.md` |
| Estado o decisión de un proyecto | ✅ Sí | `proyectos.md` |
| Algo fundamental e identitario de Silvana | ✅ Sí | `perfil.md` |
| Qué hizo Pacho hoy / contexto del día | ✅ Sí, pero efímero | `bitacora/` |
| Detalle de una tarea puntual que no se repite | ❌ No (o solo bitácora) | — |
| Información que cambia cada día (clima, una cifra de hoy) | ❌ No | — |
| Algo que Silvana pidió mantener en privado / olvidar | ❌ Nunca | — |

**Regla de oro de captura:** ante la duda, anótalo en la **bitácora** (capa 1).
La consolidación posterior (§5) decide si merece subir a un archivo temático.
Así nada importante se pierde, pero los archivos curados no se ensucian.

---

## 4. Protocolo durante la sesión (escritura en caliente)

Cada vez que Pacho trabaja:

**Al empezar (lectura):**
1. Lee siempre `memoria/perfil.md` y `memoria/preferencias.md` (son cortos).
2. Según la tarea, lee **solo el bloque relevante** de `personas.md` o
   `proyectos.md` (no todo el archivo). Usa `indice.md` para ubicarse.
3. Si la tarea continúa algo reciente, ojea la última entrada de `bitacora/`.

**Durante (captura):**
4. Cuando aparece algo durable, lo escribe en el archivo temático correcto, en el
   formato de ese archivo, y actualiza la fecha del encabezado.
5. **Si el dato nuevo contradice uno viejo:** reemplaza el viejo, no acumula los
   dos. Anota el cambio en la bitácora del día ("actualicé X: antes Y, ahora Z").
6. Toda acción o aprendizaje relevante → una línea en `bitacora/AAAA-MM-DD.md`.

**Al cerrar (commit):**
7. Hace **commit** de los cambios de `memoria/` con un mensaje claro
   (ej. `memoria: actualizo estado del proyecto X y preferencia de horarios`).
   Sin commit, la memoria no sobrevive a la sesión.

---

## 5. Mantenimiento y optimización (el proceso periódico)

Esto es lo que evita que la memoria se degrade. Pacho corre una **rutina de
mantenimiento** (recomendado: semanal, p. ej. domingos por la noche, vía
`/schedule`; ver §9 del documento de setup). El comando dedicado es
`/memoria-mantenimiento` (definido en §7).

En cada mantenimiento, Pacho hace **siete pasos en orden**:

1. **Consolidar (promover):** lee las bitácoras de la semana, extrae lo durable y
   lo mueve a su archivo temático. La bitácora es memoria de trabajo; lo que
   importa de verdad debe vivir en la capa curada.
2. **Deduplicar:** busca información repetida dentro de un archivo o entre
   archivos, y la unifica en un solo lugar.
3. **Resolver conflictos:** si hay datos contradictorios, se queda con el más
   reciente/correcto y elimina el obsoleto.
4. **Podar y archivar:** lo que ya no está activo (proyectos cerrados, personas
   que dejaron de ser relevantes) se mueve a `memoria/archivo/`. No se borra
   —se archiva— por si hace falta después.
5. **Reorganizar:** si un archivo creció demasiado, lo divide; si una sección
   quedó desordenada, la reestructura. Mantiene "estado arriba, detalle abajo".
6. **Resumir:** comprime historial viejo en resúmenes. Mantiene cada bloque
   legible: lo vigente claro, lo antiguo condensado.
7. **Reindexar y commit:** actualiza `memoria/indice.md` para reflejar la
   estructura real, y hace un commit con un resumen de qué cambió en el
   mantenimiento.

**Higiene de bitácoras:** una vez consolidada, una bitácora vieja (p. ej. de
más de 30–60 días) puede resumirse en una línea o archivarse. Lo importante ya
subió a la capa curada; la bitácora cruda no necesita conservarse para siempre.

> **Principio de fondo:** la memoria de Pacho es un jardín, no un depósito. El
> mantenimiento semanal es la poda. Sin poda, en tres meses los archivos serían
> un basurero ilegible y Pacho se volvería lento y confuso. Con poda, la memoria
> se mantiene chica, vigente y útil — y Pacho se vuelve **más** afilado con el
> tiempo, no menos.

---

## 6. Plantillas de los archivos

**`memoria/perfil.md`**
```markdown
<!-- Última actualización: AAAA-MM-DD -->
# Perfil de Silvana

## Quién es
(rol, ocupación, contexto de vida en 2–4 líneas)

## Contexto fijo
- (cosas que casi nunca cambian)

## No-negociables
- (horarios protegidos, días libres, límites duros)
```

**`memoria/preferencias.md`**
```markdown
<!-- Última actualización: AAAA-MM-DD -->
# Preferencias aprendidas

## Comunicación
- (ej.: "respuestas cortas", "sin emojis en correos de trabajo")

## Agenda
- (ej.: "no agendar antes de las 9", "viernes PM libre")

## Correo / tareas
- (reglas que Silvana fue pidiendo)
```

**`memoria/personas.md`** (un bloque por persona)
```markdown
<!-- Última actualización: AAAA-MM-DD -->
# Personas clave

## [Nombre] — [rol/relación]
- **Estado:** (relación actual / contexto vigente en 1 línea)
- Cómo tratar: (tono, prioridad, qué le importa)
- Contexto: (historial relevante, condensado)
```

**`memoria/proyectos.md`** (un bloque por proyecto)
```markdown
<!-- Última actualización: AAAA-MM-DD -->
# Proyectos / temas activos

## [Proyecto]
- **Estado:** (dónde va, en 1 línea)
- Objetivo: (qué se busca)
- Próximos pasos: (lo siguiente concreto)
- Notas: (links, decisiones, condensado)
```

**`memoria/bitacora/AAAA-MM-DD.md`**
```markdown
# Bitácora — AAAA-MM-DD

- HH:MM — (qué hizo Pacho / qué pasó / qué aprendió)
- HH:MM — ...
```

---

## 7. Wiring: cómo se instaura esto en el repo de Pacho

Para que esto no sea solo "buena intención" sino algo que Pacho **ejecuta**:

1. **En el `CLAUDE.md`** va la versión corta del protocolo (capas, lectura al
   empezar, escritura + commit, captura). Es lo que Pacho lee en cada sesión.
   Ya está incluido en la plantilla del documento de setup (§6).

2. **Comando `/memoria-mantenimiento`** en `.claude/commands/memoria-mantenimiento.md`,
   con los 7 pasos de §5. Ejemplo de contenido:
   ```markdown
   ---
   description: Consolida, depura y reorganiza la memoria de Pacho
   ---
   Ejecuta el mantenimiento de memoria siguiendo memoria/03 (los 7 pasos):
   consolidar, deduplicar, resolver conflictos, podar/archivar, reorganizar,
   resumir, reindexar. Lee las bitácoras desde el último mantenimiento, promueve
   lo durable a los archivos temáticos, y haz commit con un resumen de cambios.
   ```

3. **Rutina programada** (semanal) que llama a ese comando, vía `/schedule`
   (ver §9 del documento de setup).

4. **Commit disciplinado:** la regla "si lo aprendiste, escríbelo y haz commit"
   vive en el `CLAUDE.md`. Sin commit, no hay memoria.

---

## 8. Resumen en una frase

> La bitácora captura todo en crudo; durante la sesión Pacho promueve lo durable
> a archivos temáticos y hace commit; y una vez por semana consolida, depura,
> poda y reorganiza para que la memoria se mantenga **chica, vigente y útil**.
> Eso es lo que hace que Pacho mejore con el tiempo.
