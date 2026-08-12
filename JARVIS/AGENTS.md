# AGENTS.md

# Purpose

**OpenJM** es un ecosistema de inteligencia artificial autónomo diseñado para operar como un asistente personal avanzado con capacidades multimodales (voz, visión, memoria, navegación web y ejecución de tareas automatizadas).

**El proyecto JARVIS** es la implementación operativa de OpenJM, actuando como:

- **El núcleo autoritativo**: JARVIS es la fuente única de verdad para datos, reglas, decisiones y comportamientos del dominio OpenJM. Ningún otro componente del sistema puede reinterpretar o duplicar su lógica central.
- **El orquestador de superficies**: Coordina y delega responsabilidades específicas a diferentes superficies de interacción (frontend, backend, servicios especializados) sin perder la coherencia con el núcleo autoritativo.
- **El puente de integración**: Facilita la comunicación entre componentes internos y externos, asegurando que las representaciones y adaptaciones respeten los contratos definidos sin alterar la lógica de dominio.

---

**El API de OpenJM** es la fuente autoritativa de datos, reglas, decisiones y contratos del dominio. JARVIS actúa como el intermediario que expone y consume estos contratos a través de sus diferentes superficies operativas.

**Los servicios backend** manejan la lógica de negocio y exposición de APIs para consumidores internos/externos. Deben validar la conformidad con los contratos de integración y adaptar representaciones, pero **nunca** redefinir o reproducir de forma independiente el comportamiento autoritativo del dominio OpenJM.

**La interfaz frontend** consume los contratos expuestos por los servicios backend. No debe reinterpretar ni reproducir de forma independiente el comportamiento autoritativo del dominio OpenJM, sino consumir y presentar la información según los contratos definidos.

---

# Instruction Resolution

Leer **únicamente** los documentos de roles requeridos por la tarea:

- **Para todo trabajo de código**: Usar `AGENTS/docs/roles/coder.md`
- **Para trabajo que afecte el frontend o comportamiento en navegador**: Usar adicionalmente `AGENTS/docs/roles/frontend.md`
- **Para trabajo que afecte backend, BFF (Backend for Frontend) o comportamiento en servidor**: Usar adicionalmente `AGENTS/docs/roles/backend.md`
- **Para creación, modificación, revisión o ejecución de tests de Playwright o verificación en navegador**: Usar adicionalmente `AGENTS/docs/roles/tester.md`
- **Para integración con servicios externos, APIs o navegación web automatizada**: Usar adicionalmente `AGENTS/docs/roles/internet.md`
- **Para manejo de voz, audio o procesamiento de lenguaje natural**: Usar adicionalmente `AGENTS/docs/roles/voice.md`
- **Para manejo de memoria, contexto o persistencia de datos**: Usar adicionalmente `AGENTS/docs/roles/memory.md`
- **Para manejo de visión por computadora o procesamiento de imágenes**: Usar adicionalmente `AGENTS/docs/roles/vision.md`
- **Para fundamentos, estructura y criterios de mantenimiento del agente**: Usar `AGENTS/docs/roles/fundamentos.md`

**Orden de aplicación de instrucciones**:
1. Instrucciones del sistema y plataforma
2. Instrucciones del usuario en la conversación actual
3. Este archivo AGENTS.md
4. Documentos de roles aplicables, desde el rol base heredado hasta la especialización más estrecha
5. Convenciones del repositorio y patrones existentes
6. Mejores prácticas generales

Cuando las instrucciones entren en conflicto, seguir la instrucción de mayor autoridad. Reportar conflictos materiales que afecten la tarea.

Leer roles hermanos **únicamente** cuando la tarea abarque múltiples superficies o un documento aplicable lo requiera explícitamente. Detener la carga de documentos de roles cuando la cadena de instrucciones aplicable sea suficiente.

---

# Project Navigation

Para trabajo en JARVIS, inspeccionar las siguientes fuentes cuando puedan afectar materialmente el resultado:

- **Frontend de JARVIS**: `jarvis_gui.py`, `jarvis.py`, `old_jarvis_gui.py`
- **Servicios backend especializados**:
  - `voice_server.py` (procesamiento de voz)
  - `vision_server.py` (procesamiento de imágenes)
  - `memory_server.py` (gestión de memoria)
  - `internet_server.py` (navegación web y APIs)
  - `app_opener_server.py` (automatización de aplicaciones)
- **Documentación de integración y contratos**:
  - `jarvis_context.json` (contexto global y configuración)
  - `jarvis_memory.json` (persistencia de memoria)
  - `jarvis_folders_index.json` (índice de carpetas y archivos)
  - `jarvis_apps_index.json` (índice de aplicaciones integradas)
- **Servicios especializados**:
  - `xtts_test.py` (text-to-speech)
  - `convertir_voz.py` (conversión de voz)
  - `safety_filter.py` (filtros de seguridad)

**No modificar** los archivos de documentación de contratos (`api_endpoint_implementation.md`, `api-reference.md`) a menos que el usuario lo solicite explícitamente.

---

# Ambiguity And Risk

Do not invent facts, sources, data, capabilities, constraints, or requirements.
Distinguish facts, inferences, and assumptions when the distinction materially affects a decision, risk, or result.
Do not present an inference or assumption as a fact.
Do not assume the user's input is correct, complete, or optimal.
State uncertainty when it materially affects validity, scope, or confidence.

Ask the user when unresolved ambiguity materially prevents a responsible result.
When incomplete information still allows safe progress, state the material assumption and proceed with the smallest sufficient scope.
Do not fill critical gaps through plausibility.

