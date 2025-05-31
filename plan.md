# Informe Detallado: Transformación de agente_plantilla a Enjambre de Agentes con Intervención del Master y Orquestador Conversacional

## Objetivo

Adaptar la estructura mono-agente de agente_plantilla para crear un sistema de enjambre multi-agente orquestado asíncronamente, con gestión de contexto individual, uso estandarizado de herramientas (consola como principal), logging en base de datos, y capacidades de comunicación bidireccional. El Agente Master servirá como el principal punto de contacto conversacional para el usuario, manejando la interacción directa (a través de la mediación de main.py), supervisando el estado de los agentes del enjambre, recibiendo reportes de problemas, y enviando mensajes para intervenir o reanudar la ejecución.

## Punto de Partida

El repositorio agente_plantilla proporciona una excelente base en su estructura (servicios/, agentes/, prompts/), la clase Agente con gestión de historial LangChain, y servicios placeholders.

## Componentes de la Arquitectura Final (Actualizada y Enfocada en la Interacción)

### main.py

Manejador de Interfaz de Usuario y Ejecutor de Acciones del Master. Es la capa más externa que interactúa con la consola del usuario (lee input, imprime output). Recibe las acciones solicitadas por el Agente Master (Tool Calls) y las ejecuta (llamando a gestor_enjambre). Recibe el texto de respuesta generado por el Agente Master y lo muestra al usuario. Monitorea el estado general del enjambre.

### agentes/clase_agente.py

Clase base para un agente individual del enjambre. Contenedor de estado: nombre, rol, objetivo, instancia del LLM, y su historial de conversación (contexto).

### servicios/cargar_llm.py

Servicio centralizado para la inicialización y configuración (incluyendo bindeo de herramientas) de las instancias del LLM (Gemini). Usado por el Master y cada Agente del Enjambre.

### servicios/ejecutor_consola.py

Servicio seguro (en la medida de lo posible) para ejecutar comandos en la consola del contenedor. Invocado por el bucle_logico_agente cuando un agente lo solicita via Tool Call.

### servicios/gestor_logs.py

Servicio centralizado para interactuar con la base de datos SQLite (data/swarm.db). Registra toda la actividad del sistema para depuración y auditoría.

### servicios/orquestador_master.py

Lógica Conversacional y de Orquestación del Agente Master. Interactúa con su propio LLM y contexto (historial de conversación CON el usuario y notificaciones del sistema). Recibe input del usuario (mediado por main.py). Recibe notificaciones del sistema (inyectadas en su historial por gestor_enjambre). Genera acciones (delegar, enviar mensaje) via Tool Calls Y genera texto de respuesta conversacional para el usuario. No ejecuta tareas ni habla directamente con otros agentes; su comunicación y acciones son interpretadas y ejecutadas por main.py y gestor_enjambre.

### servicios/gestor_enjambre.py

Gestor del Enjambre. Mantiene un registro de las instancias activas de los agentes del enjambre. Recibe solicitudes de lanzamiento (delegación) desde main.py. Recibe reportes de estado, resultados y problemas desde los bucle_logico_agente. Implementa la lógica para enviar mensajes a agentes específicos. Inyecta notificaciones (problemas, finalización de agentes) en el historial del Agente Master.

### servicios/bucle_logico_agente.py

Bucle de Ejecución para UN agente del enjambre. Contiene la lógica del ciclo: gestionar el historial, llamar al LLM (pasando el historial completo), procesar la respuesta (detectar Tool Calls o texto), llamar a servicios (ejecutor_consola), y reportar estado/problemas/resultados al gestor_enjambre.py (via Tool Calls interpretadas por sí mismo). Gestiona su propio estado (running, paused, completed, failed).

### prompts/

Archivos de prompts para Master y agentes del enjambre.

### prompts/tool_definitions.py

Archivo que define formalmente las herramientas para el Master y los agentes. Incluye herramientas de acción externa y herramientas para modelar la comunicación interna.

### agentes_json/

Archivos JSON con las definiciones configurables de los tipos de agente del enjambre.

### data/swarm.db

Archivo de la base de datos SQLite para el logging.

### docker/

Archivos para Docker.

## Pasos de Transformación (Re-Enfocados en la Interacción del Master)

### Paso 1 a 5 (Configuración, Servicios Base, Clase Agente, Herramientas, Bucle Lógico Agente)

Estos pasos permanecen conceptualmente similares a como los hemos definido, con las implementaciones ya corregidas para usar langchain_core.messages, Tool Calls, logging, y el estado de pausa/reanudación en el bucle lógico del agente. La clase Agente es un holder de estado. Los servicios cargar_llm, ejecutor_consola, gestor_logs son utilidades llamadas por otros componentes. Las herramientas se definen en tool_definitions.py y se bindean al LLM correspondiente.

### Paso 6: Implementar Gestor del Enjambre (Completado/Refinado)

servicios/gestor_enjambre.py: Implementado como el Gestor del Enjambre. Su principal cambio de enfoque es su rol más activo en reportar eventos significativos (finalización de agentes, problemas reportados). Lo hace inyectando mensajes especiales (ej: SystemMessage con un marcador) en el historial de conversación del Agente Master a través del método orquestador_master.add_message_to_history(). También maneja send_message_to_agent llamando al bucle lógico correspondiente. Sigue siendo llamado por main.py para lanzar agentes.

