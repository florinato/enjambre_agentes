Informe Detallado: Transformación de agente_plantilla a Enjambre de Agentes con Intervención del Master
Objetivo: Adaptar la estructura mono-agente de agente_plantilla para crear un sistema de enjambre multi-agente orquestado asíncronamente, con gestión de contexto individual, uso estandarizado de herramientas (consola como principal), logging en base de datos, y capacidades de comunicación bidireccional que permitan al Agente Master supervisar el estado de los agentes del enjambre, recibir reportes de problemas, y enviar mensajes para intervenir o reanudar la ejecución.
Punto de Partida: El repositorio agente_plantilla proporciona una excelente base en su estructura (servicios/, agentes/, prompts/), la clase Agente con gestión de historial LangChain, y servicios placeholders.
Componentes de la Arquitectura Final (Actualizada):
main.py: Bucle Principal de Orquestación. Maneja la interacción con el usuario, procesa las acciones del Agente Master (delegación, envío de mensajes), y monitorea el estado general del enjambre.
agentes/clase_agente.py: Clase base para un agente individual del enjambre. Contenedor de estado: nombre, rol, objetivo, instancia del LLM, y su historial de conversación (contexto).
servicios/cargar_llm.py: Servicio centralizado para la inicialización y configuración (incluyendo bindeo de herramientas) de las instancias del LLM (Gemini). Usado por el Master y cada Agente del Enjambre.
servicios/ejecutor_consola.py: Servicio seguro (en la medida de lo posible) para ejecutar comandos en la consola del contenedor. Invocado por el bucle_logico_agente cuando un agente lo solicita via Tool Call.
servicios/gestor_logs.py: Servicio centralizado para interactuar con la base de datos SQLite (data/swarm.db). Registra toda la actividad del sistema: acciones del Master, ciclo de vida y estado de los agentes, cada interacción LLM (input/output), cada uso de herramienta y su resultado, y reportes de problemas/resultados.
servicios/orquestador_master.py: Lógica del Agente Master. Interactúa con su propio LLM y contexto. Recibe tareas del usuario o notificaciones del sistema (inyectadas en su historial). Genera acciones (delegar, enviar mensaje) via Tool Calls. No ejecuta tareas directamente.
servicios/gestor_enjambre.py: Gestor del Enjambre. Mantiene un registro de las instancias de los agentes del enjambre activos (sus AgenteExecutionLoop) y sus hilos. Recibe solicitudes de lanzamiento (delegación) desde main.py. Recibe reportes de estado, resultados y problemas desde los bucle_logico_agente. Implementa la lógica para enviar mensajes a agentes específicos (inyectando en su historial y reanudándolos).
servicios/bucle_logico_agente.py: Bucle de Ejecución para UN agente del enjambre. Contiene la lógica principal del ciclo: gestionar el historial, llamar al LLM (pasando el historial completo), procesar la respuesta (detectar Tool Calls o texto), llamar a servicios (ejecutor_consola), reportar estado/problemas/resultados al gestor_enjambre.py (via Tool Calls interceptadas por sí mismo), y gestionar su propio estado (running, paused, completed, failed), incluyendo la lógica de pausa y reanudación.
prompts/: Directorio para almacenar los textos de los prompts (instrucciones) para el Master y los diferentes tipos de agentes del enjambre.
prompts/tool_definitions.py: Archivo Python que define formalmente las herramientas disponibles para el Master y los agentes del enjambre utilizando @tool de LangChain. Incluye herramientas para acciones externas (consola) y herramientas para modelar la comunicación interna (delegar, reportar resultado, reportar problema, enviar mensaje).
agentes_json/: Directorio que contiene archivos JSON con las definiciones configurables de cada tipo de agente del enjambre (rol, objetivo, archivo de prompt de instrucción, herramientas permitidas).
data/swarm.db: Archivo de la base de datos SQLite para el logging y estado persistente.
docker/: Archivos para construir y ejecutar el sistema en un contenedor Docker.
Pasos de Transformación (Actualizados):
Paso 1: Configuración Inicial y Estructura (Ajustado)
Mantener la estructura de directorios agentes/, servicios/, prompts/, agentes_json/, data/, docker/.
Configurar .env con MODEL y GOOGLE_API_KEY.
Asegurarse de que requirements.txt incluya las dependencias necesarias (langchain, langchain-google-genai, python-dotenv, sqlite3) y langchain-core.
Asegurar que el Dockerfile cree el directorio data/ y configure volúmenes para persistir swarm.db.
Paso 2: Implementar Servicios Base (Completado/Refinado)
servicios/cargar_llm.py: Implementado según tu versión proporcionada. Se usará para cargar instancias de ChatGoogleGenerativeAI para el Master y cada agente del enjambre.
servicios/ejecutor_consola.py: Implementado según tu versión proporcionada, con la nota sobre shell=True como riesgo experimental. Es llamado por el bucle_logico_agente.
servicios/gestor_logs.py: Implementado según tu versión proporcionada, con estructura básica para SQLite y métodos para loggear eventos, inicios/fines de ejecución de agentes, interacciones LLM y ejecuciones de herramientas. Es llamado por casi todos los componentes.
Paso 3: Refinar Clase Agente (Completado)
agentes/clase_agente.py: Implementado como un holder de estado (nombre, rol, objetivo, modelo, historial_conversacion como lista de BaseMessage). Métodos add_message_to_history y get_history son clave. Eliminado ConversationChain y Memory.
Paso 4: Implementar Herramientas y Definiciones (Completado)
prompts/tool_definitions.py: Implementado con las definiciones @tool para:
Agentes del Enjambre: ejecutar_comando_consola, reportar_resultado_final, reportar_problema.
Agente Master: delegate_task, send_message_to_agent.
Listas SWARM_AGENT_TOOLS y MASTER_AGENT_TOOLS para bindeo.
agentes_json/: Crear archivos JSON para cada tipo de agente (ej: ejecutor.json, analista.json). Cada JSON define agent_type, rol, objetivo, instruction_prompt_file, y la lista available_tools (nombres de las herramientas permitidas, incluyendo las de comunicación reportar_resultado_final y reportar_problema si aplica).
prompts/: Crear archivos .txt para cada prompt de instrucción de agente del enjambre y para el Master. Estos prompts deben instruir al LLM sobre su rol, objetivo, herramientas disponibles, y cómo usar las herramientas de reporte (reportar_resultado_final, reportar_problema) y cómo interpretar mensajes inyectados (para agentes del enjambre) o notificaciones inyectadas (para el Master).
Paso 5: Implementar Bucle Lógico del Agente (Core - Completado/Refinado)
servicios/bucle_logico_agente.py: Implementado como la clase AgenteExecutionLoop.
Recibe instancias del Agente y de los servicios (ejecutor_consola_svc, gestor_logs_svc, gestor_enjambre_svc).
Mantiene un atributo de estado (_state: running, paused, completed, failed, etc.).
En run(), carga el prompt de instrucción desde archivo y lo añade al historial como SystemMessage. Añade la tarea inicial como HumanMessage. Bindea las herramientas permitidas (available_tools_names) al LLM del agente (agente.modelo.bind_tools(...)).
Contiene el bucle while self._state == "running":.
Dentro del bucle, llama al LLM con el historial completo (agente.modelo.invoke(agente.get_history())).
Procesa la respuesta del LLM: Detecta Tool Calls (response_obj.additional_kwargs.get('tool_calls')).
Maneja Tool Calls:
Si ejecutar_comando_consola: Llama a ejecutor_consola_svc.ejecutar_comando_seguro(). Añade ToolMessage con el resultado al historial.
Si reportar_resultado_final: Marca el estado a completed. Llama a gestor_enjambre_svc.report_agent_status(agent_id, "completed", resultado). Sale del bucle principal.
Si reportar_problema: Marca el estado a paused. Llama a gestor_enjambre_svc.report_agent_problem(agent_id, problem_description). Sale del bucle principal (para ir al estado de pausa).
Para otras Tool Calls: Llama al servicio correspondiente y añade ToolMessage.
Maneja errores de Tool Calls (mal formadas, argumentos incorrectos, no permitidas) añadiendo ToolMessage con el error al historial.
Si la respuesta no es una Tool Call: Añade el texto (AIMessage) al historial.
Maneja el estado paused en el bucle: Entra en un sub-bucle de espera (while self._state == "paused":).
Implementa inject_message_and_resume(message_content): Añade un SystemMessage con el message_content al historial y cambia _state a running.
Loggea todos los pasos clave usando gestor_logs_svc.
Implementa lógica básica de límite de iteraciones.
Paso 6: Implementar Gestor del Enjambre (Completado/Refinado)
servicios/gestor_enjambre.py: Implementado como la clase GestorEnjambre.
Recibe referencias a todos los servicios (cargar_llm_svc, ejecutor_consola_svc, gestor_logs_svc, orquestador_master_svc).
Carga las definiciones de agentes desde los archivos JSON en agentes_json/ en __init__.
lanzar_agente(agent_type, task_description):
Busca la definición JSON para agent_type.
Crea instancia de Agente.
Registra inicio en gestor_logs_svc.
Crea instancia de AgenteExecutionLoop, pasándole el Agente, todos los servicios (incluyendo self como gestor_enjambre_svc), tarea inicial, ruta al prompt y nombres de herramientas permitidas (de la definición JSON).
Lanza loop.run() en un hilo separado (threading.Thread).
Mantiene registros (agentes_activos, agente_threads, agentes_status, agentes_resultados, agentes_problemas) con locks para acceso seguro desde múltiples hilos.
Implementa report_agent_status(agent_id, status, result=None): Recibe estado final/resultado del bucle lógico, actualiza estado local, loggea.
Implementa report_agent_problem(agent_id, problem_description): Recibe reporte de problema del bucle lógico, actualiza estado local a "paused", loggea, y llama a orquestador_master_svc.add_message_to_history() para inyectar una notificación en el historial del Master.
Implementa send_message_to_agent(agent_id, message_content): Busca la instancia del bucle lógico por ID, y llama a loop.inject_message_and_resume(message_content).
Paso 7: Implementar Orquestador Master (Completado/Refinado)
servicios/orquestador_master.py: Implementado como la clase OrquestadorMaster.
Recibe referencias a gestor_logs_svc, gestor_enjambre_svc, cargar_llm_svc.
Carga su prompt desde archivo y lo añade a su historial (historial_conversacion).
Bindea las herramientas del Master (MASTER_AGENT_TOOLS, incluyendo delegate_task y send_message_to_agent) a su LLM.
process_user_task_or_event(input_message=None): Método clave llamado por main.py.
Si input_message no es None, lo añade como HumanMessage (tarea de usuario).
Llama a su LLM con su historial completo.
Loggea la interacción LLM.
Procesa la respuesta del LLM: Busca Tool Calls (response_obj.additional_kwargs.get('tool_calls')).
Maneja Tool Calls del Master:
Si delegate_task: Extrae args, añade a una lista de acciones solicitadas de tipo "delegate".
Si send_message_to_agent: Extrae args, añade a una lista de acciones solicitadas de tipo "send_message".
Añade la respuesta del LLM a su historial.
Retorna la lista de acciones solicitadas ({"type": "delegate", ...} o {"type": "send_message", ...}) a main.py.
add_message_to_history(): Método público llamado por gestor_enjambre.py para inyectar notificaciones (problemas de agentes).
Paso 8: Implementar Orquestación General en main.py (Completado/Refinado)
main.py: Implementado como el bucle principal de control.
Inicializa todos los servicios (GestorLogs, función ejecutor_comando_seguro, función cargar_llm).
Inicializa GestorEnjambre y OrquestadorMaster, pasando las referencias a los servicios y las referencias circulares entre ellos.
Contiene un bucle while True principal.
Dentro del bucle:
Verifica el estado de los agentes activos (gestor_enjambre.get_all_agents_status()).
Si no hay agentes activos Y se necesita input del usuario, pide tarea al usuario. Si la tarea es 'salir', rompe el bucle principal.
Llama a orquestador_master.process_user_task_or_event(): Si hay input del usuario, se lo pasa. Si no, le pasa None para que el Master procese solo su historial (y reaccione a notificaciones de problemas inyectadas).
Recibe la lista de acciones solicitadas por el Master.
Itera sobre las acciones y las ejecuta:
Si type == "delegate": Llama a gestor_enjambre.lanzar_agente().
Si type == "send_message": Llama a gestor_enjambre.send_message_to_agent().
Tiene lógica para determinar si debe pedir input de usuario en el siguiente ciclo (cuando no hay agentes activos Y el Master no solicitó más acciones en esta ronda).
Incluye pausas (time.sleep) para no spamear el LLM y permitir que los hilos de agentes trabajen.
Manejo básico de KeyboardInterrupt para salir.
Paso 9: Implementar Gestión de Memoria (Resumen - Placeholder)
La lógica para medir tokens y resumir el historial en bucle_logico_agente.py sigue siendo un TODO. La estructura para insertarla en el bucle (_context_too_long, _summarize_context) está esbozada.
Protocolo de Comunicación (Resumen de Implementación - Actualizado):
La comunicación dentro de tu sistema se logra ahora de forma bidireccional, mediada por tu código Python y utilizando Tool Calls como lenguaje de señalización:
Usuario → Master: Input de texto capturado por main.py, pasado a orquestador_master.process_user_task_or_event() como input_message.
Master → Gestor Enjambre (Delegación): Master genera Tool Call delegate_task. main.py intercepta, llama a gestor_enjambre.lanzar_agente(), pasando task_description como HumanMessage inicial para el nuevo agente.
Agente Enjambre → Servicios (Uso de Herramientas Externas): Agente genera Tool Call ejecutar_comando_consola. bucle_logico_agente.py intercepta, llama a ejecutor_consola.ejecutar_comando_seguro(). Resultado se añade como ToolMessage al historial del agente.
Agente Enjambre → Gestor Enjambre (Reporte de Resultado Final): Agente genera Tool Call reportar_resultado_final. bucle_logico_agente.py intercepta, marca estado 'completed', llama a gestor_enjambre.report_agent_status().
Agente Enjambre → Gestor Enjambre → Master (Reporte de Problema): Agente genera Tool Call reportar_problema. bucle_logico_agente.py intercepta, marca estado 'paused', llama a gestor_enjambre.report_agent_problem(). gestor_enjambre recibe, loggea, y llama a orquestador_master.add_message_to_history() para inyectar un SystemMessage de notificación en el historial del Master.
Master → Gestor Enjambre → Agente Enjambre (Intervención): Master genera Tool Call send_message_to_agent. main.py intercepta, llama a gestor_enjambre.send_message_to_agent(). gestor_enjambre recibe, busca el agente por ID, y llama a bucle_logico_agente.inject_message_and_resume() en la instancia correspondiente, inyectando el message_content como SystemMessage en el historial del agente y cambiando su estado a running.
Servicios → Logs: Todos los componentes clave llaman a gestor_logs_svc.log_event() o métodos específicos para registrar su actividad.