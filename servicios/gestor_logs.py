# servicios/gestor_logs.py
import datetime
import json  # Importar json para los detalles, aunque tu versión simple no lo usa en BD
import os
import sqlite3
from typing import Any, Dict, Optional

# Definir la ruta de la BD
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "swarm.db")

def crear_directorio_si_no_existe(ruta):
    if not os.path.exists(ruta):
        os.makedirs(ruta, exist_ok=True) # Usar exist_ok=True para evitar race condition simple

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
                tipo TEXT, -- Ej: llm_input, llm_output, tool_execution, agent_state, master_delegation
                agente_id TEXT, -- ID del agente o 'master'
                mensaje TEXT, -- Descripción corta del evento
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details TEXT -- Campo para JSON string (para output LLM, tool args/results, etc.)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE, -- Hacer UNIQUE si agent_id es el identificador principal
                agent_type TEXT,
                agent_rol TEXT,
                agent_objetivo TEXT,
                task_description TEXT,
                start_time DATETIME,
                end_time DATETIME NULL,
                status TEXT -- started, completed, failed, max_iterations
            )
        """)
        # No necesita commit con isolation_level=None

    # --- Métodos de Loggeo General (adaptados a tu estructura simple) ---
    def log_event(self, tipo: str, agente_id: str, mensaje: str, details: Optional[Dict[str, Any]] = None):
        """Registra un evento general en la base de datos."""
        details_json = json.dumps(details) if details is not None else None
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO logs (tipo, agente_id, mensaje, details) VALUES (?, ?, ?, ?)",
                (tipo, agente_id, mensaje, details_json)
            )
            # No necesita commit con isolation_level=None
        except Exception as e:
             print(f"Error logging event (type: {tipo}, agent: {agente_id}): {e}") # Log error to console


    # --- Métodos de Loggeo Específicos ---

    def iniciar_ejecucion_agente(self, agent_id: str, agent_type: str, rol: str, objetivo: str, task_description: str):
        """Registra el inicio de la ejecución de un agente."""
        start_time = datetime.datetime.now()
        try:
            cursor = self.conn.cursor()
            # Usar INSERT OR IGNORE si asumes que agent_id es único por run
            cursor.execute(
                "INSERT INTO agent_runs (agent_id, agent_type, agent_rol, agent_objetivo, task_description, start_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, agent_type, rol, objetivo, task_description, start_time, "started")
            )
        except Exception as e:
             print(f"Error al registrar inicio de agente {agent_id}: {e}")

        self.log_event("agent_run_start", agent_id, f"Inicio de ejecución: {rol} ({objetivo})", details={"agent_type": agent_type, "task_description": task_description})


    def finalizar_ejecucion_agente(self, agent_id: str, status: str, final_result: Optional[str] = None):
        """Registra la finalización de la ejecución de un agente."""
        end_time = datetime.datetime.now()
        try:
            cursor = self.conn.cursor()
            # Actualizar solo si el status es 'running' para evitar sobrescribir fallos/completados
            cursor.execute(
                "UPDATE agent_runs SET end_time = ?, status = ? WHERE agent_id = ? AND status = 'started'",
                (end_time, status, agent_id)
            )
            # Si no se actualizó (ej: ya estaba fallido), insertar una entrada de finalización duplicada si es necesario
            if cursor.rowcount == 0:
                 print(f"Advertencia: No se encontró agent_run 'started' para actualizar {agent_id}. Registrando fin con nuevo log.")
                 # Podrías loggear un evento de fin adicional aquí si la actualización falla
        except Exception as e:
             print(f"Error al registrar fin de agente {agent_id}: {e}")

        message = f"Ejecución finalizada con estado: {status}"
        details: Dict[str, Any] = {"final_status": status}
        if final_result:
            message += f". Resultado: {final_result[:200]}..." # Truncar resultado para log simple
            details["final_result_snippet"] = final_result[:500] # Guardar un snippet en details
        self.log_event("agent_run_end", agent_id, message, log_level="INFO" if status=="completed" else "ERROR", details=details)


    def log_llm_interaction(self, agent_id: str, input_content: Any, output_content: Any):
        """Registra la interacción con el LLM (input y output)."""
        # Para logs simples, convertir a string. Para detalles, usar campo details.
        input_str = str(input_content) # Puede ser lista de mensajes, mejor serializar o snippet
        output_str = str(output_content) # Puede ser AIMessage, ToolCall, etc.

        self.log_event(
            "llm_input",
            agent_id,
            f"Input LLM ({len(input_str)} chars): {input_str[:100]}...", # Log snippet
            details={"full_input": input_str} # Log full input in details
        )

        output_details: Dict[str, Any] = {"content": output_str}
        event_type = "llm_output"
        # Intenta añadir detalles estructurados si es posible (para tool_calls)
        try:
            if hasattr(output_content, 'additional_kwargs'):
                 output_details["additional_kwargs"] = output_content.additional_kwargs
                 if 'tool_calls' in output_content.additional_kwargs:
                      event_type = "llm_output_tool_call"
            # Puedes añadir más casos para otros tipos de mensajes si es necesario
        except Exception:
            pass # Ignore errors during detail logging


        self.log_event(
            event_type,
            agent_id,
            f"Output LLM ({len(output_str)} chars): {output_str[:100]}...", # Log snippet
            details=output_details # Log details
        )


    def log_tool_execution(self, agent_id: str, tool_name: str, command: str, stdout: str, stderr: str, return_code: int, tool_call_id: Optional[str] = None):
         """Registra la ejecución de una herramienta y su resultado."""
         self.log_event(
             "tool_execution",
             agent_id,
             f"Tool Exec: {tool_name}, Cmd: {command[:50]}...",
             details={
                 "tool_name": tool_name,
                 "command": command,
                 "stdout": stdout,
                 "stderr": stderr,
                 "return_code": return_code,
                 "tool_call_id": tool_call_id
             }
         )
         # Podrías loggear el resultado crudo también si es importante
         # self.log_event("tool_result_raw", agent_id, "Resultado crudo", details={"stdout":stdout, "stderr":stderr})


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