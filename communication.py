# communication.py
import re

COMMUNICATION_PROMPTS_FILE = "prompts/communication_prompts.txt"
with open(COMMUNICATION_PROMPTS_FILE, "r") as f:
    lines = f.readlines()
    CONSULTA_USUARIO_FORMAT = lines[0].split(': ')[1].strip()
    RESPUESTA_USUARIO_FORMAT = lines[1].split(': ')[1].strip()
    CONSULTA_SISTEMA_FORMAT = lines[2].split(': ')[1].strip()
    RESPUESTA_SISTEMA_FORMAT = lines[3].split(': ')[1].strip()
    PARSE_MESSAGE_PATTERN = lines[4].strip()

def create_consulta_usuario(message: str) -> str:
    """Formato para una consulta del usuario."""
    return CONSULTA_USUARIO_FORMAT.format(message=message)

def create_respuesta_usuario(message: str) -> str:
    """Formato para la respuesta al usuario."""
    return RESPUESTA_USUARIO_FORMAT.format(message=message)

def create_consulta_sistema(command: str) -> str:
    """Formato para la consulta al sistema (ej: mongo)."""
    return CONSULTA_SISTEMA_FORMAT.format(command=command) # ADAPTAR ESTO

def create_respuesta_sistema(output: str) -> str:
    """Formato para la respuesta del sistema (ej: mongo)."""
    return RESPUESTA_SISTEMA_FORMAT.format(output=output) # ADAPTAR ESTO

def parse_message(message: str):
    """
    Parsea un mensaje con formato 'etiqueta: contenido' y devuelve la tupla (etiqueta, contenido).
    Si no se encuentra el separador, devuelve (None, message).
    Parsea un mensaje buscando 'etiqueta: contenido' (etiqueta siendo 'consulta mongo' o 'respuesta usuario').
    Ignora texto previo a la etiqueta (como timestamps).
    Si no se encuentra el patrón, devuelve (None, message).
    """

    # Buscar el patrón 'etiqueta: contenido', permitiendo texto antes
    # Se busca 'consulta mongo:' o 'respuesta usuario:' seguido de ':' y el resto
    match = re.search(PARSE_MESSAGE_PATTERN, message, re.DOTALL) # ADAPTAR ESTO

    if match:
        label = match.group(1).strip() # La etiqueta encontrada
        content = match.group(2).strip() # El contenido después de ':'
        return label, content
    else:
        # Si no se encuentra el patrón específico, devolver None y el mensaje original
        return None, message