### Paso 7: Implementar Orquestador Master (El Conversador)

servicios/orquestador_master.py: Implementado como el motor conversacional y de orquestación del sistema.
Tiene su propio LLM y mantiene su historial de conversación con el usuario (mediado por main.py). Este historial también contendrá las notificaciones inyectadas por el GestorEnjambre.

#### Método clave process_input_and_events(input_from_user=None)

Este método es llamado por main.py.

Si input_from_user no es None, lo añade como un HumanMessage a su historial (esto es la voz del usuario).

Llama a su LLM con su historial COMPLETO (que ahora incluye la conversación con el usuario Y las notificaciones inyectadas).

Procesa la respuesta del LLM:

Captura el texto de respuesta (response_obj.content). Este texto está destinado a ser mostrado al usuario.

Busca Tool Calls (response_obj.additional_kwargs.get('tool_calls')). Estas son las acciones que el Master quiere que el sistema ejecute.

Retorna AMBOS: el texto de respuesta generado por el LLM (para el usuario) Y la lista de acciones solicitadas (Tool Calls).

#### add_message_to_history(message)

Método público llamado por GestorEnjambre para inyectar notificaciones (problemas de agentes, finalización, etc.) en el historial del Master. Estos mensajes deben estar formateados para que el LLM del Master los entienda como información del sistema sobre sus agentes.

Bindea herramientas delegate_task y send_message_to_agent a su LLM.

### Paso 8: Implementar Orquestación Principal (main.py - El Interfaz)

main.py: Implementado como el bucle principal que gestiona la interfaz de usuario y ejecuta las acciones del Master.

Inicializa todos los servicios (GestorLogs, ejecutor_consola, cargar_llm), GestorEnjambre, y OrquestadorMaster, manejando las referencias circulares.

Contiene un bucle while True principal que es el ciclo de vida del sistema.

Dentro del bucle:

Verifica si se necesita input del usuario (típicamente, si no hay agentes activos y la ronda anterior del Master no generó acciones).

Si necesita input, lo solicita (input(...)). Si es 'salir', rompe el bucle.

Llama a orquestador_master.process_input_and_events():

Si obtuvo input del usuario, se lo pasa como argumento.

Si no obtuvo input (ej: esperando eventos de agentes), llama sin argumento (None).

Recibe el resultado del Master: AMBOS el texto de respuesta Y la lista de acciones solicitadas.

Imprime el texto de respuesta del Master en la consola para el usuario.

Itera sobre la lista de acciones solicitadas por el Master y las ejecuta:

Si type == "delegate": Llama a gestor_enjambre.lanzar_agente().

Si type == "send_message": Llama a gestor_enjambre.send_message_to_agent().

Gestiona el estado user_input_needed basándose en si el Master generó acciones o si hay agentes activos.

Incluye pausas (time.sleep) si hay agentes activos o acciones generadas, para dar tiempo a la ejecución asíncrona y no spamear el LLM.

Manejo de KeyboardInterrupt.

### Paso 9: Implementar Gestión de Memoria (Resumen - Placeholder)

Permanece un TODO en bucle_logico_agente.py para gestionar el historial del agente del enjambre mediante resumen. La misma lógica se aplicaría al historial del Agente Master en orquestador_master.py si su historial de conversación con el usuario y las notificaciones del sistema se vuelven demasiado largos.

## Protocolo de Comunicación (Resumen - Re-Enfocado)

La comunicación se logra de forma bidireccional, mediada por tu código Python, con el Master como el centro conversacional:

*   Usuario ↔ Master (Conversación): El usuario escribe input en main.py. main.py lo pasa a orquestador_master.process_input_and_events(). El LLM del Master genera texto de respuesta (y/o Tool Calls). orquestador_master retorna el texto de respuesta a main.py. main.py imprime el texto del Master en la consola.
*   Master → Gestor Enjambre (Delegación/Intervención): Master genera Tool Call (delegate_task o send_message_to_agent). orquestador_master retorna la Tool Call como una acción. main.py intercepta la acción, llama al método correspondiente en gestor_enjambre.
*   Gestor Enjambre → Master (Notificación): Un agente enjambre usa Tool Call (reportar_problema, reportar_resultado_final). bucle_logico_agente.py intercepta, llama a gestor_enjambre.report_agent_problem() / report_agent_status(). gestor_enjambre recibe y llama a orquestador_master.add_message_to_history() para inyectar un SystemMessage en el historial del Master.
*   Agente Enjambre ↔ Servicios (Uso de Herramientas Externas): Agente genera Tool Call (ejecutar_comando_consola). bucle_logico_agente.py intercepta, llama al servicio (ejecutor_consola.ejecutar_comando_seguro()). Resultado se añade como ToolMessage al historial del agente.
*   Master → Agente Enjambre (Directiva/Mensaje): Master genera Tool Call send_message_to_agent. main.py intercepta, llama a gestor_enjambre.send_message_to_agent(). gestor_enjambre busca el bucle del agente, llama a inject_message_and_resume(), inyectando un SystemMessage en el historial del agente y reanudándolo.
