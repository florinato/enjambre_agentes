# Instrucciones para configurar el entorno

Sigue estos pasos para configurar el entorno virtual y las dependencias del proyecto:

## 1. Crear un entorno virtual

Abre una terminal y ejecuta el siguiente comando:

```bash
python -m venv venv
```

## 2. Activar el entorno virtual

### En Windows:

```bash
venv\\Scripts\\activate
```

### En macOS y Linux:

```bash
source venv/bin/activate
```

## 3. Instalar las dependencias

Asegúrate de estar en el directorio raíz del proyecto y ejecuta el siguiente comando:

```bash
pip install -r requirements.txt
```

Si no existe el archivo `requirements.txt`, puedes crear uno con las dependencias necesarias:

```bash
pip freeze > requirements.txt
```

## 4. Configurar las variables de entorno

El proyecto utiliza variables de entorno para su configuración. El archivo `.env.example`, renómbralo a `.env`. Este archivo sirve como plantilla y contiene las variables necesarias para ejecutar el proyecto. Modifica los valores de las variables en el archivo `.env` con la configuración correcta para tu entorno. Por ejemplo:

```
API_KEY=tu_api_key
DATABASE_URL=tu_url_de_base_de_datos
```

**Nota:** No incluyas información sensible (como contraseñas o claves secretas) directamente en este archivo. Asegúrate de que el archivo `.env` está incluido en el archivo `.gitignore` para evitar subir información sensible al repositorio. El archivo `.env` no debe ser subido al repositorio.

## Repositorios de ejemplo

Estos repositorios utilizan este patrón:

*   [agenteMongoDB](https://github.com/florinato/agenteMongoDB)
*   [agenteLiterario](https://github.com/florinato/agenteLiterario)
