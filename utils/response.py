import logging
import os
from datetime import datetime
from pathlib import Path
import unicodedata

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

from utils.functions import encrypt_document, doc_to_base64


# Variables para utilizar la encriptación de PQRS
POPPLER_PATH = r'C:\Users\O014796\AppData\Local\Programs\poppler-25.07.0\Library\bin'
TESSERACT_PATH = r'C:\Users\O014796\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

MAIN_PATH = Path(os.getcwd())
DATA_PATH = MAIN_PATH / "data"
FONT_PATH = MAIN_PATH / "fonts" / "noto-sans-regular.ttf"

# Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)


# Función para obtener respuesta del agente
def get_agent_response(
        thread_id: str,
        typo_list: str,
        sys_prompt: str,
        cases_path: Path,
        memory: InMemorySaver,
        agent: StateGraph,
        user_input: str = None,
        doc_path: Path = None
) -> str:
    
    """
    It has all the steps of the agent.

    Args:
        user_input: String message for the user
        thread_id: Unique id for conversation memory
        typo_list: List of typologies to chose
        sys_prompt: Base prompt of the agent
        doc_path: Local path for the document to analize
    """
    # En caso de que no haya mensaje
    # Se utiliza el mensaje por defecto
    if not user_input:
        user_input = "Analiza este documento y entregame el análisis"
    # Nombre del caso por defecto
    case_name = ""
    # Respuesta predefinida para errores
    error_response = "Lo lamento. No puedo ayudarte en este momento. Intenta de nuevo más tarde."
    # Obtenemos la fecha de hoy
    today = datetime.today().strftime("%Y-%m-%d")
    logger.info(f"In use date: {today}")
    # Este es el prompt general
    system_msg = sys_prompt.format(typo_list=typo_list, today=today, file_name="")
    # Si existe un documento cargado debemos leerlo
    # Leerlo implica extraer la información en base64
    # Para que LLM lo entienda
    # Si el usuario carga un documento
    # Entonces lo que hay que hacer es extraerle la información en base64
    if doc_path:
        logger.info(f"Document loaded")
        # Creamos el directorio del caso
        case_name = doc_path.stem
        case_path = cases_path / case_name
        case_path.mkdir(exist_ok=True)
        encrypted_path = case_path / f"{case_name}_encrypted.pdf"
        # Agregamos el nombre del archivo para la salida de la plantilla
        system_msg = sys_prompt.format(typo_list=typo_list, today=today, file_name=case_name)
        # Realizamos la encriptación
        # Si y solo si no se ha hecho antes
        if not os.path.exists(encrypted_path):
            try:
                encrypt_document(
                    doc_path=doc_path,
                    output_path=encrypted_path,
                    poppler_path=POPPLER_PATH,
                    tesseract_path=TESSERACT_PATH,
                    font_path=FONT_PATH
                )
            except Exception as e:
                return error_response
        else:
            logger.info(f"Encryption already done")
        # Listo ya tenemos nuestro documento encriptado
        # Es hora de convertirlo a base64 para que el agente lo utilice
        try:
            base64_pages = doc_to_base64(encrypted_path)
        except Exception as e:
            logger.error(f"Error in base64 conversion: {e}")
            return error_response
        # Creamos el input_message utilizando las imagenes como referencia
        # Si la conversación ya existe no tengo necesidad de volver a enviar el documento
        # El agente ya lo tiene en su memoria
        try:
            len(memory.get({"configurable": {"thread_id": thread_id}})["channel_values"]["messages"])
            logger.info("Thread exists")
            input_message = {
                "role": "user",
                "content": [
                    {"type": "text",
                    "text": user_input}
                ]
            }
        except Exception as e:
            logger.error("Thread does not exists")
            input_message = {
                "role": "user",
                "content": [
                    {"type": "text",
                    "text": user_input}
                ] + base64_pages
            }
    # Si no hay ningun documento cargado el mensaje que le enviamos
    # Es basicamente solamente el texto que escribe el usuario
    else:
        logger.info("No document loaded")
        input_message = {
            "role": "user",
            "content": [
                {"type": "text",
                "text": user_input}
            ]
        }
    # Ahora creamos el mensaje para enviar
    # Validamos si ya existe la conversación en memoria
    try:
        # Si existe existe quiere decir que no es la primera conversación
        # Por lo tanto debo enviarle el prompt del sistema
        len(memory.get({"configurable": {"thread_id": thread_id}})["channel_values"]["messages"])
        logger.info("Thread exists")
        messages = {
            "messages": [
                input_message
            ]
        }
    except Exception as e:
        # De lo contrario si existe
        # Entonces ya no hace falta enviarle el system_prompt
        logger.error("Thread does not exists")
        messages = {
            "messages": [
                {"role": "system", "content": system_msg},
                input_message
            ]
        }
    # Esta es la sesion
    config = {"configurable": {"thread_id": thread_id}}
    # Una vez tenemos el input del mensaje
    # Ya podemos enviarlo al agente
    try:
        result = agent.invoke(messages, config=config)
        response = result["messages"][-1].content
        logger.info("Main agent response succesful")
    except Exception as e:
        logger.error(f"Error getting main response: {e}")
        return error_response

    return response, case_name