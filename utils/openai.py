import os
import logging
import json
from pathlib import Path

import streamlit as st

import requests
import httpx
from aws_requests_auth.aws_auth import AWSRequestsAuth
from dotenv import load_dotenv


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

MAIN_PATH = Path(os.getcwd())

load_dotenv(MAIN_PATH / ".env")

AWS_ACCESS_KEY = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_REGION = st.secrets["AWS_REGION"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_SESSION_TOKEN = st.secrets["AWS_SESSION_TOKEN"]
HOST_EXP_ENV = st.secrets["HOST_EXP_ENV"]
JWT_EXP_ENV = st.secrets["JWT"]
URL_EXP_ENV = st.secrets["URL_EXP_ENV"]

class AWSSignedHTTPTransport(httpx.HTTPTransport):
    def __init__(self):
        super().__init__()

    def handle_request(self, request):
        content = json.loads(request.content.decode("utf-8"))
        headers = dict(request.headers)
        headers["Host"] = HOST_EXP_ENV
        headers["api-key"] = JWT_EXP_ENV

        auth = AWSRequestsAuth(
            aws_access_key=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_token=AWS_SESSION_TOKEN,
            aws_host=HOST_EXP_ENV,
            aws_region=AWS_REGION,
            aws_service="execute-api",
        )

        response = requests.post(
            request.url,
            auth=auth,
            json=content,
            headers=headers,
        )

        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )