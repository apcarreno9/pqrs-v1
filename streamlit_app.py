import logging
import os
from pathlib import Path

import numpy as np
import httpx
from dotenv import load_dotenv

from langgraph.checkpoint.memory import InMemorySaver

import streamlit as st

from utils.tools import get_typology_concept, get_subtypologies, make_response_document, typo_data
from utils.prompts import agent_prompt
from utils.agent import make_agent_graph
from utils.response import get_agent_response

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

# --------------------------------------------------- VARIABLES DE ENTORNO ----------------------------------------------------
MAIN_PATH = Path(os.getcwd())
DATA_PATH = MAIN_PATH / "data"
FONT_PATH = MAIN_PATH / "fonts" / "noto-sans-regular.ttf"
DB_PATH = DATA_PATH / "db"
CASES_PATH = DATA_PATH / "cases"
PQRS_PATH = DATA_PATH / "pqrs"

load_dotenv(MAIN_PATH / ".env")

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_REGION = os.getenv("AWS_REGION")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
HOST_EXP_ENV = os.getenv("HOST_EXP_ENV")
JWT_EXP_ENV = os.getenv("JWT")
URL_EXP_ENV = os.getenv("URL_EXP_ENV")

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png"
}
# -----------------------------------------------------------------------------------------------------------------------------

# Selección de cliente
model_supplier = "openai"
model_id = "gpt-5"

if model_supplier == "openai":
    from utils.openai import AWSSignedHTTPTransport
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=model_id,
        base_url=URL_EXP_ENV,
        api_key=JWT_EXP_ENV,
        max_tokens=None,
        http_client=httpx.Client(transport=AWSSignedHTTPTransport()),
        temperature=0
    )
    logger.info(f"Using OPENAI {model_id}")
elif model_supplier == "vertex":
    from utils.vertexai import service_account_credentials
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        model_name=model_id,
        base_url=URL_EXP_ENV,
        credentials=service_account_credentials,
        max_tokens=None,
        temperature=0
    )
    logger.info(f"Using VERTEX {model_id}")
else:
    None

# --------------------------------------------------- STREAMLIT ---------------------------------------------------------------
st.markdown(
    "<h1 style='text-align: center;'>¡Hola 👋 soy Faro! Tu asistente para la gestión de PQRS de BBVA 📑</h1>",
    unsafe_allow_html=True
)
with st.expander("**¿Cómo usar a Faro?**"):
    st.markdown(
"""
FARO es el asistente inteligente diseñado especificamente para ayudarte a gestionar las PQRS de los clientes.
Lo único que debes hacer es cargar el documento **.pdf** que deseas que analicemos juntos.
En este momento tengo la capacidad de:
* Identificar la o las tipologías más adecuadas para el contexto del caso del cliente.
* Darte un resumen detallado de que necesita el usuario.
* Informarte si esta tipología necesita escalarse
* Generarte una plantilla de respuesta para que tu la completes

**IMPORTANTE:** _Si deseas reiniciar el chat simplemente refresca la página con F5._

**¡Simplemente pideme que analice el documento y podre responderte todas las preguntas que tengas! 🫡**
"""
)
# Permite cargar el documento que quieren analizar
st.markdown(
    "<h4 style='text-align: center;'>Aquí puedes cargar el documento que quieres que analicemos📑</h4>",
    unsafe_allow_html=True
)
uploaded_file = st.file_uploader(
    label="Cargar documento",
    label_visibility="collapsed",
    type="pdf",
    accept_multiple_files=False,
)

# Variables de sesión de Streamlit
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(np.random.randint(1, 500)).zfill(5)

if "memory" not in st.session_state:
    st.session_state["memory"] = InMemorySaver()

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if "document_analyzed" not in st.session_state:
    st.session_state["document_analyzed"] = False

if "uploaded_filename" not in st.session_state:
    st.session_state["uploaded_filename"] = ""


# Agente
agent = make_agent_graph(
    llm=llm,
    tools=[get_typology_concept, get_subtypologies, make_response_document],
    memory=st.session_state["memory"]
)

# Una vez cargado crea un mensaje para disparar el agente automaticamente
if uploaded_file:
    if uploaded_file.name != st.session_state["uploaded_filename"]:
        logger.info("New document")
        st.toast("**¡Documento cargado!** ✅", duration="long")
        doc_path = MAIN_PATH / uploaded_file.name
        with open(doc_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        logger.info("Document obtained")

        # Reiniciar conversación y memoria
        st.session_state["thread_id"] = str(np.random.randint(1, 500)).zfill(5)
        st.session_state["messages"] = []
        st.session_state["document_analyzed"] = False

        # Ya tenemos el documento podemos ejecutar la logica
        # siempre y cuando no lo hayamos hecho antes
        with st.spinner("¡Analizando documento! 🧐"):
            auto_response = get_agent_response(
                cases_path=CASES_PATH,
                agent=agent,
                thread_id=st.session_state["thread_id"],
                typo_list="\n".join(typo_data["data"].tolist()),
                sys_prompt=agent_prompt,
                user_input=None,
                doc_path=doc_path,
                memory=st.session_state["memory"]
            )
        st.session_state.messages.append({"role": "assistant", "content": auto_response[0]})
        st.chat_message("assistant").markdown(auto_response[0])
        # Marcamos el documento como ya analizado
        st.session_state["uploaded_filename"] = uploaded_file.name
        st.session_state["document_analyzed"] = True
    else:
        doc_path = MAIN_PATH / uploaded_file.name
else:
    logger.info("Document already analized")
    doc_path = None

# -------------------------------------------------------------- CHATBOT -------------------------------------------------------
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)
    with st.spinner("¡Pensando! 🧐", show_time=False):
        response = get_agent_response(
            cases_path=CASES_PATH,
            agent=agent,
            thread_id=st.session_state["thread_id"],
            typo_list="\n".join(typo_data["data"].tolist()),
            sys_prompt=agent_prompt,
            user_input=prompt,
            doc_path=doc_path,
            memory=st.session_state["memory"]
        )
    st.session_state.messages.append({"role": "assistant", "content": response[0]})
    st.chat_message("assistant").markdown(response[0])
    # Boton de descarga de las imagenes
    # if response[1] != "":
    #     response_document_path = CASES_PATH / response[1] / f"plantilla_respuesta_{response[1]}.docx"
    #     if os.path.exists(response_document_path):
    #         logger.info("Response document generated")
    #         with open(response_document_path, "rb") as file:
    #             btn = st.download_button(
    #                 label="¡Descargar tu plantilla!",
    #                 data=file,
    #                 file_name=f"plantilla_generada_{response[1]}.docx",
    #                 mime=MIME_TYPES["docx"],
    #             )