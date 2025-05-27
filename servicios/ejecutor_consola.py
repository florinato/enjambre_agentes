import platform
import subprocess


def ejecutar_comando_seguro(comando: str) -> dict:
    """
    Ejecuta un comando de forma segura utilizando subprocess.run.
    Usa shell=True solo en Windows para soportar comandos internos como 'dir'.
    """
    try:
        is_windows = platform.system().lower() == "windows"
        result = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            shell=is_windows,  # shell=True solo en Windows
        )
        return {
            "salida": result.stdout.strip(),
            "error": result.stderr.strip(),
            "codigo": result.returncode,
        }
    except subprocess.CalledProcessError as e:
        return {
            "salida": e.stdout.strip() if e.stdout else "",
            "error": e.stderr.strip() if e.stderr else str(e),
            "codigo": e.returncode,
        }
    except FileNotFoundError:
        return {
            "salida": "",
            "error": "Comando no encontrado",
            "codigo": 127,
        }
    except Exception as e:
        return {
            "salida": "",
            "error": str(e),
            "codigo": 1,
        }


if __name__ == "__main__":
    # Ejemplo de uso (para probar)
    comando = "dir"
    resultado = ejecutar_comando_seguro(comando)
    print(f"Comando: {comando}")
    print(f"Salida: {resultado['salida']}")
    print(f"Error: {resultado['error']}")
    print(f"Código: {resultado['codigo']}")
