# main.py
# Add venv/Lib/site-packages to sys.path
import os
import sys
import threading  # Para verificar hilos de agentes
import time  # Para pausas en el bucle principal

from dotenv import load_dotenv

venv_path = os.path.join(os.getcwd(), "venv", "Lib", "site-packages")
if venv_path not in sys.path:
    sys.path.insert(0, venv_path)

from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage, ToolMessage)

# Importar servicios y orquestador
from servicios.cargar_llm import \
    cargar_llm  # Usaremos cargar_llm para obtener instancias separadas si es necesario
from servicios.ejecutor_consola import ejecutar_comando_seguro
from servicios.gestor_enjambre import GestorEnjambre
from servicios.gestor_logs import DB_DIR  # Importar el gestor y rutas de BD
from servicios.gestor_logs import DB_FILE, GestorLogs
from servicios.orquestador_master import OrquestadorMaster

# Asegurar que las variables de entorno estén cargadas al inicio
load_dotenv()

def main():
    print("--- Iniciando Superagente Quintana ---")

    # --- 1. Inicializar Servicios Compartidos ---
    # El GestorLogs se encargará de inicializar la BD al crearse
    # Asegurar que el directorio data existe ANTES de inicializar GestorLogs
    os.makedirs(DB_DIR, exist_ok=True)
    gestor_logs = GestorLogs(db_path=DB_FILE)
    gestor_logs.log_event("system_init", "main", "GestorLogs inicializado.")

    # El ejecutor de consola (pasamos la función)
    ejecutor_consola_svc = ejecutar_comando_seguro

    # La función para cargar instancias del LLM (pasamos la función)
    # Cada Agente y el Master cargará su propia instancia usando esta función.
    cargar_llm_svc = cargar_llm # O get_shared_llm_instance si quieres un singleton

    # Cargar el LLM antes de inicializar OrquestadorMaster y GestorEnjambre
    try:
        
        print("Verificación inicial del LLM exitosa.")
        gestor_logs.log_event("system_init", "main", "Verificación inicial del LLM exitosa.")
    except ValueError as e:
        print(f"\n--- ERROR CRÍTICO: Configuración del LLM inválida ---")
        print(f"Por favor, revisa tus variables de entorno MODEL y GOOGLE_API_KEY.")
        print(f"Detalle del error: {e}")
        gestor_logs.log_event("system_init", "main", f"ERROR CRÍTICO: Configuración LLM inválida: {e}", log_level="FATAL")
        sys.exit(1) # Salir si el LLM no carga

    gestor_logs.log_event("system_init", "main", "Servicios base inicializados (Logs, EjecutorConsola, CargarLLM).")

    # --- 2. Inicializar Gestor de Enjambre y Orquestador Master ---
    # Necesitamos referencias circulares lógicas: Master necesita GestorEnjambre (indirectamente via main),
    # GestorEnjambre necesita Master (para notificar). Los creamos primero y luego pasamos referencias si es necesario.

    print(f"cargar_llm_svc: {cargar_llm_svc}")
    orquestador_master = OrquestadorMaster(gestor_logs, gestor_enjambre, cargar_llm_svc) # Placeholder refs
    gestor_enjambre = GestorEnjambre(cargar_llm_svc, ejecutor_consola_svc, gestor_logs, orquestador_master) # Placeholder refs

    # orquestador_master.__init__( # Re-inicializar Master
    #     gestor_logs=gestor_logs,
    #     gestor_enjambre=gestor_enjambre, # Pasar la referencia completa al GestorEnjambre
    #     cargar_llm_svc=cargar_llm_svc
    # )
    # gestor_logs.log_event("system_init", "main", "Orquestador Master inicializado con referencia al Gestor de Enjambre.")

    # # Pasamos las referencias completas después
    # gestor_enjambre.__init__( # Usamos __init__ para re-inicializar con refs correctas
    #     cargar_llm_svc=cargar_llm_svc,
    #     ejecutor_consola_svc=ejecutor_consola_svc,
    #     gestor_logs_svc=gestor_logs,
    #     orquestador_master_svc=orquestador_master # Pasamos la referencia completa al Master
    # )
    # gestor_logs.log_event("system_init", "main", "Gestor de Enjambre inicializado con referencia al Master.")
    # gestor_logs.log_event("system_init", "main", "Orquestador Master inicializado con referencia al Gestor de Enjambre.")


    print("\nSistema listo. Introduce una tarea para el Agente Master:")

    # --- Bucle Principal de Orquestación ---
    # Este bucle maneja la interacción con el usuario y las acciones del Master
    try:
        while True: # Bucle principal infinito hasta que el usuario decida salir
            # --- 4. Procesar Input del Usuario o Esperar Eventos ---
            # En un sistema real, esto sería un loop de eventos (escuchar usuario, escuchar agentes)
            # Para esta demo, pediremos input del usuario, y si no hay agentes activos,
            # ese input activa una ronda del Master. Si hay agentes, simplemente esperamos o mostramos estado.

            agentes_activos = gestor_enjambre.get_all_agents_status()
            num_agentes_activos = len([s for s in agentes_activos.values() if s in ["started", "running", "paused"]])

            if num_agentes_activos == 0:
                # Si no hay agentes del enjambre trabajando, la entrada del usuario activa al Master
                tarea_usuario = input("\nIntroduce la siguiente tarea principal (o 'salir' para terminar): ")
                if tarea_usuario.lower() == 'salir':
                    gestor_logs.log_event("main_loop", "main", "Usuario solicitó salir.")
                    break # Salir del bucle principal
                if not tarea_usuario.strip():
                     gestor_logs.log_event("main_loop", "main", "Input vacío. Ignorando.")
                     continue # Ignorar input vacío

                gestor_logs.log_event("main_loop", "main", f"Recibida nueva tarea del usuario: {tarea_usuario}")
                print("\nProcesando con Agente Master...")

                # --- 5. Pasar Tarea al Orquestador Master y Obtener Acciones Solicitadas ---
                # El Master procesará la tarea del usuario (añadida a su historial) y devolverá acciones
                acciones_master = orquestador_master.process_user_task_or_event(tarea_usuario)

            else:
                # Si hay agentes activos, no pedimos input, damos una pausa y procesamos acciones del Master
                # (que podrían venir de notificaciones de problemas inyectadas en su historial)
                print(f"\nAgentes activos: {num_agentes_activos}. Estados: {agentes_activos}. Procesando ciclo del Master...")
                gestor_logs.log_event("main_loop", "main", f"Agentes activos ({num_agentes_activos}). Procesando ciclo del Master.")

                # Enviar un mensaje vacío o señal al Master para que procese su historial
                # Esto es clave para que el Master vea las notificaciones de problemas
                acciones_master = orquestador_master.process_user_task_or_event("Check agent status and decide next step.") # O un marcador especial

                # Pausa si no hay acciones del Master y hay agentes activos
                if not acciones_master:
                    gestor_logs.log_event("main_loop", "main", "Master no solicitó acciones. Pausando brevemente...", log_level="DEBUG")
                    time.sleep(1) # Pausa corta para no spamear

            # --- 6. Ejecutar Acciones Solicitadas por el Master ---
            if acciones_master:
                gestor_logs.log_event("main_orchestration", "main", f"Master solicitó {len(acciones_master)} acciones.")
                print(f"\nMaster solicitó {len(acciones_master)} acción(es)...")

                for i, accion in enumerate(acciones_master):
                    accion_type = accion.get("type")

                    if accion_type == "delegate":
                        agent_type = accion.get("agent_type")
                        task_description = accion.get("task_description")
                        if agent_type and task_description:
                             gestor_logs.log_event("main_orchestration", "main", f"Ejecutando acción {i+1}: Delegar {agent_type}.", details={"task": task_description})
                             print(f"\n--- Master delega: Lanzando agente {agent_type} para sub-tarea: {task_description} ---")
                             try:
                                 # El GestorEnjambre creará el Agente y el BucleLogico y lo ejecutará en un hilo
                                 gestor_enjambre.lanzar_agente(agent_type, task_description)
                             except Exception as e:
                                 gestor_logs.log_event("main_orchestration", "main", f"Error al lanzar agente {agent_type} (accion {i+1}): {e}", log_level="ERROR")
                                 print(f"Error al lanzar agente {agent_type} (accion {i+1}): {e}")

                        else:
                            gestor_logs.log_event("main_orchestration", "main", f"Acción 'delegate' inválida del Master (accion {i+1}).", log_level="WARNING", details=accion)
                            print(f"Advertencia: Acción 'delegate' inválida del Master (accion {i+1}): {accion}")

                    elif accion_type == "send_message":
                        agent_id = accion.get("agent_id")
                        message_content = accion.get("message_content")
                        if agent_id and message_content:
                             gestor_logs.log_event("main_orchestration", "main", f"Ejecutando acción {i+1}: Enviar mensaje a {agent_id}.", details={"message_snippet": message_content[:100] + "..."})
                             print(f"\n--- Master envía mensaje a agente {agent_id}: {message_content[:100]}... ---")
                             try:
                                 # El GestorEnjambre busca el agente y le inyecta el mensaje
                                 gestor_enjambre.send_message_to_agent(agent_id, message_content)
                             except Exception as e:
                                 gestor_logs.log_event("main_orchestration", "main", f"Error al enviar mensaje a agente {agent_id} (accion {i+1}): {e}", log_level="ERROR")
                                 print(f"Error al enviar mensaje a agente {agent_id} (accion {i+1}): {e}")

                        else:
                            gestor_logs.log_event("main_orchestration", "main", f"Acción 'send_message' inválida del Master (accion {i+1}).", log_level="WARNING", details=accion)
                            print(f"Advertencia: Acción 'send_message' inválida del Master (accion {i+1}): {accion}")

                    # TODO: Manejar otras acciones del Master si las hay


            # TODO: Lógica para esperar a que todos los agentes terminen antes de finalizar main,
            #       si no estamos en un bucle infinito de interacción.
            #       GestorEnjambre.wait_for_all_agents() podría usarse aquí si fuera necesario.
            #       En este diseño actual, el bucle principal sigue corriendo y procesa eventos.

            # Pausa al final de cada ciclo principal de orquestación si no hay input directo
            if num_agentes_activos > 0:
                 time.sleep(0.5) # Pausa para que los hilos de agentes hagan algo

    except Exception as e:
        gestor_logs.log_event("system_error", "main", f"Error fatal en main loop: {e}", log_level="FATAL")
        print(f"\n--- ERROR FATAL DEL SISTEMA ---: {e}")
        import traceback
        print(traceback.format_exc()) # Print traceback for fatal errors

    finally:
        # TODO: Añadir lógica de apagado (ej: esperar hilos, cerrar BD si es necesario)
        # Para esta demo simple con daemon threads, no es estrictamente necesario,
        # pero es una buena práctica.
        print("\n--- Finalizando Superagente Quintana ---")


if __name__ == "__main__":
    main()
