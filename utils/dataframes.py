import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

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
DATA_PATH = MAIN_PATH / "data"
FONT_PATH = MAIN_PATH / "fonts" / "noto-sans-regular.ttf"
DB_PATH = DATA_PATH / "db"
CASES_PATH = DATA_PATH / "cases"
PQRS_PATH = DATA_PATH / "pqrs"


# Tabla de tipologias --------------------------------------------------------------------------------
typo_data = pd.read_csv(
    DATA_PATH / "db" / "tipologias.csv",
    sep=",",
    dtype="str"
)
typo_data.columns = ["id", "typo", "desc"]
typo_data["id"] = typo_data["id"].astype(int)
# Eliminamos nulos
typo_data = typo_data.dropna(subset=["typo", "desc"], how="any")
typo_data["typo"] = typo_data["typo"].str.upper().str.strip()
typo_data["data"] = typo_data["id"].astype(str) + ". **" + typo_data["typo"] + "**: " + typo_data["desc"]


# Tabla de subtipologias --------------------------------------------------------------------------------
subtypo_data = pd.read_csv(
    DATA_PATH / "db" / "subtipologias.csv",
    sep=",",
    dtype="str"
)
subtypo_data.columns = ["id", "typo", "subtypo", "desc"]
subtypo_data["typo"] = subtypo_data["typo"].str.upper().str.strip()
subtypo_data["id"] = subtypo_data["id"].astype(int)
subtypo_data["subtypo_id"] = subtypo_data.groupby(["typo"]).cumcount() + 1
subtypo_data["data"] = "Tipología: " + subtypo_data["typo"] + "\nSubtipología " + \
    subtypo_data["subtypo_id"].astype(str) + "\n" + subtypo_data["subtypo"] + ": " + subtypo_data["desc"]


# Tabla de concepto de terceros --------------------------------------------------------------------------------
concept_data = pd.read_csv(
    DATA_PATH / "db" / "concepto_terceros.csv",
    sep=",",
    dtype="str"
)
concept_data.columns = ["cat", "typo", "desc", "casu", "area", "info"]
concept_data["typo"] = concept_data["typo"].str.upper().str.strip()
concept_data = concept_data.drop_duplicates()
# Eliminamos nulos
concept_data = concept_data.dropna(subset=["typo", "desc"], how="any")
# Modificaciones nuevas
# La idea es que siempre me debe dar requisitos adicionales
# Modificare la base de datos para simular que siempre hay documentos adicionales
concept_data["escal"] = np.where(concept_data["area"] == "Proveedor NTTDATA", "No", "Si")
# Reemplazamos nulos
concept_data = concept_data.fillna("No disponible")
concept_data = concept_data.replace("No aplica", "No disponible")
# Agregamos el indice de las tipologias
concept_data = concept_data.merge(
    typo_data[["id", "typo"]],
    on=["typo"],
    how="left"
)
# concept_data["id"] = concept_data["id"].astype(int)
concept_data["id"] = concept_data["id"].fillna(0).astype(int)
concept_data["casu_id"] = concept_data.groupby(["typo", "desc"]).cumcount() + 1
concept_data["data"] = "Tipología: " + concept_data["typo"] + "\nEscalar: " + concept_data["escal"] + \
    "\nCasuistica " + concept_data["casu_id"].astype(str) + ": " + concept_data["casu"] + "\nArea para escalar: " + \
    concept_data["area"] + "\nRequisitos adicionales para escalar: " + concept_data["info"]