# Fundamentos y Estructura de JARVIS

## Propósito

Este documento define los principios fundamentales, responsabilidades y criterios de mantenimiento para el agente JARVIS. Su objetivo es mantener la coherencia arquitectónica, garantizar la estabilidad operativa y proporcionar una guía clara para el desarrollo continuo del proyecto.

---

## Principios Fundamentales

### 1. **Núcleo Autoritativo**
JARVIS actúa como la única fuente de verdad para:
- Datos del dominio OpenJM
- Reglas y decisiones operativas
- Contratos de integración y APIs
- Comportamientos autoritativos

**Regla de Oro**: Ningún otro componente puede reinterpretar o duplicar la lógica central definida en el núcleo.

### 2. **Separación de Responsabilidades**
Cada superficie de interacción tiene un ámbito claramente definido:

| Superficie | Responsabilidad Principal | Alcance |
|------------|--------------------------|---------|
| **Frontend** | Consumir contratos del backend y presentar información | Interfaz de usuario y experiencia de usuario |
| **Backend** | Validar contratos y exponer APIs para consumidores | Lógica de negocio y exposición de servicios |
| **Servicios Especializados** | Implementar funcionalidades específicas | Voz, visión, memoria, navegación, automatización |
| **Núcleo Autoritativo** | Definir reglas y datos centrales | Configuración global y persistencia |

### 3. **Contratos como Contrato Social**
Todos los componentes deben:
- Cumplir estrictamente los contratos definidos en `jarvis_context.json`
- Validar la conformidad con las APIs y servicios
- Adaptar representaciones sin alterar la lógica autoritativa
- Documentar cualquier desviación o ampliación de contrato

---

## Responsabilidades por Área

### 🔹 **Núcleo Autoritativo (Core)**
**Ubicación**: `jarvis_context.json`, `jarvis_memory.json`

**Responsabilidades**:
- Definir la configuración global del sistema
- Mantener el estado persistente de memoria y contexto
- Validar que todos los componentes cumplan con los contratos
- Proporcionar puntos de extensión seguros para nuevos servicios

**Principios de Operación**:
- **Inmutabilidad**: Los datos centrales no se modifican directamente
- **Validación**: Todos los cambios deben pasar por validación de contrato
- **Persistencia**: La memoria se actualiza de forma atómica y recuperable
- **Extensibilidad**: Nuevos servicios deben integrarse sin modificar el núcleo

---

### 🔹 **Frontend**
**Ubicación**: `jarvis_gui.py`, `old_jarvis_gui.py`

**Responsabilidades**:
- Consumir los contratos expuestos por el backend
- Presentar información al usuario de forma clara y consistente
- Recopilar entradas del usuario y validarlas contra contratos
- Notificar al usuario sobre el estado del sistema y posibles acciones

**Principios de Operación**:
- **Consumo de APIs**: Solo debe consumir endpoints documentados en `jarvis_context.json`
- **Validación de Entradas**: Validar todas las entradas del usuario antes de procesarlas
- **Feedback Visual**: Proporcionar retroalimentación clara sobre el estado de las operaciones
- **Separación de Preocupaciones**: No debe contener lógica de negocio autoritativa

---

### 🔹 **Backend y Servicios Especializados**
**Ubicaciones**:
- Backend general: `jarvis.py`
- Voz: `voice_server.py`, `xtts_test.py`, `convertir_voz.py`
- Visión: `vision_server.py`
- Memoria: `memory_server.py`
- Internet: `internet_server.py`
- Automatización: `app_opener_server.py`

**Responsabilidades**:
- Validar la conformidad con los contratos de integración
- Adaptar representaciones para consumidores (frontend, APIs externas)
- Implementar la lógica de negocio específica de cada dominio
- Gestionar recursos y conexiones de forma segura

**Principios de Operación**:
- **Validación de Contratos**: Todos los servicios deben validar entradas y salidas contra los contratos definidos
- **Seguridad de Recursos**: Gestionar adecuadamente conexiones, archivos temporales y sesiones
- **Recuperación ante Fallos**: Implementar manejo de errores y recuperación para operaciones críticas
- **Documentación de APIs**: Documentar todos los endpoints y contratos en `jarvis_context.json`

---

## Criterios de Mantenimiento

### ✅ **Coherencia del Núcleo Autoritativo**
- **Hacer**:
  - Validar que todos los componentes consuman el núcleo sin reinterpretar lógica
  - Actualizar `jarvis_context.json` cuando se añadan nuevos servicios o APIs
  - Mantener `jarvis_memory.json` actualizado y consistente
  - Documentar cualquier cambio en contratos en los archivos correspondientes

