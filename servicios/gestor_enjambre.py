# servicios/gestor_enjambre.py
import json
import os
import threading
import time  # Para ID simple
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage

# Importar SystemMessage para notificaciones al Master
# Importar las clases necesarias
from agentes.clase_agente import Agente

# from servicios.bucle_logico_agente import AgenteExecutionLoop

# Importar servicios (solo para type hinting o si se pasan en __init__)
# from servicios.cargar_llm import cargar_llm
# from servicios.ejecutor_consola import ejecutar_comando_seguro
# from servicios.gestor_logs import GestorLogs
# from servicios.orquestador_master import OrquestadorMaster # Para pasar la referencia


class GestorEnjambre:
    def __init__(self, cargar_llm_svc: Any, ejecutor_consola_svc: Any, gestor_logs_svc: Any, orquestador_master_svc: Any):
        self.cargar_llm_svc = cargar_llm_svc # Servicio para cargar LLM (no lo usa directamente, lo pasan a AgenteExecutionLoop)
        self.ejecutor_consola_svc = ejecutor_consola_svc
        self.gestor_logs_svc = gestor_logs_svc
        self.orquestador_master_svc = orquestador_master_svc # Referencia al Master para notificar problemas

        # --- Cargar Definiciones de Agentes ---
        self.agente_definitions = self._load_agent_definitions("agentes_json/")
        if not self.agente_definitions:
             print("Advertencia GestorEnjambre: No se cargaron definiciones de agentes desde agentes_json/.")
             self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", "No se cargaron definiciones de agentes.", log_level="WARNING")

        # --- Gestión de agentes activos (ahora bucles de ejecución) ---
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from servicios.bucle_logico_agente import AgenteExecutionLoop
        self.agentes_activos: Dict[str, "AgenteExecutionLoop"] = {} # Mapea agent_id a instancia del Bucle
        self.agente_threads: Dict[str, threading.Thread] = {} # Mapea agent_id a su hilo de ejecución

        # Para manejar resultados reportados y problemas
        self.agente_status_lock = threading.Lock() # Lock para acceder a self.agentes_activos_status y resultados
        self.agentes_status: Dict[str, str] = {} # Estado actual reportado por agentes (completed, failed, paused)
        self.agentes_resultados: Dict[str, Any] = {} # Resultados finales reportados


        self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", f"Gestor de Enjambre inicializado. Definiciones cargadas: {list(self.agente_definitions.keys())}")


    def _load_agent_definitions(self, dir_path: str) -> Dict[str, Dict[str, Any]]:
        """Carga las definiciones de agentes desde archivos JSON en el directorio."""
        definitions = {}
        if not os.path.isdir(dir_path):
            self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", f"Directorio de definiciones de agentes no encontrado: {dir_path}", log_level="ERROR")
            return definitions

        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                file_path = os.path.join(dir_path, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        definition = json.load(f)
                        required_keys = ["agent_type", "rol", "objetivo", "instruction_prompt_file", "available_tools"]
                        if all(k in definition for k in required_keys):
                             definitions[definition["agent_type"]] = definition
                             self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", f"Definición cargada: {definition['agent_type']}", log_level="DEBUG")
                        else:
                             missing_keys = [k for k in required_keys if k not in definition]
                             self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", f"Definición JSON inválida (faltan claves: {missing_keys}) en {filename}", log_level="WARNING", details={"definition": definition})
                except json.JSONDecodeError:
                     self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", f"Error al parsear JSON en {filename}", log_level="ERROR")
                except Exception as e:
                     self.gestor_logs_svc.log_event("swarm_init", "gestor_enjambre", f"Error al cargar definición {filename}: {e}", log_level="ERROR")

        return definitions


    def lanzar_agente(self, agent_type: str, task_description: str):
        """
        Lanza un nuevo agente en el enjambre basado en su tipo definido.
        Ahora ejecuta el bucle en un hilo separado.
        """
        self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Recibida solicitud para lanzar agente {agent_type} con tarea: {task_description}")

        # --- Buscar definición ---
        definition = self.agente_definitions.get(agent_type)
        if not definition:
            error_msg = f"Error GestorEnjambre: Definición de agente '{agent_type}' no encontrada."
            self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", error_msg, log_level="ERROR")
            print(error_msg)
            # Considerar un fallback a un agente genérico si existe
            generic_def = self.agente_definitions.get("generico") # Asumiendo una definición 'generico.json'
            if generic_def:
                 definition = generic_def
                 agent_type = "generico"
                 self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Usando definición genérica para agente '{agent_type}'", log_level="WARNING")
            else:
                 # Reportar al Master que no se pudo lanzar el agente (si GestorEnjambre puede hacerlo)
                 # self.orquestador_master_svc.report_swarm_event("gestor_enjambre", f"No se pudo lanzar agente {agent_type}: definición no encontrada.")
                 return # No se puede lanzar el agente si no hay definición ni fallback

        # Generar un ID único para el agente
        agent_id = f"{agent_type}_{int(time.time())}_{len(self.agentes_activos) + 1}"
        self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Generado ID para nuevo agente: {agent_id}")


        rol = definition["rol"]
        objetivo = definition["objetivo"]
        instruction_prompt_file = definition["instruction_prompt_file"]
        available_tools_names = definition["available_tools"]

        from servicios.bucle_logico_agente import \
            AgenteExecutionLoop  # Importar aquí para evitar la importación circular

        # Crear una nueva instancia del Agente (solo el estado, historial empieza vacío)
        agente = Agente(nombre=agent_id, rol=rol, objetivo=objetivo)
        self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Instancia Agente creada: {agent_id} ({rol})")

        # Registrar el inicio de la ejecución del agente en los logs
        self.gestor_logs_svc.iniciar_ejecucion_agente(agent_id, agent_type, rol, objetivo, task_description)


        # Crear una nueva instancia del bucle lógico del agente
        loop = AgenteExecutionLoop(
            agente=agente,
            ejecutor_consola_svc=self.ejecutor_consola_svc,
            gestor_logs_svc=self.gestor_logs_svc,
            gestor_enjambre_svc=self, # Pasar la referencia a sí mismo para que el bucle pueda reportar
            tarea_inicial=task_description,
            instruction_prompt_path=os.path.join("prompts", instruction_prompt_file), # Construir la ruta completa
            available_tools_names=available_tools_names
        )
        self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Instancia BucleLogicoAgente creada para {agent_id}.")

        # --- Iniciar la ejecución del bucle en un hilo separado ---
        thread = threading.Thread(target=loop.run)
        thread.daemon = True # Permite que el programa principal salga aunque los hilos estén corriendo
        thread.start()

        # Registrar el agente y su hilo como activos
        with self.agente_status_lock:
            self.agentes_activos[agent_id] = loop # Guardar la instancia del loop
            self.agente_threads[agent_id] = thread
            self.agentes_status[agent_id] = "started" # Registrar estado local en el gestor

        self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Ejecución asíncrona iniciada para {agent_id} en hilo {thread.name}.")


    # --- Métodos para que AgenteExecutionLoop reporte estado/resultados ---
    # Llamados por AgenteExecutionLoop cuando un agente termina o reporta un problema
    def report_agent_status(self, agent_id: str, status: str, result: Optional[str] = None):
        """Recibe el estado final o resultado de un agente que ha terminado."""
        with self.agente_status_lock:
            self.agentes_status[agent_id] = status
            if result is not None:
                 self.agentes_resultados[agent_id] = result
            self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Agente {agent_id} reporta estado: {status}", details={"result": result})
            # Opcional: Remover agente de activos si ha terminado completamente
            # if status in ["completed", "failed", "fatal_error", "max_iterations"]:
            #      self.agentes_activos.pop(agent_id, None)
            #      self.agente_threads.pop(agent_id, None)


    def report_agent_problem(self, agent_id: str, problem_description: str):
        """Recibe la notificación de un problema por parte de un agente."""
        with self.agente_status_lock:
            self.agentes_status[agent_id] = "paused" # El bucle ya se marcó como paused
            self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Agente {agent_id} reporta problema: {problem_description}", log_level="WARNING")

        # --- Notificar al Agente Master ---
        # Esto se hace inyectando un mensaje en el historial del Master
        notification_message = SystemMessage(
             content=f"[Notificación del Sistema de Enjambre]: El agente {agent_id} ({self.agentes_activos[agent_id].agente.rol}) ha reportado un problema: {problem_description}. Está pausado esperando intervención."
        )
        self.orquestador_master_svc.add_message_to_history(notification_message)
        self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Problema de {agent_id} notificado al Master.", details={"problem": problem_description})

        # TODO: Implementar un mecanismo en main.py para asegurarse de que el Master
        # tenga una oportunidad de procesar su historial y ver esta notificación pronto.


    # --- Método para el Master enviar mensaje a un agente ---
    # Llamado por main.py (que intercepta la tool_call 'send_message_to_agent' del Master)
    def send_message_to_agent(self, agent_id: str, message_content: str):
        """Busca un agente activo por ID e inyecta un mensaje para reanudarlo si está pausado."""
        with self.agente_status_lock:
            loop_instance = self.agentes_activos.get(agent_id)
            current_status = self.agentes_status.get(agent_id)

        if loop_instance and current_status in ["started", "running", "paused"]:
             self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", f"Enviando mensaje a agente {agent_id}. Estado: {current_status}", details={"message": message_content})
             loop_instance.inject_message_and_resume(message_content) # Llama al método del bucle
        elif loop_instance and current_status in ["completed", "failed", "fatal_error", "max_iterations"]:
             error_msg = f"No se puede enviar mensaje al agente {agent_id}. Ya ha finalizado con estado: {current_status}."
             self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", error_msg, log_level="WARNING")
             # Opcional: Reportar este error al Master inyectando un mensaje en su historial
             # self.orquestador_master_svc.add_message_to_history(SystemMessage(content=f"[Notificación del Sistema de Enjambre]: Falló el envío de mensaje al agente {agent_id}: {error_msg}"))

        else:
             error_msg = f"No se puede enviar mensaje. Agente {agent_id} no encontrado o no está activo."
             self.gestor_logs_svc.log_event("swarm_management", "gestor_enjambre", error_msg, log_level="ERROR")
             # Opcional: Reportar este error al Master

    # --- Métodos de consulta ---
    def get_agent_status(self, agent_id: str) -> Optional[str]:
        """Obtiene el último estado reportado de un agente."""
        with self.agente_status_lock:
            return self.agentes_status.get(agent_id)

    def get_all_agents_status(self) -> Dict[str, str]:
        """Obtiene el estado de todos los agentes gestionados."""
        with self.agente_status_lock:
            # Devuelve una copia para evitar modificar el dict interno desde fuera
            return self.agentes_status.copy()

    # TODO: Método para recolectar resultados finales de agentes completados
    #       El main.py podría llamarlo después de que todos los agentes terminen.
    #       def collect_final_results(self): ...


    # TODO: Método para esperar a que todos los agentes terminen (para main.py)
    #       def wait_for_all_agents(self): ... (Necesita join() en los hilos)