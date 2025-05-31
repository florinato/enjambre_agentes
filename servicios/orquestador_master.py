# servicios/orquestador_master.py
import json
import re
from typing import Any, Dict, List, Optional

from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.schema.messages import BaseMessage

# Importar las herramientas del Master como objetos @tool
from prompts.tool_definitions import (MASTER_AGENT_TOOLS, delegate_task,
                                      send_message_to_agent)

# Importar servicios necesarios
# from servicios.cargar_llm import cargar_llm, get_shared_llm_instance
# from servicios.gestor_enjambre import GestorEnjambre
# from servicios.gestor_logs import GestorLogs

# Hacer forward declaration si hay referencias circulares
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from servicios.cargar_llm import cargar_llm
#     from servicios.gestor_enjambre import GestorEnjambre
#     from servicios.gestor_logs import GestorLogs


class OrquestadorMaster:
    def __init__(self, gestor_logs: Any, gestor_enjambre: Any, cargar_llm_svc: Any):
        self.gestor_logs = gestor_logs
        self.gestor_enjambre_svc = gestor_enjambre # Referencia al gestor para enviar mensajes via main.py

        # Cargar LLM del Master
        print(f"Tipo de cargar_llm_svc: {type(cargar_llm_svc)}")
        print(f"Valor de cargar_llm_svc: {cargar_llm_svc}")
        self.modelo = cargar_llm_svc() # O get_shared_llm_instance()
        if not self.modelo:
             self.gestor_logs.log_event("master_init", "master", "Error: No se pudo cargar el LLM para el Master.", log_level="FATAL")
             # No se puede operar sin LLM
             return # O lanzar excepción

        # --- Inicializar historial del Master ---
        self.historial_conversacion: List[BaseMessage] = []
        self.prompt_master_text = self.cargar_prompt("prompts/master_agent_prompt.txt") # Cargar el texto del prompt

        # Asegurar que el historial del Master comience con su instrucción
        if self.prompt_master_text:
             self.add_message_to_history(SystemMessage(content=f"<instruction>{self.prompt_master_text}</instruction>"))
             self.gestor_logs.log_event("master_init", "master", "Instrucción Master añadida al historial.")
        else:
             self.gestor_logs.log_event("master_init", "master", "Advertencia: Prompt del Master vacío.", log_level="WARNING")


        # Vincular TODAS las herramientas del Master al modelo
        # Asegurarse de que self.modelo existe
        if self.modelo:
             self.modelo = self.modelo.bind_tools(MASTER_AGENT_TOOLS)
             self.gestor_logs.log_event("master_init", "master", f"Herramientas Master bindeadas al LLM: {[t.name for t in MASTER_AGENT_TOOLS]}.")
        else:
             self.gestor_logs.log_event("master_init", "master", "Error: No se pudo bindear herramientas, LLM no cargado.", log_level="ERROR")


    def cargar_prompt(self, file_path: str) -> str:
        """Carga el prompt desde el archivo."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            error_msg = f"Error: No se encontró el archivo de prompt del Master: {file_path}"
            self.gestor_logs.log_event("master_init", "master", error_msg, log_level="ERROR")
            print(error_msg)
            return "You are a helpful orchestrator." # Prompt de fallback


    def add_message_to_history(self, message: BaseMessage):
        """Añade un mensaje al historial de conversación del Master (usado por sistema para notificar)."""
        if not isinstance(message, BaseMessage):
             print(f"Advertencia Master: Intentando añadir un objeto no-BaseMessage ({type(message)}) al historial. Ignorando.")
             return
        # TODO: Implementar gestión de memoria/resumen para el historial del Master si se vuelve muy largo
        self.historial_conversacion.append(message)
        self.gestor_logs.log_event("master_context_update", "master", "Mensaje añadido al historial del Master.", log_level="DEBUG", details={"message_type": type(message).__name__, "content_snippet": str(message)[:100] + "..."})


    def process_user_task_or_event(self, input_message: str) -> List[Dict[str, Any]]:
        """
        Procesa una nueva tarea del usuario O permite que el Master reaccione a eventos
        en su historial (como notificaciones de problemas).
        Retorna una lista de acciones solicitadas por el Master (delegar, enviar mensaje).
        """
        self.gestor_logs.log_event("master_input", "master", f"Recibido input para Master: {input_message}")

        if not self.modelo:
             self.gestor_logs.log_event("master_input", "master", "Error: LLM del Master no cargado.", log_level="ERROR")
             return []


        # Añadir el input (tarea del usuario o señal para reaccionar) al historial del Master
        # Podría ser un HumanMessage si viene del usuario, o un SystemMessage si es una señal interna.
        # Por ahora, asumimos que `input_message` es la tarea del usuario.
        # Si la entrada es una señal para reaccionar, el historial ya contendrá la notificación.
        self.add_message_to_history(HumanMessage(content=input_message))


        # --- Llamada al LLM del Master ---
        response_obj: Optional[BaseMessage] = None
        try:
            self.gestor_logs.log_event("llm_call", "master", "Llamando al LLM Master con historial...", log_level="DEBUG")
            # Pasar el historial completo del Master al LLM
            response_obj = self.modelo.invoke(self.historial_conversacion)

            # Loggear interacción del LLM del Master
            self.gestor_logs.log_llm_interaction("master", self.historial_conversacion, response_obj) # Log input y output object
            self.gestor_logs.log_event("master_loop", "master", "Respuesta recibida del LLM Master.", log_level="DEBUG")

            # Añadir la respuesta del LLM al historial del Master
            self.add_message_to_history(response_obj)
            self.gestor_logs.log_event("master_response", "master", f"Respuesta del Master: {response_obj.content}", log_level="INFO")

        except Exception as e:
            self.gestor_logs.log_event("master_error", "master", f"Error durante llamada al LLM Master: {e}", log_level="ERROR")
            print(f"Error durante llamada al LLM Master: {e}")
            # No retornar aquí, intentar procesar respuesta_obj si llegó algo parcial


        # --- Procesar Respuesta del LLM del Master (Buscar Acciones Solicitadas) ---
        actions_requested: List[Dict[str, Any]] = [] # Puede contener delegar o enviar mensaje
        respuesta_texto = ""

        if response_obj:
             try:
                 tool_calls = None  # type: Optional[List[dict]]
                 if isinstance(response_obj, AIMessage):
                      tool_calls = response_obj.additional_kwargs.get('tool_calls')

                 if tool_calls:
                      self.gestor_logs.log_event("master_loop", "master", f"Detectadas {len(tool_calls)} llamadas a herramienta en respuesta LLM Master.", log_level="INFO")

                      for tool_call in tool_calls:
                           tool_name = tool_call.get("function", {}).get("name")
                           tool_args_str = tool_call.get("function", {}).get("arguments")
                           tool_call_id = tool_call.get("id")

                           if not tool_name or tool_args_str is None or not tool_call_id:
                               self.gestor_logs.log_event("master_error", "master", f"Llamada a herramienta mal formada: {json.dumps(tool_call)}", log_level="ERROR")
                               continue

                           try:
                               tool_args = json.loads(tool_args_str)
                           except json.JSONDecodeError:
                               self.gestor_logs.log_event("master_error", "master", f"Error al decodificar argumentos JSON para {tool_name}: {tool_args_str}", log_level="ERROR")
                               continue

                           # --- Procesar Tool Calls Conocidas del Master ---
                           if tool_name == delegate_task.name:
                                # Validar args y añadir a la lista de acciones
                                agent_type = tool_args.get("agent_type")
                                task_description = tool_args.get("task_description")
                                if isinstance(agent_type, str) and isinstance(task_description, str):
                                    actions_requested.append({
                                        "type": "delegate",
                                        "agent_type": agent_type,
                                        "task_description": task_description,
                                        "tool_call_id": tool_call_id # Mantener referencia si es útil
                                    })
                                    self.gestor_logs.log_event("master_action", "master", f"Solicitud de delegación: {agent_type}", details={"task": task_description})
                                else:
                                     self.gestor_logs.log_event("master_error", "master", f"Llamada a delegate_task args inválidos: {tool_args}", log_level="ERROR")

                           elif tool_name == send_message_to_agent.name:
                                # Validar args y añadir a la lista de acciones
                                agent_id = tool_args.get("agent_id")
                                message_content = tool_args.get("message_content")
                                if isinstance(agent_id, str) and isinstance(message_content, str):
                                     actions_requested.append({
                                         "type": "send_message",
                                         "agent_id": agent_id,
                                         "message_content": message_content,
                                         "tool_call_id": tool_call_id
                                     })
                                     self.gestor_logs.log_event("master_action", "master", f"Solicitud enviar mensaje a agente: {agent_id}", details={"message_snippet": message_content[:100] + "..."})
                                else:
                                     self.gestor_logs.log_event("master_error", "master", f"Llamada a send_message_to_agent args inválidos: {tool_args}", log_level="ERROR")

                           else:
                                # El Master pidió otra herramienta desconocida
                                self.gestor_logs.log_event("master_error", "master", f"El Master solicitó herramienta desconocida: {tool_name}", log_level="WARNING", details={"tool_call": tool_call})


                 # Si no hay tool_calls, la respuesta es texto normal
                 if not tool_calls and response_obj.content:
                      self.gestor_logs.log_event("master_response_text", "master", f"Respuesta de texto del Master: {response_obj.content[:200]}...", log_level="INFO")
                      respuesta_texto = response_obj.content
                      # Aquí podrías tener lógica para interactuar con el usuario o marcar que Master ha terminado su fase de planning/respuesta


             except Exception as e:
                 self.gestor_logs.log_event("master_error", "master", f"Error al procesar la respuesta del LLM Master o parsear tool_calls: {e}", log_level="ERROR")
                 print(f"Error al procesar la respuesta del LLM Master o parsear tool_calls: {e}")

        return actions_requested, respuesta_texto # Retorna la lista de acciones a ser ejecutadas por main.py y el texto de respuesta
