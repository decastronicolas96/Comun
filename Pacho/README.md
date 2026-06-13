# 🐎 Pacho — Asistente personal de Silvana

Pacho es un asistente personal construido sobre **Claude Code en la web**, conectado
a GitHub y a las herramientas que Silvana usa todos los días (correo, calendario,
notas, tareas, documentos). Es eficiente, pragmático y directo: hace el trabajo,
no da vueltas, y pregunta solo cuando algo es irreversible o ambiguo.

Este folder contiene todo lo necesario para montarlo.

## Contenido

| Archivo | Para qué sirve |
| :------ | :------------- |
| [`01_Requerimientos_Setup_Pacho.md`](01_Requerimientos_Setup_Pacho.md) | Documento de requerimientos: cuentas, pasos exactos de instalación, estructura del repositorio, plantilla de personalidad y checklist de verificación. |
| [`02_Preguntas_para_Silvana.md`](02_Preguntas_para_Silvana.md) | Cuestionario para Silvana. Sus respuestas definen qué herramientas conectar, qué rutinas automatizar y cómo debe comportarse Pacho. **Responder esto antes de hacer el setup final.** |

## Orden recomendado

1. **Silvana responde** el cuestionario (`02_Preguntas_para_Silvana.md`).
2. Con esas respuestas, se completa el setup siguiendo `01_Requerimientos_Setup_Pacho.md`.
3. Se prueba con un par de tareas reales y se ajusta el `CLAUDE.md` de Pacho.

> El setup base toma ~30–45 min. Conectar integraciones y afinar la personalidad
> es iterativo: Pacho mejora a medida que Silvana lo usa y le va diciendo qué
> quiere distinto.
