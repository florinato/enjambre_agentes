# servicios/bucle_logico_agente.py
import json
import threading  # Importar threading para el Lock si es necesario para estado/historial concurrente
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain.schema import (AIMessage, BaseMessage, HumanMessage,
                              SystemMessage)
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage, ToolCall, ToolMessage)

from agentes.clase_agente import Agente
# Importar servicios
from prompts.tool_definitions import \
    ejecutar_comando_consola  # Importar el objeto tool
from prompts.tool_definitions import (  # Importar la lista de objetos Tool/funciones y tools necesarias
    SWARM_AGENT_TOOLS, reportar_problema, reportar_resultado_final)
from servicios.ejecutor_consola import ejecutar_comando_seguro
from servicios.gestor_logs import GestorLogs

# from servicios.gestor_enjambre import GestorEnjambre # Para pasarle la referencia


class AgenteExecutionLoop:
    def __init__(self,
                 agente: Agente,
                 ejecutor_consola_svc: Any, # Referencia al servicio
                 gestor_logs_svc: Any,      # Referencia al servicio
                 gestor_enjambre_svc: Any,  # Referencia al GestorEnjambre para reportar problemas/resultados
                 tarea_inicial: str,
                 instruction_prompt_path: str,
                 available_tools_names: List[str]
                 ):

        self.agente: Agente = agente
        self.ejecutor_consola = ejecutor_consola_svc
        self.gestor_logs = gestor_logs_svc
        self.gestor_enjambre_svc = gestor_enjambre_svc # Guardar referencia al gestor enjambre

        self.tarea_inicial: str = tarea_inicial
        self.instruction_prompt_path: str = instruction_prompt_path
        self.available_tools_names: List[str] = available_tools_names

        self.agent_id: str = self.agente.nombre

        # --- Estado del Bucle ---
        self._state: str = "initialized" # Posibles estados: initialized, running, paused, completed, failed, max_iterations

        # Lock para proteger el historial si se accede desde múltiples hilos (ej: inject_message_and_resume)
        self._history_lock = threading.Lock()


        # Mapear nombres de herramientas a sus objetos LangChain Tool (usado para bindear y validar)
        all_available_tools_map = {tool.name: tool for tool in SWARM_AGENT_TOOLS}
        self.tools_to_bind = [all_available_tools_map[name] for name in self.available_tools_names if name in all_available_tools_map]

        if not self.tools_to_bind:
             self.gestor_logs.log_event("agent_init", self.agent_id, "Advertencia: No hay herramientas válidas especificadas para este agente.", log_level="WARNING")
        else:
             self.gestor_logs.log_event("agent_init", self.agent_id, f"Herramientas disponibles para {self.agent_id}: {[t.name for t in self.tools_to_bind]}")


    def _load_instruction_prompt(self) -> str:
        """Carga y formatea el contenido del prompt de instrucción desde el archivo."""
        try:
            with open(self.instruction_prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read().strip()
                # Formatear el template con detalles del agente
                instruction_text = prompt_template.format(
                    agent_name=self.agente.nombre,
                    agent_rol=self.agente.rol,
                    agent_objetivo=self.agente.objetivo
                )
                return instruction_text
        except FileNotFoundError:
            error_msg = f"Error: No se encontró el archivo de prompt de instrucción: {self.instruction_prompt_path}"
            self.gestor_logs.log_event("agent_init", self.agent_id, error_msg, log_level="ERROR")
            print(error_msg)
            self._state = "failed" # Marcar como fallido si no se carga el prompt
            return "You are a helpful agent." # Prompt de fallback


    def _bind_tools_to_llm(self):
        """Vincula las herramientas disponibles al modelo LLM del agente."""
        if self.tools_to_bind:
             self.agente.modelo = self.agente.modelo.bind_tools(self.tools_to_bind)
             self.gestor_logs.log_event("agent_init", self.agent_id, f"Herramientas bindeadas al LLM: {[t.name for t in self.tools_to_bind]}")
        else:
             self.gestor_logs.log_event("agent_init", self.agent_id, "No hay herramientas para bindear al LLM.", log_level="WARNING")

    def inject_message_and_resume(self, message_content: str):
         """
         Inyecta un mensaje (ej: del Master) al historial del agente y lo reanuda si estaba pausado.
         """
         self.gestor_logs.log_event("agent_intervention", self.agent_id, f"Recibido mensaje para inyectar. Estado actual: {self._state}")

         # Usar lock al modificar el historial si el bucle puede estar leyendo
         with self._history_lock:
             # Añadir el mensaje inyectado al historial. Usar un tipo de mensaje claro.
             # SystemMessage es bueno para instrucciones del sistema/Master
             injected_message = SystemMessage(content=f"[Mensaje del Agente Master]: {message_content}")
             self.agente.add_message_to_history(injected_message)
             self.gestor_logs.log_event("agent_intervention", self.agent_id, "Mensaje inyectado al historial.", details={"content": message_content})

         # Si estaba pausado, reanudar
         if self._state == "paused":
             self.gestor_logs.log_event("agent_intervention", self.agent_id, "Agente reanudado.")
             self._state = "running"


    # TODO: Implementar _context_too_long() y _summarize_context() para gestión de memoria

    def run(self):
        """Ejecuta el bucle principal del agente."""
        # gestor_enjambre_svc.iniciar_ejecucion_agente(self.agent_id, ...) # Esto debería ser llamado por GestorEnjambre ANTES de crear el loop

        self.gestor_logs.log_event("agent_init", self.agent_id, "AgenteExecutionLoop iniciado.")
        self._state = "running" # Empezar en estado running

        # --- Inicialización del Contexto y Herramientas (si no se hizo ya) ---
        if not self.agente.get_history():
            instruction_text = self._load_instruction_prompt()
            if self._state == "failed": # Si falló al cargar el prompt
                 self.gestor_logs.finalizar_ejecucion_agente(self.agent_id, "failed", "Error al cargar prompt de instrucción.")
                 return # Salir si no se puede inicializar

            # Añadir la instrucción inicial como SystemMessage
            self.agente.add_message_to_history(SystemMessage(content=f"<instruction>{instruction_text}</instruction>"))
            # Añadir la tarea inicial como el primer mensaje Human
            self.agente.add_message_to_history(HumanMessage(content=self.tarea_inicial))
            self.gestor_logs.log_event("agent_init", self.agent_id, f"Contexto inicial y tarea añadidos. Historial size: {len(self.agente.get_history())}")

            # Vincular herramientas al LLM
            self._bind_tools_to_llm()


        # --- Bucle Principal de Ejecución ---
        iteration_count = 0
        max_iterations = 20 # Límite de iteraciones para evitar bucles infinitos en experimento
        final_result_content: Optional[str] = None # Para capturar el resultado de reportar_resultado_final

        # Bucle se ejecuta mientras el estado sea 'running' y no haya errores/límite
        while self._state == "running" and iteration_count < max_iterations:
            iteration_count += 1
            self.gestor_logs.log_event("agent_loop", self.agent_id, f"--- Iteración {iteration_count} ---", log_level="INFO")

            # --- Pausa si el estado cambia a 'paused' ---
            # Esto permite que inject_message_and_resume cambie el estado y detenga el bucle temporalmente
            while self._state == "paused":
                 self.gestor_logs.log_event("agent_loop", self.agent_id, "Agente pausado. Esperando reanudación...", log_level="INFO")
                 time.sleep(5) # Dormir y re-verificar el estado

            # Si salimos de la pausa pero el estado no es 'running' (ej: fue marcado como fallido mientras pausado)
            if self._state != "running":
                self.gestor_logs.log_event("agent_loop", self.agent_id, f"Saliendo de pausa, estado no es 'running': {self._state}", log_level="INFO")
                break


            # --- Lógica de Gestión de Memoria (Placeholder) ---
            # TODO: Implementar conteo de tokens y lógica de resumen si es necesario
            # if self._context_too_long():
            #    self._summarize_context()
            #    self.gestor_logs.log_event("agent_loop", self.agent_id, "Contexto resumido.")

            # --- Llamada al LLM ---
            try:
                current_history = self.agente.get_history()
                self.gestor_logs.log_llm_interaction(self.agent_id, current_history, "LLM Call Triggered")

                # Usar lock mientras se llama al LLM para que inject_message_and_resume no modifique el historial
                # que se está enviando o procesando.
                with self._history_lock:
                     response_obj: BaseMessage = self.agente.modelo.invoke(current_history)

                self.gestor_logs.log_llm_interaction(self.agent_id, "LLM Input Sent", response_obj)
                self.gestor_logs.log_event("agent_loop", self.agent_id, "Respuesta recibida del LLM.", log_level="DEBUG")

                # Añadir la respuesta del LLM al historial INMEDIATAMENTE para la próxima iteración
                # Esto se hace FUERA del lock de la llamada invoke, pero DENTRO de un lock para modificar el historial
                with self._history_lock:
                     self.agente.add_message_to_history(response_obj)
                     self.gestor_logs.log_event("agent_loop", self.agent_id, f"Respuesta LLM añadida al historial. Nuevo historial size: {len(self.agente.get_history())}", log_level="DEBUG")


            except Exception as e:
                self.gestor_logs.log_event("agent_error", self.agent_id, f"Error durante llamada al LLM: {e}", log_level="ERROR")
                import traceback
                self.gestor_logs.log_event("agent_error", self.agent_id, traceback.format_exc(), log_level="DEBUG")
                self._state = "failed" # Marcar como fallido
                break # Salir del bucle

            # --- Procesar Respuesta del LLM ---
            try:
                tool_calls: Optional[List[ToolCall]] = None
                if isinstance(response_obj, AIMessage):
                     tool_calls = response_obj.additional_kwargs.get('tool_calls') # Gemini >= 1.5 uses 'tool_calls'


                if tool_calls:
                    # --- Es una o más llamadas a Herramienta ---
                    self.gestor_logs.log_event("agent_loop", self.agent_id, f"Detectadas {len(tool_calls)} llamadas a herramienta.", log_level="INFO")

                    tool_messages_to_add: List[ToolMessage] = [] # Para guardar los ToolMessages resultantes

                    for tool_call in tool_calls:
                        tool_name = tool_call.get("function", {}).get("name")
                        tool_args_str = tool_call.get("function", {}).get("arguments")
                        tool_call_id = tool_call.get("id")

                        if not tool_name or tool_args_str is None or not tool_call_id:
                            self.gestor_logs.log_event("agent_error", self.agent_id, f"Llamada a herramienta mal formada: {json.dumps(tool_call)}", log_level="ERROR")
                            error_msg = f"Error: La llamada a herramienta '{tool_name or '??'}' estaba mal formada."
                            tool_messages_to_add.append(ToolMessage(content=json.dumps({"error": error_msg}), tool_call_id=tool_call_id if tool_call_id else "unknown_id"))
                            continue

                        self.gestor_logs.log_event("tool_call_request", self.agent_id, f"Solicitud herramienta: {tool_name}", details={"args_str": tool_args_str, "tool_call_id": tool_call_id})

                        # --- Validar que la herramienta solicitada esté permitida ---
                        if tool_name not in self.available_tools_names:
                            error_msg = f"Error: Herramienta '{tool_name}' solicitada no permitida para este agente."
                            self.gestor_logs.log_event("agent_error", self.agent_id, error_msg, log_level="ERROR")
                            tool_messages_to_add.append(ToolMessage(content=json.dumps({"error": error_msg}), tool_call_id=tool_call_id))
                            continue

                        # --- Ejecutar la Lógica de la Herramienta Correspondiente ---
                        # Nota: No se llama al objeto @tool aquí, se llama al SERVICIO Python correspondiente
                        tool_result_content: Any = None
                        execution_error: Optional[str] = None
                        should_terminate_after_tool: bool = False # Si la tool marca el fin de la tarea
                        should_pause_after_tool: bool = False # Si la tool marca una pausa (reportar_problema)


                        try:
                            tool_args = json.loads(tool_args_str)
                        except json.JSONDecodeError:
                            execution_error = f"Error al decodificar argumentos JSON para {tool_name}: {tool_args_str}"
                            self.gestor_logs.log_event("agent_error", self.agent_id, execution_error, log_level="ERROR")


                        if execution_error is None: # Solo intentar ejecutar si el parseo de args fue bien
                             if tool_name == ejecutar_comando_consola.name:
                                command = tool_args.get("command")
                                if isinstance(command, str):
                                    resultado_comando = self.ejecutor_consola.ejecutar_comando_seguro(command)
                                    tool_result_content = json.dumps(resultado_comando)
                                    self.gestor_logs.log_tool_execution(self.agent_id, tool_name, command, resultado_comando.get("salida",""), resultado_comando.get("error",""), resultado_comando.get("codigo",-1), tool_call_id)
                                else:
                                     execution_error = "Error: La llamada a 'ejecutar_comando_consola' requiere el argumento 'command' (string)."

                             elif tool_name == reportar_resultado_final.name:
                                final_result_content = tool_args.get("resultado")
                                if final_result_content is not None:
                                    self.gestor_logs.log_event("agent_complete", self.agent_id, "Agente reporta resultado final.")
                                    # Almacenar el resultado final y marcar para terminar
                                    final_result_content = str(final_result_content)
                                    self._task_completed = True
                                    should_terminate_after_tool = True
                                    self.gestor_enjambre_svc.report_agent_status(self.agent_id, "completed", final_result_content) # Reportar al gestor
                                else:
                                    execution_error = "Error: La llamada a 'reportar_resultado_final' requiere el argumento 'resultado'."

                             elif tool_name == reportar_problema.name:
                                problem_description = tool_args.get("descripcion_problema")
                                if isinstance(problem_description, str):
                                    self.gestor_logs.log_event("agent_problem", self.agent_id, f"Agente reporta problema: {problem_description[:200]}...")
                                    # Marcar para pausar y reportar al gestor
                                    self._state = "paused" # Cambiar estado del bucle
                                    should_pause_after_tool = True # Indicar que debe pausar después de añadir ToolMessage
                                    # Reportar al gestor enjambre para que notifique al Master
                                    self.gestor_enjambre_svc.report_agent_problem(self.agent_id, problem_description)
                                else:
                                     execution_error = "Error: La llamada a 'reportar_problema' requiere el argumento 'descripcion_problema' (string)."


                             # TODO: Añadir manejo para otras herramientas aquí

                             else:
                                 # Herramienta permitida pero sin lógica de ejecución implementada aquí
                                 execution_error = f"Error: Lógica de ejecución no implementada para herramienta permitida '{tool_name}'."


                        # --- Preparar Resultado de Herramienta para Añadir al Historial (si no es herramienta de terminación/pausa sin resultado) ---
                        if not should_terminate_after_tool and not should_pause_after_tool: # Si NO es una herramienta de terminación o pausa que no reporta resultado explícito
                            if execution_error:
                                self.gestor_logs.log_event("agent_error", self.agent_id, f"Error en ejecución/args de {tool_name}: {execution_error}", log_level="ERROR")
                                # Reportar el error al LLM como contenido del ToolMessage
                                tool_result_content = json.dumps({"error": execution_error})
                            elif tool_result_content is None:
                                # Si no hubo error ni resultado explícito (ej: tool que no devuelve nada, pero no termina/pausa)
                                # Enviar un resultado vacío o de éxito simple si tool_result_content no fue seteado
                                tool_result_content = json.dumps({"status": "success", "message": f"Tool '{tool_name}' executed."})

                            # Crear y añadir el ToolMessage al historial (usar lock)
                            # Esto prepara el contexto para la *siguiente* llamada al LLM
                            with self._history_lock:
                                tool_message = ToolMessage(content=str(tool_result_content), tool_call_id=tool_call_id)
                                self.agente.add_message_to_history(tool_message)
                                self.gestor_logs.log_event("tool_result_added", self.agent_id, f"Resultado de {tool_name} añadido al historial.", log_level="DEBUG")


                    # --- Romper el Bucle si una Tool Call marcó la terminación o un error fatal ---
                    if self._state != "running": # Si el estado cambió a 'paused', 'completed', 'failed'
                        break # Salir del bucle principal

                    # Si hubo tool calls pero el estado sigue 'running', el bucle continuará
                    # para la siguiente iteración, donde el LLM verá los ToolMessages añadidos.

                else:
                    # --- No hay llamadas a Herramientas, es Texto Normal ---
                    # La respuesta de texto ya fue añadida al historial arriba (response_obj)
                    response_text = response_obj.content

                    # Verificar si el texto indica terminación (si el agente no usó reportar_resultado_final tool)
                    # Esto es un fallback. Es mejor que el agente use la tool.
                    if self._check_for_termination_marker(response_text):
                        self.gestor_logs.log_event("agent_complete_marker", self.agent_id, "Tarea completada (marcador en texto).")
                        self._state = "completed" # Marcar como completado
                        # TODO: Capturar resultado si es posible del texto final
                        final_result_content = response_text # Usar el texto como resultado final
                        self.gestor_enjambre_svc.report_agent_status(self.agent_id, "completed", final_result_content) # Reportar al gestor
                        break # Salir del bucle

                    # Si no es una llamada a herramienta y no es una respuesta final de texto,
                    # el bucle terminará esta iteración. En la siguiente, el LLM verá su
                    # propia última respuesta de texto y continuará "pensando".

            except Exception as e:
                self.gestor_logs.log_event("agent_error", self.agent_id, f"Error al procesar la respuesta del LLM o durante manejo de tool_call: {e}", log_level="ERROR")
                import traceback
                self.gestor_logs.log_event("agent_error", self.agent_id, traceback.format_exc(), log_level="DEBUG")
                self._state = "failed" # Marcar como fallido
                break # Salir del bucle

            # Pausa corta entre iteraciones
            time.sleep(0.1)


        # --- Fin del Bucle ---
        # Si el bucle terminó por max_iterations
        if iteration_count >= max_iterations and self._state == "running":
             self._state = "max_iterations"
             self.gestor_logs.log_event("agent_loop_end", self.agent_id, f"Bucle finalizado por límite de iteraciones ({max_iterations}).", log_level="WARNING")


        # Registrar el estado final si no se hizo ya por una Tool Call de reporte
        if self._state not in ["completed", "failed", "fatal_error"]: # Si el estado se cambió por un error fatal fuera del try/except
             self.gestor_logs.finalizar_ejecucion_agente(self.agent_id, self._state, final_result=final_result_content)

        self.gestor_logs.log_event("agent_loop_end", self.agent_id, f"Bucle de ejecución finalizado. Estado final: {self._state}", log_level="INFO")
        print(f"Agente {self.agent_id} finalizado con estado: {self._state}")

        # No retornar explícitamente, el estado y resultados se reportan via gestor_enjambre_svc


# Inicializa los servicios primero
DB_FILE = "data\swarm.db"  # Define aquí la ruta a tu archivo de base de datos
gestor_logs = GestorLogs(db_path=DB_FILE)
ejecutor_consola_svc = ejecutar_comando_seguro

# Importar o definir cargar_llm antes de usarlo
from servicios.cargar_llm import \
    cargar_llm  # Ajusta la ruta según tu estructura de proyecto
from servicios.gestor_enjambre import GestorEnjambre
# Importar OrquestadorMaster y GestorEnjambre antes de usarlos
from servicios.orquestador_master import OrquestadorMaster

cargar_llm_svc = cargar_llm

# Crea el orquestador y el gestor de enjambre con referencias reales
orquestador_master = OrquestadorMaster(
    gestor_logs=gestor_logs,
    gestor_enjambre=None,  # Se asignará después
    cargar_llm_svc=cargar_llm_svc
)
gestor_enjambre = GestorEnjambre(
    cargar_llm_svc=cargar_llm_svc,
    ejecutor_consola_svc=ejecutor_consola_svc,
    gestor_logs_svc=gestor_logs,
    orquestador_master_svc=orquestador_master
)
# Ahora puedes asignar la referencia circular si es necesario:
orquestador_master.gestor_enjambre = gestor_enjambre


