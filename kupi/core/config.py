import gzip
import base64
import os
from dotenv import load_dotenv

load_dotenv()

RAPPI_DEVICE_ID: str = os.environ["RAPPI_DEVICE_ID"]
RAPPI_AUTH_USER: str = os.getenv("RAPPI_AUTH_USER", "")

def _load_rappi_token() -> str:
    # En desarrollo: leer directo del .env
    direct = os.getenv("RAPPI_TOKEN")
    if direct:
        return direct

    # En Lambda: leer desde Parameter Store (fácil de rotar sin redesplegar)
    import boto3
    ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return ssm.get_parameter(Name="/kupi/rappi-token")["Parameter"]["Value"]

RAPPI_TOKEN: str = _load_rappi_token()

def _load_cookie_string() -> str:
    # En desarrollo: leer directo del .env
    direct = os.getenv("UBEREATS_COOKIE_STRING")
    if direct:
        return direct

    # En Lambda: leer desde Parameter Store en 2 partes y unir
    import boto3
    ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1"))
    part1 = ssm.get_parameter(Name="/kupi/ubereats-cookie-1")["Parameter"]["Value"]
    part2 = ssm.get_parameter(Name="/kupi/ubereats-cookie-2")["Parameter"]["Value"]
    return part1 + part2

UBEREATS_COOKIE_STRING: str = _load_cookie_string()

DEFAULT_LAT: float = float(os.getenv("DEFAULT_LAT", "24.8143484"))
DEFAULT_LNG: float = float(os.getenv("DEFAULT_LNG", "-107.4005298"))