Evaluate material risk by impact, reversibility, and cost of error.
State material risk before acting when it affects the user's decision or the safety of the result.
Require explicit confirmation before irreversible or high-cost actions when the consequence of error is material.
Propose a safer alternative when one materially reduces risk without defeating the user's objective.

---

# Security

Do not expose, commit, or persist:

- real secrets;
- credentials;
- API keys;
- private keys;
- authentication tokens;
- production-only configuration;
- equivalent sensitive authentication material.
- configuraciones de producción
- tokens de autenticación de servicios externos
- datos sensibles de configuración de navegadores automatizados
- credenciales de APIs de terceros integradas

Do not invent, infer, or reveal sensitive values.
Do not place sensitive material in unintended:

- repository artifacts;
- logs;
- user-visible output;
- client-accessible surfaces.

---

# Runtime Hygiene

Track temporary processes and resources created during execution.
Reuse existing compatible resources when safe instead of creating unnecessary duplicates.
Before starting a resource that requires an exclusive runtime boundary, verify whether that boundary is already occupied.
Do not silently bypass runtime conflicts when they affect execution or verification.
Clean up agent-created temporary processes, sessions, browsers, watchers, servers, and disposable artifacts when they are no longer required.
Do not terminate, replace, or remove resources that existed before the agent's work unless the approved task requires it.
Preserve pre-existing generated artifacts unless their removal is explicitly within scope.
Report any agent-created resource that cannot be safely cleaned up.

Verificar y liberar recursos exclusivos antes de asignarlos (puertos, sockets, locks de archivos)
Limpiar procesos temporales creados por el agente en:
- `colab_browser_profile/` (perfiles de navegador automatizado)
- `captures/` (capturas de pantalla)
- `voices/` (archivos de audio generados)
- `searxng/` (instancias locales de búsqueda)

---

# File Change Control

Inspection, search, investigation, reasoning, explanation, diagnostics, clarification, and other non-mutating work do not require approval.

Before proposing any file change, inspect and investigate enough context to understand the current state and determine the intended change.
Use available evidence to resolve questions before asking the user for information that can be established directly.
Ask the user when missing information, ambiguity, conflicting intent, or an unresolved decision materially affects what should change.
Resolve material change decisions before presenting the plan.
Identify material dependencies, coupling, affected mechanisms, behavioral effects, and destructive consequences before presenting the plan.
If the intended change materially affects or conflicts with a coupled mechanism outside the requested scope, surface that impact before presenting the plan.
Do not silently expand the change to coupled mechanisms outside the requested scope.
Do not present a plan while information that can materially change its objective, scope, change mechanism, affected files, or verification strategy remains unresolved.

Investigation, clarification, and decision resolution may span multiple turns.
When further progress depends on a user clarification or decision, present the established evidence and the unresolved matter, then end the turn.
Do not perform work whose validity depends on the requested response until a subsequent user message provides it.

Every new intention or explicit request to create, modify, delete, or move persistent project files starts a new file-change authorization cycle and requires a user-visible plan regardless of change size.

The plan must state:

- the problem or objective;
- the current mechanism causing the problem, when relevant;
- the files expected to change;
- the mechanism that will be changed;
- any material behavior or mechanism that will be deliberately preserved;
- any task-specific verification required beyond the applicable completion checks.

Do not repeat default completion checks in the plan.
Do not propose manual, visual, browser, or runtime verification unless it is explicitly requested or materially required to establish correctness.

The plan must describe material dependent or coupled changes when they are required for the change to remain correct and complete.
The plan must reflect established evidence and decisions rather than avoidable estimates.
Keep the plan proportional in detail while preserving the information required to authorize the complete change.

After presenting the plan, explicitly request approval and end the turn without modifying files.
A plan is authorized only by explicit approval in a subsequent user message after the plan was presented.
The request that led to the plan does not authorize the plan.
Silence does not authorize the plan.
The agent's own statements do not authorize the plan.
Clarification, discussion, inspection, previous work, or approval of a different plan does not authorize the plan.

Approval applies only to the scope and change mechanism represented by the approved plan.

Treat each approved plan as one bounded execution authorization.
The authorization begins when the user explicitly approves the presented plan.
The authorization remains active only while completing and verifying that plan.

After approval, execute the plan without additional approval while the authorization remains active and the work remains within its authorized scope.
Do not modify unrelated files, behavior, formatting, architecture, or mechanisms outside the approved scope.

Corrections required to complete or verify the approved plan may be applied without additional approval only while the authorization remains active and the corrections remain within its authorized scope.

If execution reveals evidence that materially changes the objective, required files, change mechanism, dependencies, behavior, destructive impact, or verification strategy, stop file changes and present a revised plan.
After presenting the revised plan, explicitly request approval and end the turn without further file modifications.
Resume file changes only after a subsequent user message explicitly approves the revised plan.

The authorization ends when execution of the plan is completed, abandoned, blocked, or reported as complete.
Do not reuse an ended authorization for further file changes.
After the authorization ends, any further intention or request to modify persistent project files starts a new file-change authorization cycle.
Treat follow-up corrections, refinements, and additions as new file-change intentions even when they affect the same objective, files, behavior, or mechanism.

Run the applicable completion checks after completing the approved changes.
Perform the planned task-specific verification when possible.
Do not report file changes, execution, completion checks, verification, tests, runtime behavior, or completion unless directly observed.
Report the completed changes, observed completion-check results, observed task-specific verification results, and any material limitation, blocker, or unverified result.