import os

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
        raise ValueError("La variable de entorno GOOGLE_API_KEY no está definida.")
    if not model:
        raise ValueError("La variable de entorno MODEL no está definida.")
    llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0.0)
    return llm

if __name__ == '__main__':
    try:
        llm = cargar_llm()
        print("LLM cargado exitosamente.")
        # Puedes probar el LLM aquí, por ejemplo:
        response = llm.invoke("Hola, ¿cómo estás?")
        print(response.content)
    except ValueError as e:
        print(f"Error al cargar el LLM: {e}")
