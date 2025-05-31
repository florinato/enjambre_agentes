from typing import List

# Ensure necessary BaseMessage and specific message types are imported
# Prefer imports from langchain_core.messages
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage)

from servicios.cargar_llm import cargar_llm

# Remove ChatGoogleGenerativeAI if not directly used here, but cargar_llm uses it.
# from langchain_google_genai import ChatGoogleGenerativeAI



class Agente:
    def __init__(self, nombre: str, rol: str, objetivo: str, historial_conversacion: List[BaseMessage] = None, tokens_utilizados: int = 0):
        self.nombre = nombre
        self.rol = rol
        self.objetivo = objetivo
        # Initialize history as an empty list if None is passed
        self.historial_conversacion: List[BaseMessage] = [] if historial_conversacion is None else historial_conversacion
        self.tokens_utilizados = tokens_utilizados
        self.modelo = cargar_llm()  # Obtener el LLM del servicio

    def add_message_to_history(self, message: BaseMessage):
        """Añade un mensaje al historial de la conversación."""
        self.historial_conversacion.append(message)

    def get_history(self) -> List[BaseMessage]:
        """Obtiene el historial de la conversación."""
        return self.historial_conversacion
    def clear_history(self):
        """Limpia el historial de la conversación."""
        self.historial_conversacion = []
    def get_tokens_utilizados(self) -> int:
        """Obtiene el número de tokens utilizados."""
        return self.tokens_utilizados