# model_integration.py
import json  # Import the json library
import os
import re  # Import the re library for regex
from typing import Dict, List, Optional, Tuple  # Add Tuple

import requests
from dotenv import load_dotenv
from langchain.llms.base import LLM

import logging_manager  # Importar para usar log_debug

load_dotenv()  # Carga las variables de entorno
API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiLLM(LLM):
    model_name: str = "gemini-2.0-flash-001"
    api_key: str = API_KEY
    # Suponemos un endpoint para la API de Gemini; ajústalo según la documentación real.
    endpoint: str = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-001:generateContent"

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "gemini_custom"

    @property
    def _identifying_params(self) -> Dict:
        return {"model_name": self.model_name}

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "contents": [{
                "parts": [{
                    "text": prompt # Use the modified prompt here
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": 512
            }
        }
        params = {
            "key": self.api_key
        }
        logging_manager.log_debug("Prompt Enviado", prompt) # Log modified prompt
        response = requests.post(self.endpoint, headers=headers, json=data, params=params)
        response.raise_for_status()
        result = response.json()

        # Extract the raw text response
        raw_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        logging_manager.log_debug("Respuesta Cruda Modelo", raw_text) # Log raw response

        # Clean and parse the response
        cleaned_text = self._clean_and_parse_response(raw_text)
        logging_manager.log_debug("Respuesta Limpia Modelo", cleaned_text) # Log cleaned response
        return cleaned_text

    def _clean_and_parse_response(self, raw_text: str) -> str:
        """
        Cleans the raw text response from Gemini robustly.
        Prioritizes finding the label and extracts the content.
        """
        text = raw_text.strip()

        # Find the first valid label, ignoring potential fences around it.
        # This regex allows for multiple spaces between the label and content,
        # and handles labels with alphanumeric characters and underscores.
        match = re.search(r"([\w\s]+):\s*(.*)", text, re.IGNORECASE)

        if match:
            label = match.group(1).strip()
            content = match.group(2).strip()

            # Clean residual markdown fences from the extracted content
            content = re.sub(r"```", "", content).strip()

            return f"{label}: {content}"
        else:
            return f"Respuesta: {text}"

# La función get_model_response ya no es necesaria,
# Langchain ConversationChain se encarga de la interacción con el LLM.
