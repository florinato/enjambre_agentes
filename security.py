# security.py
# Adaptar según el sistema

def is_command_dangerous(command: str) -> bool:
    """
    Comprueba si un comando es peligroso.
    """
    command = command.lower()
    dangerous_commands = ["dropdatabase", "drop", "delete"]
    for dangerous_command in dangerous_commands:
        if dangerous_command in command:
            return True
    return False

def request_authorization() -> bool:
    """
    Solicita autorización al usuario para ejecutar un comando peligroso.
    """
    response = input("¿Estás seguro de que quieres ejecutar este comando peligroso? (s/n): ")
    return response.lower() == "s"