- **Evitar**:
  - Duplicar comportamientos de negocio en múltiples superficies
  - Modificar directamente datos en el núcleo sin pasar por validación
  - Ignorar contratos definidos para nuevos servicios

- **Verificar**:
  - Que los contratos en `jarvis_context.json` reflejen la implementación real
  - Que todos los servicios especializados cumplan con sus contratos
  - Que la memoria persistente (`jarvis_memory.json`) sea consistente con el estado del sistema

### ✅ **Aislamiento de Responsabilidades**
- Cada servicio especializado debe tener un ámbito claro y documentado
- Los cambios en un servicio no deben afectar la coherencia de otros componentes
- Las dependencias deben ser explícitas y minimizadas
- Implementar interfaces bien definidas entre componentes

### ✅ **Documentación y Contexto**
- **Archivos críticos a mantener actualizados**:
  - `jarvis_context.json` (configuración global y contratos)
  - `jarvis_memory.json` (persistencia de memoria)
  - `jarvis_folders_index.json` (índice de carpetas y archivos)
  - `jarvis_apps_index.json` (índice de aplicaciones integradas)
  - Documentación de APIs en `AGENTS/docs/`

- **Buenas prácticas de documentación**:
  - Documentar decisiones arquitectónicas en los archivos correspondientes
  - Mantener un changelog de cambios significativos en contratos
  - Documentar dependencias entre servicios
  - Incluir ejemplos de uso en la documentación de APIs

### ✅ **Seguridad Operativa**
- **Auditorías periódicas**:
  - Credenciales en archivos de configuración
  - Tokens de APIs externas
  - Permisos de archivos y directorios
  - Configuraciones de seguridad en navegadores automatizados

- **Filtros y protecciones**:
  - Implementar `safety_filter.py` para validar entradas y salidas
  - Validar que los servicios no expongan datos sensibles
  - Limitar el acceso a recursos críticos

### ✅ **Optimización Continua**
- **Revisión periódica**:
  - Rendimiento de servicios especializados
  - Consumo de recursos (CPU, memoria, red)
  - Tiempos de respuesta en interacciones con el usuario
  - Eficiencia de algoritmos y procesos

- **Actualización de dependencias**:
  - Mantener actualizadas las bibliotecas y frameworks
  - Evaluar nuevas versiones de componentes críticos
  - Probar cambios en entornos controlados antes de implementar

### ✅ **Verificación y Pruebas**
- **Tests automatizados**:
  - Contratos de APIs
  - Integración entre servicios
  - Procesamiento de voz, visión y memoria
  - Manejo de errores y recuperación

- **Verificación manual**:
  - Coherencia de datos entre componentes
  - Funcionalidad de interfaces de usuario
  - Comportamiento en escenarios de borde

---

## Flujo de Trabajo Recomendado

### 📋 **Para solicitudes de cambios**

1. **Identificar el componente afectado**:
   - ¿Es un cambio en el frontend, backend, un servicio especializado o el núcleo?
   - Consultar el documento de roles correspondiente

2. **Analizar el impacto**:
   - ¿Afecta a contratos existentes?
   - ¿Requiere cambios en otros componentes?
   - ¿Modifica la configuración global?

3. **Planificar el cambio**:
   - Definir el alcance exacto del cambio
   - Identificar dependencias y acoplamientos
   - Planificar pruebas de verificación

4. **Implementar y validar**:
   - Realizar el cambio según el plan
   - Validar que no se rompan contratos existentes
   - Verificar que el cambio cumple con su objetivo

5. **Documentar y actualizar**:
   - Actualizar la documentación afectada
   - Registrar el cambio en el historial correspondiente
   - Notificar a los usuarios relevantes

### 🔧 **Para integraciones nuevas**

1. **Definir el contrato**:
   - ¿Qué datos y funcionalidades necesita el nuevo servicio?
   - ¿Cómo se integrará con el núcleo autoritativo?
   - Documentar en `jarvis_context.json`

2. **Implementar el servicio**:
   - Crear el nuevo servicio especializado
   - Implementar la lógica de negocio específica
   - Validar contra los contratos definidos

3. **Documentar la integración**:
   - Actualizar índices relevantes (`jarvis_apps_index.json`, `jarvis_folders_index.json`)
   - Documentar en `AGENTS/docs/roles/[servicio]_md`
   - Incluir ejemplos de uso

4. **Implementar pruebas**:
   - Tests unitarios para la nueva funcionalidad
   - Tests de integración con otros servicios
   - Pruebas de recuperación ante fallos

### 🔄 **Para mantenimiento preventivo**

