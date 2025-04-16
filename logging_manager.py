# logging_manager.py
import logging
import os
from datetime import datetime

# Define la carpeta de logs
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Define el nombre del archivo log basado en la fecha
LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("%Y-%m-%d") + ".log")

# Configura el logger
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

LOGGING_MANAGER_PROMPTS_FILE = "prompts/logging_manager_prompts.txt"
with open(LOGGING_MANAGER_PROMPTS_FILE, "r") as f:
    LOG_FORMAT = f.readline().strip()

def log_debug(category: str, message: str):
    """
    Registra un mensaje de depuración.
    """
    logging.debug(LOG_FORMAT.format(category=category, message=message))

def log_info(category: str, message: str):
    """
    Registra un mensaje de información.
    """
    logging.info(LOG_FORMAT.format(category=category, message=message))

def log_warning(category: str, message: str):
    """
    Registra un mensaje de advertencia.
    """
    logging.warning(LOG_FORMAT.format(category=category, message=message))

def log_error(category: str, message: str):
    """
    Registra un mensaje de error.
    """
    logging.error(LOG_FORMAT.format(category=category, message=message))
