import logging
from pathlib import Path

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from dotenv import load_dotenv
from google.oauth2 import service_account
import os
from requests.sessions import Session

import streamlit as st

import vertexai

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

# Cargamos las variables de entorno
# Estas tienen las credenciales de autenticación a AWS
MAIN_PATH = Path(os.getcwd())

load_dotenv(MAIN_PATH / ".env")

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") 

AWS_ACCESS_KEY = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_REGION = st.secrets["AWS_REGION"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_SESSION_TOKEN = st.secrets["AWS_SESSION_TOKEN"]
HOST_EXP_ENV = st.secrets["HOST_EXP_ENV"]
JWT_EXP_ENV = st.secrets["JWT"]
URL_EXP_ENV = st.secrets["URL_EXP_ENV"]


# Carga las credenciales de la cuenta de servicio
service_account_credentials = service_account.Credentials.from_service_account_file(
    MAIN_PATH / "utils" / "service_account.json"
)

# Initialize Vertex AI client
vertexai.init(
    project="expenvgenai",
    credentials=service_account_credentials,
    api_endpoint=URL_EXP_ENV,
    api_transport="rest",
)

# Save the original Session.request method
original_request = Session.request


def custom_request(self, method, url, headers, data, **kwargs):
    # Replace domain if called via langchain
    url = url.replace("https://us-central1-aiplatform.googleapis.com", URL_EXP_ENV)
    # Check if the URL is for your Vertex AI endpoint
    if URL_EXP_ENV in url:
        # Format headers
        # Lowercase and sort headers
        headers = {k.lower(): v for k, v in sorted(dict(headers).items())}
        # Inject the API GAteway Host
        headers["host"] = HOST_EXP_ENV.lower()
        # Inject the JWT token into a custom header for downstream validation
        headers["x-jwt-token"] = f"Bearer {JWT_EXP_ENV}"

        # Sign the request with AWS SigV4
        aws_request = AWSRequest(
            method=method,
            url=url + "?%24alt=json%3Benum-encoding%3Dint",
            headers=headers,
            data=data
        )
        session = boto3.Session(
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN
        )
        credentials = session.get_credentials().get_frozen_credentials()
        SigV4Auth(credentials, "execute-api", AWS_REGION).add_auth(aws_request)

    # Call the original request method with modified paramters
    return original_request(self,
                            method=aws_request.method,
                            url=url,
                            headers=dict(aws_request.headers),
                            data=aws_request.body,
                            **kwargs
                            )


# Patch the request
Session.request = custom_request