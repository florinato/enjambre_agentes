import os
import sys

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI


def cargar_llm():
    """
    Inicializa y devuelve una instancia de ChatGoogleGenerativeAI.
    """
    # Cargar variables de entorno siempre que se llame la función
    load_dotenv(override=True)
    model = os.getenv("MODEL")
    api_key = os.getenv("GOOGLE_API_KEY")
    print("Modelo cargado desde .env:", model)
    print("API KEY cargada:", "Sí" if api_key else "No")  # Para depuración
    print(f"model: {model}")

    if not api_key:
        print("Error: La variable de entorno GOOGLE_API_KEY no está definida.")
        return None
    if not model:
        print("Error: La variable de entorno MODEL no está definida.")
        return None
    try:
        llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0.0)
        print(f"[DEBUG] LLM cargado. Tipo: {type(llm)}, Valor: {llm}")
        return llm
    except Exception as e:
        import traceback
        print(f"[ERROR] Error al cargar el LLM: {e}")
        print(traceback.format_exc())
        return None

if __name__ == '__main__':
    try:
        llm = cargar_llm()
        if llm:
            print("LLM cargado exitosamente.")
            response = llm.invoke("Hola, ¿cómo estás?")
            print(response.content)
        else:
            print("No se pudo cargar el LLM.")
    except ValueError as e:
        print(f"Error al cargar el LLM: {e}")
