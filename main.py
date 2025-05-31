# main.py
import os
import sys
import threading
import time
from typing import Any, Dict, List  # Importar tipos usados en type hints

from dotenv import load_dotenv

# Importar servicios y orquestador
from servicios.cargar_llm import \
    cargar_llm  # Usaremos cargar_llm para obtener instancias separadas si es necesario
from servicios.ejecutor_consola import ejecutar_comando_seguro
from servicios.gestor_enjambre import GestorEnjambre
from servicios.gestor_logs import DB_DIR  # Importar el gestor y rutas de BD
from servicios.gestor_logs import DB_FILE, GestorLogs
from servicios.orquestador_master import OrquestadorMaster

# Importar los tipos de mensajes necesarios para referencias si se usan directamente en main
# Aunque no se usan directamente en el bucle principal actual, mantenerlos para claridad
# from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
#                                      SystemMessage, ToolMessage)




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
    cargar_llm_svc = cargar_llm  # O get_shared_llm_instance si quieres un singleton
    llm_master = None
    orquestador_master = None # Inicializar orquestador_master

    try:
        llm_master = cargar_llm_svc()
        print(f"Tipo de llm_master: {type(llm_master)}, valor: {llm_master}")
        if llm_master is None:
            print("Error: cargar_llm() devolvió None. Abortando.")
            gestor_logs.log_event("system_init", "main", "Error: cargar_llm() devolvió None.", log_level="FATAL")
            return

        print("Verificación inicial del LLM exitosa.")
        gestor_logs.log_event("system_init", "main", "Verificación inicial del LLM exitosa.")

        # --- 2. Inicializar Gestor de Enjambre y Orquestador Master ---
        # Primero crea instancias vacías (sin referencias cruzadas)
        gestor_enjambre = GestorEnjambre(
            cargar_llm_svc=cargar_llm_svc,
            ejecutor_consola_svc=ejecutor_consola_svc,
            gestor_logs_svc=gestor_logs,
            orquestador_master_svc=None  # Se asignará después
        )
        orquestador_master = OrquestadorMaster(
            gestor_logs=gestor_logs,
            gestor_enjambre=gestor_enjambre,
            cargar_llm_svc=cargar_llm_svc
        )
        # Ahora asigna la referencia cruzada
        gestor_enjambre.orquestador_master = orquestador_master

        gestor_logs.log_event("system_init", "main", "Orquestador Master y Gestor de Enjambre inicializados y enlazados.")

        print("\nSistema listo. Introduce una tarea para el Agente Master:")

        # --- Bucle Principal de Orquestación y Eventos ---
        # Este bucle se ejecuta continuamente para:
        # 1. Recibir input del usuario (si no hay agentes activos).
        # 2. Darle al Master una oportunidad para procesar su historial y reaccionar (especialmente si hay notificaciones de problemas).
        # 3. Ejecutar las acciones solicitadas por el Master (delegar, enviar mensajes).
        # 4. Monitorear el estado de los agentes.
        user_input_needed = True # Bandera para saber cuándo pedir input al usuario

        while True:
            acciones_master: List[Dict[str, Any]] = [] # Resetear acciones en cada ciclo
            respuesta_texto = ""

            # --- 4. Procesar Input del Usuario o Dar Ciclo al Master ---
            agentes_status = gestor_enjambre.get_all_agents_status()
            agentes_running_or_paused = {
                 aid: status for aid, status in agentes_status.items()
                 if status in ["started", "running", "paused"]
            }
            num_agentes_activos = len(agentes_running_or_paused)

            if user_input_needed and num_agentes_activos == 0:
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
                user_input_needed = False # Ya procesamos el input del usuario

                # Pasar la tarea del usuario al Master para su procesamiento inicial
                acciones_master, respuesta_texto = orquestador_master.process_user_task_or_event(tarea_usuario)

            else:
                # Si hay agentes activos O si ya procesamos el input y el Master necesita más ciclos
                # Damos al Master la oportunidad de procesar su historial (notificaciones, etc.)
                # Esto es crucial para que el Master reaccione a los problemas reportados.
                if num_agentes_activos > 0:
                    print(f"\nAgentes activos: {num_agentes_activos}. Estados: {agentes_running_or_paused}. Master procesando...")
                    gestor_logs.log_event("main_loop", "main", f"Agentes activos ({num_agentes_activos}). Master procesando ciclo de eventos.")
                else:
                    # Caso: El Master no delegó nada en la ronda anterior, no hay agentes, no pedimos input.
                    # Damos un ciclo al Master por si debe decir algo más o el prompt lo requiere.
                    # Si el Master ya no tiene nada que hacer y no hay agentes, el bucle se volvería inactivo
                    # hasta el próximo input del usuario.
                    gestor_logs.log_event("main_loop", "main", "No hay agentes activos, Master procesando ciclo sin input directo.", log_level="DEBUG")


                # Llamar al Master sin un input de usuario directo. Esto le permite reaccionar
                # a mensajes inyectados en su historial (como las notificaciones de problemas).
                # Pasamos None para indicar que no es un nuevo input de usuario.
                acciones_master, respuesta_texto = orquestador_master.process_user_task_or_event(input_message=None)


            # --- 6. Ejecutar Acciones Solicitadas por el Master ---
            if acciones_master:
                gestor_logs.log_event("main_orchestration", "main", f"Master solicitó {len(acciones_master)} acciones.")
                print(f"\nMaster solicitó {len(acciones_master)} acción(es)...")

                for i, accion in enumerate(acciones_master):
                    accion_type = accion.get("type")

                    if accion_type == "delegate":
                        agent_type = accion.get("agent_type")
                        task_description = accion.get("task_description")
                        if isinstance(agent_type, str) and isinstance(task_description, str):
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
                        if isinstance(agent_id, str) and isinstance(message_content, str):
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


            # --- Monitoreo y Sincronización (Bucle Principal) ---
            # Si no hay acciones del Master Y no hay agentes trabajando,
            # volvemos al estado de esperar input de usuario.
            agentes_running_or_paused_after_actions = {
                 aid: status for aid, status in gestor_enjambre.get_all_agents_status().items()
                 if status in ["started", "running", "paused"]
            }
            num_agentes_activos_after_actions = len(agentes_running_or_paused_after_actions)


            if not acciones_master and num_agentes_activos_after_actions == 0:
                 # No hay nada más que el Master quiera hacer AHORA, y no hay agentes trabajando.
                 # Volvemos al estado de esperar input de usuario.
                 user_input_needed = True
                 gestor_logs.log_event("main_loop", "main", "No hay acciones del Master ni agentes activos. Esperando input de usuario.")
                 print("\n--- Ronda de orquestación completada. No hay agentes activos. ---")
                 print("--- Reanudando interacción con usuario. ---")
                 # Pequeña pausa antes de pedir input (opcional)
                 time.sleep(0.1) # Pausa mínima


            elif num_agentes_activos_after_actions > 0:
                 # Hay agentes trabajando o pausados. No pedir input del usuario todavía.
                 user_input_needed = False
                 gestor_logs.log_event("main_loop", "main", f"Hay {num_agentes_activos_after_actions} agentes activos. Continuará el ciclo de orquestación.")
                 # Pausa para no spamear y permitir que los hilos de agentes hagan su trabajo
                 time.sleep(0.5) # Pausa más larga si hay agentes activos

            # Si hay acciones del Master pero no hay agentes activos (elif acciones_master), el bucle
            # continuará inmediatamente en la siguiente iteración para procesar más posibles acciones del Master
            # sin pausa, hasta que las acciones se agoten.

            if respuesta_texto:
                print(f"Respuesta del Master: {respuesta_texto}")


    except KeyboardInterrupt:
        print("\n--- Interrupción por usuario (Ctrl+C) ---")
        gestor_logs.log_event("system_exit", "main", "Interrupción por usuario.")
        # TODO: Implementar apagado controlado de hilos de agentes si es posible
        # print("\nEsperando a que los hilos de agentes finalicen (Ctrl+C puede no esperar hilos daemon)...")
        # for thread in threading.enumerate():
        #     if thread is not threading.current_thread():
        #         try:
        #             thread.join(timeout=1) # Esperar brevemente
        #         except:
        #             pass
        # print("Hilos de agentes finalizados o ignorados.")

    except Exception as e:
        gestor_logs.log_event("system_error", "main", f"Error fatal en main loop: {e}", log_level="FATAL")
        print(f"\n--- ERROR FATAL DEL SISTEMA ---: {e}")
        import traceback
        print(traceback.format_exc()) # Print traceback for fatal errors
    finally:
        print("\n--- Finalizando Superagente Quintana ---")
        # Asegurarse de que el programa se cierra correctamente
        # if orquestador_master:
        #     # Aquí puedes agregar lógica para cerrar conexiones, etc.
        #     pass
        sys.exit(0) # Exit the program
if __name__ == "__main__":
    main()
