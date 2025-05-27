# prompts/tool_definitions.py
from typing import (  # Importar para type hints en herramientas si los argumentos son complejos
    Any, Dict)

from langchain_core.tools import tool

# --- Herramientas para Agentes del Enjambre ---

@tool
def ejecutar_comando_consola(command: str) -> str:
    """
    Ejecuta un comando en la consola del sistema dentro del contenedor.
    La entrada esperada es un string con el comando completo a ejecutar.
    Retorna un string JSON con la salida estándar ('salida'), error estándar ('error') y código de retorno ('codigo') del comando.
    """
    # La implementación REAL está en servicios/ejecutor_consola.py.
    pass

@tool
def reportar_resultado_final(resultado: str) -> str:
    """
    Reporta el resultado final conciso de la tarea que el agente ha completado al sistema.
    Usa esta herramienta CUANDO LA TAREA ASIGNADA ESTÉ TOTALMENTE FINALIZADA Y TENGAS EL RESULTADO LISTO para ser entregado.
    La entrada esperada es un string conciso con el resultado o resumen final de la tarea.
    Esta acción finaliza la ejecución del agente exitosamente.
    """
    # El BUCLE LOGICO detecta esta llamada y termina la ejecución del agente,
    # pasando el 'resultado' al GestorEnjambre.
    pass

@tool
def reportar_problema(descripcion_problema: str) -> str:
    """
    Reporta al sistema que el agente ha encontrado un problema que le impide continuar con su tarea.
    Usa esta herramienta cuando estés atascado y no puedas resolver un problema por ti mismo (ej: permisos denegados, herramienta no funciona como esperas, información faltante).
    La entrada esperada es una descripción clara y concisa del problema.
    Esta acción pausará la ejecución del agente y notificará al Agente Master.
    """
    # El BUCLE LOGICO detecta esta llamada, pausa el agente y notifica al GestorEnjambre/Master.
    pass

# TODO: Añadir otras definiciones de herramientas aquí (ej: navegacion)


# --- Herramientas para el Agente Master ---

@tool
def delegate_task(agent_type: str, task_description: str) -> str:
    """
    Delega una sub-tarea a un agente especializado del enjambre para su ejecución.
    Usa esta herramienta para romper una tarea grande en sub-tareas y asignarlas a otros agentes.
    Argumentos:
    - agent_type: El tipo de agente a lanzar (ej: 'ejecutor', 'analista'). Debe ser uno de los tipos definidos en el sistema.
    - task_description: Una descripción CLARA Y ESPECÍFICA de la sub-tarea que el agente delegado debe realizar. Esta será la instrucción principal para el agente delegado.
    Retorna un string indicando que la delegación fue solicitada.
    """
    # El Master genera la llamada a esta herramienta.
    # main.py o GestorEnjambre intercepta esta llamada del Master y lanza el agente.
    pass

@tool
def send_message_to_agent(agent_id: str, message_content: str) -> str:
    """
    Envía un mensaje o una nueva instrucción a un agente del enjambre específico que está activo o pausado.
    Usa esta herramienta para intervenir en la ejecución de un agente, darle una pista, reformular una tarea, o ayudarle a resolver un problema.
    Argumentos:
    - agent_id: El ID del agente del enjambre al que se le enviará el mensaje.
    - message_content: El contenido del mensaje o la nueva instrucción para el agente.
    """
    # El Master genera la llamada a esta herramienta.
    # main.py o GestorEnjambre intercepta esta llamada y busca el agente por ID para inyectarle el mensaje y reanudarlo.
    pass


# Listas de herramientas para bindeo (conveniente)
SWARM_AGENT_TOOLS = [ejecutar_comando_consola, reportar_resultado_final, reportar_problema]
MASTER_AGENT_TOOLS = [delegate_task, send_message_to_agent]
