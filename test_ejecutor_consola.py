from servicios.ejecutor_consola import ejecutar_comando_seguro


def test_ejecutor_consola():
    """
    Prueba la función ejecutar_comando_seguro.
    """
    comando = "dir"
    resultado = ejecutar_comando_seguro(comando)
    print(f"Comando: {comando}")
    print(f"Salida: {resultado['salida']}")
    print(f"Error: {resultado['error']}")
    print(f"Código: {resultado['codigo']}")

if __name__ == "__main__":
    test_ejecutor_consola()
