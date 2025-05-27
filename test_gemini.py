import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

def test_gemini():
    """
    Prueba la conexión a Gemini con el modelo y la API key de .env.
    """
    model = os.getenv("MODEL", "gemini-2.0-flash-lite-preview-02-05")
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return "Error: GOOGLE_API_KEY no definida en .env"

    try:
        llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0.0)
        response = llm.invoke("Hola, soy un test.")
        return f"Conexión exitosa. Respuesta: {response.content}"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    resultado = test_gemini()
    print(resultado)
