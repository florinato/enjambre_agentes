from langchain.schema import HumanMessage

from agentes.clase_agente import Agente
from servicios.cargar_llm import cargar_llm
from servicios.ejecutor_consola import ejecutar_comando_seguro


def test_agent_instantiation():
    """
    Prueba la instanciación de un agente ejecutor y la ejecución de un comando.
    """
    try:
        # Crear un agente ejecutor
        agente = Agente(nombre="test_agent", rol="ejecutor", objetivo="Ejecutar comandos en el sistema.")
        print("Agente instanciado correctamente.")
        print(f"Nombre: {agente.nombre}")
        print(f"Rol: {agente.rol}")
        print(f"Objetivo: {agente.objetivo}")

        # Crear un mensaje para listar los archivos en la carpeta prompts
        tarea = "listar los archivos de esta carpeta: C:\\Users\\oscar\\Desktop\\proyectospy\\agente_plantilla\\prompts"
        mensaje = HumanMessage(content=tarea)
        agente.add_message_to_history(mensaje)

        # Obtener la respuesta del LLM (simulado)
        # En un escenario real, esto se haría a través de una llamada al LLM
        respuesta_llm = "<tool_call>\nagent_type: ejecutor\ntask_description: dir \"C:\\Users\\oscar\\Desktop\\proyectospy\\agente_plantilla\\prompts\"\n</tool_call>" # Simulación de la respuesta del LLM

        # Procesar la respuesta del LLM
        if "<tool_call>" in respuesta_llm:
            # Extraer el comando
            start_index = respuesta_llm.find("task_description: ") + len("task_description: ")
            end_index = respuesta_llm.find("\n</tool_call>")
            comando = respuesta_llm[start_index:end_index].strip().replace('"', '')

            # Ejecutar el comando
            resultado = ejecutar_comando_seguro(comando)
            print(f"Resultado del comando '{comando}':")
            print(f"  Salida: {resultado['salida']}")
            print(f"  Error: {resultado['error']}")
            print(f"  Código: {resultado['codigo']}")
        else:
            print("Error: Formato de respuesta del LLM incorrecto.")

        return True
    except Exception as e:
        print(f"Error al instanciar el agente: {e}")
        return False

if __name__ == "__main__":
    test_agent_instantiation()