1. **Revisión de configuración**:
   - Auditar `jarvis_context.json` y `jarvis_memory.json`
   - Limpiar datos obsoletos en memoria persistente
   - Validar que todos los contratos sean consistentes

2. **Optimización de recursos**:
   - Revisar el consumo de CPU, memoria y red
   - Optimizar procesos críticos
   - Limpiar archivos temporales y recursos huérfanos

3. **Actualización de dependencias**:
   - Revisar versiones de bibliotecas y frameworks
   - Probar actualizaciones en entornos controlados
   - Implementar cambios en producción de forma gradual

4. **Verificación de seguridad**:
   - Auditar permisos y accesos
   - Revisar filtros de seguridad
   - Validar que no haya fugas de información sensible

---

## Buenas Prácticas

### 🎯 **Separación de Preocupaciones**
- Cada componente debe tener una única responsabilidad clara
- Los servicios deben ser independientes y desacoplados
- Las dependencias deben ser explícitas y documentadas

### 📋 **Contratos Explícitos**
- Todas las APIs y servicios deben definir contratos claros
- Los contratos deben estar documentados y versionados
- Las entradas y salidas deben ser validadas estrictamente

### 🔗 **Minimizar Acoplamiento**
- Las dependencias entre componentes deben ser mínimas
- Utilizar interfaces bien definidas para la comunicación
- Implementar patrones de diseño que promuevan el desacoplamiento

### 🔒 **Seguridad por Diseño**
- Implementar seguridad en cada capa desde el inicio
- Validar todas las entradas y salidas
- Proteger datos sensibles y credenciales
- Implementar filtros y protecciones en puntos de entrada

### 📖 **Documentación Viva**
- Mantener la documentación actualizada con cada cambio significativo
- Documentar decisiones arquitectónicas y su justificación
- Incluir ejemplos prácticos y casos de uso
- Mantener un historial de cambios en la documentación

### 🧪 **Pruebas Automatizadas**
- Validar cambios con tests antes de implementar en producción
- Implementar pruebas unitarias, de integración y de sistema
- Verificar que los contratos se cumplan en todas las pruebas
- Incluir pruebas de recuperación ante fallos

### 🔄 **Mejora Continua**
- Revisar periódicamente el rendimiento y la eficiencia
- Actualizar dependencias y optimizar código
- Implementar nuevas tecnologías y mejores prácticas
- Aprender de los incidentes y errores para mejorar el sistema

---

## Estructura de Archivos Recomendada

```
AGENTS/
├── docs/
│   ├── roles/
│   │   ├── coder.md          # Guía para trabajo de código
│   │   ├── frontend.md        # Guía para trabajo frontend
│   │   ├── backend.md         # Guía para trabajo backend
│   │   ├── tester.md          # Guía para pruebas y verificación
│   │   ├── internet.md        # Guía para integración con APIs
│   │   ├── voice.md           # Guía para procesamiento de voz
│   │   ├── memory.md          # Guía para manejo de memoria
│   │   ├── vision.md          # Guía para procesamiento de imágenes
│   │   └── fundamentos.md     # Este documento
│   └── AGENTS.md             # Políticas raíz
└── ...
```

---

## Gobernanza y Toma de Decisiones

### 🏛️ **Jerarquía de Autoridad**
1. **AGENTS.md** (Políticas raíz)
2. **Documentos de roles** (Reglas específicas por superficie)
3. **Contratos definidos** (`jarvis_context.json`)
4. **Implementación** (Código y servicios)

### ⚖️ **Resolución de Conflictos**
- Los conflictos entre documentos se resuelven siguiendo la jerarquía de autoridad
- Si un conflicto afecta a contratos o al núcleo autoritativo, se requiere aprobación explícita del usuario
- Los conflictos en implementaciones específicas se resuelven según los principios definidos en los documentos de roles

### 📊 **Métricas de Éxito**
- **Coherencia**: Todos los componentes cumplen con los contratos definidos
- **Estabilidad**: El sistema opera sin errores críticos durante largos períodos
- **Mantenibilidad**: Los cambios se implementan y despliegan sin romper funcionalidades existentes
- **Seguridad**: No hay incidentes de seguridad o fugas de datos
- **Rendimiento**: El sistema opera dentro de los parámetros de rendimiento definidos

---

## Conclusión

JARVIS es un sistema complejo que requiere una estructura clara, documentación precisa y una gobernanza estricta para mantener su estabilidad y coherencia. Este documento, junto con los documentos de roles específicos, proporciona el marco necesario para operar, mantener y evolucionar el sistema de manera efectiva.

**Recuerda**: La clave del éxito está en seguir los principios definidos, mantener la documentación actualizada y validar cada cambio contra los contratos establecidos.
