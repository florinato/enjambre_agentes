# servicios/gestor_logs.py
# servicios/gestor_logs.py
import datetime
import json  # Importar json para el campo details
import os
import sqlite3
from typing import Any, Dict, Optional  # Importar para type hints

# Importar mensajes de LangChain (ajusta el import si usas otro paquete)
from langchain.schema import (AIMessage, BaseMessage, HumanMessage,
                              SystemMessage)

# Definir la ruta de la BD
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "swarm.db")

def crear_directorio_si_no_existe(ruta):
    # Usar exist_ok=True para evitar errores si el directorio ya existe
    if not os.path.exists(ruta):
        os.makedirs(ruta, exist_ok=True)

class GestorLogs:
    def __init__(self, db_path=DB_FILE):
        # Asegurar el directorio ANTES de conectar
        crear_directorio_si_no_existe(os.path.dirname(db_path))
        # isolation_level=None para autocommit
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self._crear_tablas()
        print(f"--- GestorLogs inicializado. DB: {db_path} ---")

    def _crear_tablas(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP, -- Usar default SQLite
                agente_id TEXT,
                tipo TEXT, -- Ej: llm_input, llm_output, tool_execution, agent_state, master_delegation
                log_level TEXT, -- INFO, DEBUG, ERROR, WARNING, FATAL
                mensaje TEXT, -- Descripción corta del evento
                details TEXT -- JSON string para detalles estructurados
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE, -- UNIQUE si agent_id identifica la ejecución
                agent_type TEXT,
                agent_rol TEXT,
                agent_objetivo TEXT,
                task_description TEXT,
                start_time DATETIME,
                end_time DATETIME NULL,
                status TEXT -- started, running, paused, completed, failed, max_iterations
            )
        """)
        # No necesita commit con isolation_level=None

    # --- Métodos de Loggeo General (AHORA ACEPTA log_level y details) ---
    def log_event(self, tipo: str, agente_id: str, mensaje: str, log_level: str = "INFO", details: Optional[Dict[str, Any]] = None):
        """Registra un evento general en la base de datos."""
        # timestamp se genera por defecto en la BD
        details_json = json.dumps(details) if details is not None else None
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO logs (tipo, agente_id, mensaje, log_level, details) VALUES (?, ?, ?, ?, ?)",
                (tipo, agente_id, mensaje, log_level.upper(), details_json) # Guardar log_level en mayúsculas
            )
            # No necesita commit con isolation_level=None
        except Exception as e:
             # Imprimir error de loggeo a consola si falla la BD
             print(f"Error logging event (type: {tipo}, agent: {agente_id}, level: {log_level}): {e}")
             # Opcional: Fallback a loggear a archivo de texto si la BD falla persistentemente


    # --- Métodos de Loggeo Específicos (AHORA PASAN log_level y details a log_event) ---

    def iniciar_ejecucion_agente(self, agent_id: str, agent_type: str, rol: str, objetivo: str, task_description: str):
        """Registra el inicio de la ejecución de un agente."""
        start_time = datetime.datetime.now()
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO agent_runs (agent_id, agent_type, agent_rol, agent_objetivo, task_description, start_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, agent_type, rol, objetivo, task_description, start_time, "started")
            )
            # Usar INSERT OR IGNORE para evitar errores si el ID ya existe (aunque no debería con el timestamp)
        except Exception as e:
             print(f"Error al registrar inicio de agente {agent_id}: {e}")

        # Loguear también en la tabla logs con detalles
        self.log_event(
            "agent_run_start",
            agent_id,
            f"Inicio de ejecución: {rol} ({objetivo})",
            log_level="INFO",
            details={"agent_type": agent_type, "task_description": task_description}
        )


    def finalizar_ejecucion_agente(self, agent_id: str, status: str, final_result: Optional[str] = None):
        """Registra la finalización de la ejecución de un agente."""
        end_time = datetime.datetime.now()
        try:
            cursor = self.conn.cursor()
            # Actualizar solo si el status es 'started' o 'running'
            cursor.execute(
                "UPDATE agent_runs SET end_time = ?, status = ? WHERE agent_id = ? AND status IN ('started', 'running', 'paused')",
                (end_time, status, agent_id)
            )
            if cursor.rowcount == 0:
                 print(f"Advertencia: No se encontró agent_run 'started/running/paused' para actualizar {agent_id}. Registrando fin con nuevo log event.")
                 # Loggear un evento de fin adicional si la actualización falla
                 self.log_event("agent_run_end_update_failed", agent_id, f"Falló actualizar fin de agente {agent_id}", log_level="WARNING", details={"final_status_attempted": status})


        except Exception as e:
             print(f"Error al registrar fin de agente {agent_id}: {e}")

        # Loguear también en la tabla logs con detalles
        message = f"Ejecución finalizada con estado: {status}"
        details: Dict[str, Any] = {"final_status": status}
        if final_result:
            message += f". Resultado: {final_result[:100]}..." # Truncar resultado para log simple
            details["final_result_snippet"] = final_result[:500] # Guardar un snippet en details (o completo si el campo details es grande)

        log_level = "INFO"
        if status in ["failed", "fatal_error"]:
             log_level = "ERROR"
        elif status in ["max_iterations", "warning_state"]: # Si defines otros estados de advertencia
             log_level = "WARNING"

        self.log_event("agent_run_end", agent_id, message, log_level=log_level, details=details)


    # Adaptado para aceptar Any para input/output que pueden ser listas de mensajes u objetos AIMessage/ToolCall
    def log_llm_interaction(self, agent_id: str, input_content: Any, output_content: Any):
        """Registra la interacción con el LLM (input y output)."""
        # Intentar serializar o representar el input (lista de mensajes) y output (BaseMessage)
        input_repr = str(input_content) # Default representation
        output_repr = str(output_content)

        input_details: Dict[str, Any] = {}
        if isinstance(input_content, list): # Si es una lista de mensajes
             # Puedes loguear solo el último mensaje o una representación concisa
             input_repr = f"Historial con {len(input_content)} mensajes. Último: {str(input_content[-1])[:100]}..." if input_content else "Historial vacío"
             # Loguear el historial completo en details (puede ser muy grande)
             input_details["full_history_repr"] = [str(msg) for msg in input_content] # Guardar string representation de mensajes


        output_details: Dict[str, Any] = {"raw_output_repr": output_repr}
        event_type = "llm_output"
        # Intentar añadir detalles estructurados si es posible (para tool_calls)
        try:
            # Verifica si es un tipo de mensaje de LangChain y si tiene additional_kwargs/tool_calls
            if hasattr(output_content, 'additional_kwargs'):
                 output_details["additional_kwargs"] = output_content.additional_kwargs
                 if 'tool_calls' in output_content.additional_kwargs:
                      event_type = "llm_output_tool_call"
            # Puedes añadir más casos para otros tipos de mensajes si es necesario (ej: ChatMessage)
        except Exception:
            pass # Ignorar errores al extraer detalles


        self.log_event(
            "llm_input",
            agent_id,
            f"Input LLM ({len(input_repr)} chars): {input_repr[:100]}...", # Log snippet
            log_level="DEBUG", # Nivel DEBUG para inputs completos
            details=input_details # Log full input/history in details
        )

        self.log_event(
            event_type,
            agent_id,
            f"Output LLM ({len(output_repr)} chars): {output_repr[:100]}...", # Log snippet
            log_level="DEBUG" if event_type == "llm_output" else "INFO", # Tool calls son INFO, texto normal DEBUG
            details=output_details # Log details
        )


    # Adaptado para aceptar tool_call_id y pasar más detalles
    def log_tool_execution(self, agent_id: str, tool_name: str, command: str, stdout: str, stderr: str, return_code: int, tool_call_id: Optional[str] = None):
         """Registra la ejecución de una herramienta (ej: consola) y su resultado."""
         self.log_event(
             "tool_execution",
             agent_id,
             f"Tool Exec: {tool_name}, Cmd: {command[:50]}...",
             log_level="INFO" if return_code == 0 else "ERROR", # INFO si éxito, ERROR si falla
             details={
                 "tool_name": tool_name,
                 "command": command,
                 "stdout": stdout,
                 "stderr": stderr,
                 "return_code": return_code,
                 "tool_call_id": tool_call_id
             }
         )


    # Añadido método específico para loggear el resultado AÑADIDO al historial como ToolMessage
    def log_tool_result_added(self, agent_id: str, tool_name: str, tool_call_id: str, content_snippet: str):
        """Registra que el resultado de una herramienta fue añadido al historial."""
        self.log_event(
            "tool_result_added",
            agent_id,
            f"Resultado de {tool_name} añadido a historial.",
            log_level="DEBUG",
            details={"tool_name": tool_name, "tool_call_id": tool_call_id, "content_snippet": content_snippet}
        )


    # Añadido método para loggear el reporte de problema por un agente
    def log_agent_problem_reported(self, agent_id: str, problem_description: str):
        """Registra que un agente ha reportado un problema."""
        self.log_event(
            "agent_problem_reported",
            agent_id,
            f"Agente reporta problema: {problem_description[:100]}...",
            log_level="WARNING", # Los problemas son WARNINGs
            details={"description": problem_description}
        )

    # TODO: Añadir métodos para consultar logs para depuración

# Ejemplo de uso (mantener para pruebas individuales)
if __name__ == '__main__':
    print("--- Prueba básica de GestorLogs (Actualizado) ---")
    # Asegurar que el directorio 'data' existe para la prueba
    crear_directorio_si_no_existe(DB_DIR)

    logs = GestorLogs()
    agent_id_test = "test_agent_456"
    task_desc_test = "Probar el logging avanzado."

    logs.iniciar_ejecucion_agente(agent_id_test, "tester_v2", "Probar logging avanzado", "Probar logging avanzado")
    logs.log_event("test_event", agent_id_test, "Mensaje de prueba general con detalles", log_level="INFO", details={"key1": "value1", "number": 123})
    logs.log_event("debug_info", agent_id_test, "Mensaje de depuración", log_level="DEBUG")
    logs.log_tool_execution(agent_id_test, "consola", "ls -l", "salida ok", "", 0, "call_def")
    logs.log_tool_execution(agent_id_test, "consola", "rm /nonexistent", "", "No such file", 1, "call_ghi")
    logs.log_agent_problem_reported(agent_id_test, "No pude borrar el archivo porque no existe.")

    # Simular interacción LLM
    input_msgs = [SystemMessage(content="Inst"), HumanMessage(content="Task"), AIMessage(content="Ok, use tool")]
    output_tc = AIMessage(content="", additional_kwargs={"tool_calls":[{"function":{"name":"tool1","arguments":"{}"},"id":"call1"}]})
    output_text = AIMessage(content="Done.")

    logs.log_llm_interaction(agent_id_test, input_msgs, output_tc)
    logs.log_tool_result_added(agent_id_test, "tool1", "call1", json.dumps({"status": "success"}))
    logs.log_llm_interaction(agent_id_test, input_msgs + [output_tc, SystemMessage(content="...", tool_call_id="call1")], output_text)


    logs.finalizar_ejecucion_agente(agent_id_test, "completed", "Prueba de logging avanzada completada.")
    print("Logs de prueba avanzada generados en swarm.db.")


# Ejemplo de uso (mantener para pruebas individuales)
if __name__ == '__main__':
    print("--- Prueba básica de GestorLogs ---")
    # Asegurar que el directorio 'data' existe para la prueba
    crear_directorio_si_no_existe(DB_DIR)

    logs = GestorLogs()
    agent_id = "test_agent_123"
    task_desc = "Probar la ejecución y el loggeo."

    logs.iniciar_ejecucion_agente(agent_id, "tester", "Probar el logging", task_desc)
    logs.log_event("test_event", agent_id, "Mensaje de prueba general", details={"key": "value"})
    logs.log_tool_execution(agent_id, "consola", "ls -l", "total 1\n-rw-r--r-- 1 user user 0 jan 1 00:00 file", "", 0, "call_abc")
    logs.log_llm_interaction(agent_id, "system message + human message", "AI response with tool_call") # Simular
    logs.log_llm_interaction(agent_id, "system message + human message + AI with tool_call + Tool result", "AI response text") # Simular
    logs.finalizar_ejecucion_agente(agent_id, "completed", "Prueba completada con éxito.")
    print("Logs de prueba generados en swarm.db.")

    # Para verificar los logs, usa una herramienta SQLite externa o añade funciones de consulta aquí.
