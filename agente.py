# agente_plantilla.py
import os
import re

# Local imports (a adaptar)
import communication
import executor
import logging_manager
import security
from model_integration import GeminiLLM  # Importar la clase LLM directamente

# Definir la plantilla del prompt para Langchain (ADAPTAR ESTO)
PROMPT_FILE = "prompts/agente_prompt.txt"
with open(PROMPT_FILE, "r") as f:
    TEMPLATE = f.read()

# Inicializar LLM, Memoria y Cadena de Conversación
# Adaptar la inicialización del LLM si es necesario
llm = GeminiLLM()

def main():
    # Inicializar LLM, Memoria y Cadena de Conversación
    llm = GeminiLLM()
    memory = ConversationBufferMemory(memory_key="history", human_prefix="consulta usuario", ai_prefix="respuesta modelo") # Usar prefijos personalizados si es necesario
    conversation = ConversationChain(
        llm=llm,
        prompt=PROMPT,
        verbose=False, # Poner a True para ver el prompt completo enviado a Langchain
        memory=memory
    )

    log_file_path = os.path.abspath(logging_manager.LOG_FILE)
    print("Agente [Nombre del Agente] con Gemini (Langchain): Iniciando sesión...")
    print(f"Las interacciones de depuración se guardarán en: {log_file_path}")

    # Bucle principal de interacción con el usuario
    while True:
        user_query = input("Ingrese su consulta (o 'salir' para terminar): ")
        if user_query.lower() == 'salir':
            print("Finalizando sesión.")
            break

        logging_manager.log_debug("User Query", user_query)

        # Variable para pasar la entrada al modelo en cada iteración
        current_input = user_query
        is_first_iteration = True

        # Bucle de iteración autónoma para una consulta de usuario
        while True:
            # Determinar el prefijo correcto para la memoria basado en si es la consulta inicial o una respuesta mongo
            # Esto es un HACK porque ConversationBufferMemory no maneja bien roles intermedios.
            # Idealmente, usaríamos un tipo de memoria diferente o un Agente.
            # if not is_first_iteration:
            #     # Forzar el prefijo humano para la respuesta mongo (para que el LLM la vea como entrada)
            #     # Esto puede ensuciar el historial si se ve directamente.
            #     memory.human_prefix = "respuesta mongo" # Temporalmente cambiar prefijo
            # else:
            #     memory.human_prefix = "consulta usuario" # Prefijo normal

            # Obtener respuesta del modelo
            # Langchain añade automáticamente el 'current_input' al historial con el prefijo adecuado (human_prefix)
            model_response_raw = conversation.predict(input=current_input)
            logging_manager.log_debug(f"Respuesta Modelo Raw (Iteración {'Inicial' if is_first_iteration else 'Interna'})", model_response_raw)

            # Restaurar prefijo por si lo cambiamos (si usamos el hack anterior)
            # memory.human_prefix = "consulta usuario"

            # Procesar respuesta
            label, content = communication.parse_message(model_response_raw)

            if not label:
                logging_manager.log_debug("Error Parseo", f"No se pudo parsear: {model_response_raw}")
                print(f"Error: Respuesta inesperada del modelo: {model_response_raw}")
                # Guardar la respuesta no parseada en memoria como respuesta de IA
                # El input fue 'current_input'
                conversation.memory.save_context({"input": current_input}, {"output": f"respuesta usuario: {model_response_raw}"})
                break # Salir del bucle interno en caso de error de parseo

            # Ejecutar si es consulta [sistema]
            if label == "consulta mongo": # ADAPTAR ESTO
                is_first_iteration = False # Ya no es la primera iteración

                # Validación de comandos peligrosos
                if security.is_command_dangerous(content):
                    print(f"Comando Peligroso Detectado: {content}")
                    if not security.request_authorization():
                        print("Autorización denegada. Abortando secuencia.")
                        # Guardar que se abortó
                        conversation.memory.save_context(
                            {"input": current_input}, # El input que llevó a la consulta peligrosa
                            {"output": "respuesta usuario: Comando peligroso detectado y autorización denegada."} # La respuesta del modelo fue la consulta
                        )
                        break # Salir del bucle interno
                    else:
                        print("Autorización concedida. Ejecutando comando.")
                        # Continuar con la ejecución

                # Ejecutar el comando
                command_to_execute = content.strip()
                output = executor.execute_mongo_command(command_to_execute) # ADAPTAR ESTO
                logging_manager.log_debug("Salida Mongo", output)

                # Crear respuesta etiquetada y mostrarla al usuario
                respuesta_mongo_etiquetada = communication.create_respuesta_mongo(output) # ADAPTAR ESTO
                logging_manager.log_debug("Respuesta Mongo Etiquetada", respuesta_mongo_etiquetada)
                print(respuesta_mongo_etiquetada) # Mostrar pasos intermedios

                # Preparar la respuesta mongo como la *siguiente entrada* para el modelo
                current_input = respuesta_mongo_etiquetada

                # Guardar en memoria: La IA dijo 'consulta mongo', el sistema respondió con 'respuesta mongo'
                # Langchain ya guardó (current_input -> model_response_raw)
                # Necesitamos añadir manualmente el resultado para el siguiente turno.
                # El workaround anterior de save_context puede ser confuso aquí.
                # La forma en que Langchain ConversationChain maneja esto no es ideal para agentes.
                # Vamos a confiar en que el LLM use el historial correctamente.
                # El historial ahora tendrá:
                # Humano (user_query) -> IA (consulta mongo)
                # Humano (respuesta mongo) -> IA (siguiente consulta mongo o respuesta usuario)
                # Esto requiere que el LLM entienda que 'respuesta mongo' es la entrada para su siguiente decisión.

                # Continuar el bucle interno para el siguiente paso autónomo

            elif label == "respuesta usuario":
                # Si el modelo dio una respuesta directa al usuario, la tarea terminó.
                logging_manager.log_debug("Respuesta Usuario Final", model_response_raw)
                print(model_response_raw)
                # Guardar la respuesta final en memoria (Langchain ya lo hizo con predict)
                # conversation.memory.save_context({"input": current_input}, {"output": model_response_raw})
                break # Salir del bucle interno, volver a esperar input del usuario

            else:
                # Error de etiqueta desconocida
                print(f"Error: Etiqueta desconocida o formato incorrecto: {model_response_raw}")
                logging_manager.log_debug("Error Etiqueta", f"Etiqueta desconocida: {model_response_raw}")
                # Guardar respuesta no reconocida
                conversation.memory.save_context({"input": current_input}, {"output": f"respuesta usuario: {model_response_raw}"})
                break # Salir del bucle interno


if __name__ == "__main__":
    main()
