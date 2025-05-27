from typing import List

from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage)
from langchain_google_genai import ChatGoogleGenerativeAI

from servicios.cargar_llm import cargar_llm


class Agente:
    def __init__(self, nombre: str, rol: str, objetivo: str, historial_conversacion: List = [], tokens_utilizados: int = 0):
        self.nombre = nombre
        self.rol = rol
        self.objetivo = objetivo
        self.historial_conversacion = historial_conversacion
        self.tokens_utilizados = tokens_utilizados
        self.modelo = cargar_llm()  # Obtener el LLM del servicio
        self.memory = ConversationBufferMemory(memory_key="history", human_prefix="consulta usuario", ai_prefix="respuesta modelo")
        self.conversation = ConversationChain(
            llm=self.modelo,
            memory=self.memory,
            verbose=False,
        )

    def add_message_to_history(self, message):
        """Añade un mensaje al historial de la conversación."""
        self.historial_conversacion.append(message)
        if isinstance(message, HumanMessage):
            self.memory.save_context({"input": message.content}, {"output": ""}) # Guardar el input en la memoria
        elif isinstance(message, AIMessage):
            self.memory.save_context({"input": ""}, {"output": message.content}) # Guardar el output en la memoria

    def get_history(self):
        """Obtiene el historial de la conversación."""
        return self.historial_conversacion
