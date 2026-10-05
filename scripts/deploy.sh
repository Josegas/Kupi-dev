#!/bin/bash
set -e

FUNCTION_NAME="kupi-api"
REGION="us-east-1"
ROLE_NAME="kupi-lambda-role"
COOKIE_PARAM_1="/kupi/ubereats-cookie-1"
COOKIE_PARAM_2="/kupi/ubereats-cookie-2"
RAPPI_PARAM="/kupi/rappi-token"

echo "=== Kupi Deploy ==="
echo ""

# Verificar que existe .env
if [ ! -f .env ]; then
    echo "ERROR: No se encontró .env en el directorio actual."
    echo "Corre este script desde la raíz del proyecto: bash scripts/deploy.sh"
    exit 1
fi

# Obtener account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "Cuenta AWS: $ACCOUNT_ID"
echo ""

# ── Paso 1: Rol de ejecución Lambda ──────────────────────────────────────────
echo "[1/6] Rol de ejecución Lambda..."
if aws iam get-role --role-name $ROLE_NAME > /dev/null 2>&1; then
    echo "      Ya existe, continuando."
else
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' > /dev/null

    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    echo "      Creado. Esperando propagación IAM..."
    sleep 12
fi

# Permiso para leer de Parameter Store
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name kupi-ssm-read \
    --policy-document "{
        \"Version\": \"2012-10-17\",
        \"Statement\": [{
            \"Effect\": \"Allow\",
            \"Action\": \"ssm:GetParameter\",
            \"Resource\": [
                \"arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter${COOKIE_PARAM_1}\",
                \"arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter${COOKIE_PARAM_2}\",
                \"arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter${RAPPI_PARAM}\"
            ]
        }]
    }" > /dev/null

# ── Paso 2: Guardar cookie en Parameter Store (2 partes) ─────────────────────
echo "[2/6] Guardando cookie en Parameter Store..."
python3 - <<EOF
import subprocess, sys
from pathlib import Path

env_vars = {}
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    env_vars[key.strip()] = value.strip()

cookie = env_vars.get("UBEREATS_COOKIE_STRING", "")
mid = len(cookie) // 2
# Cortar en un separador de cookie (; ) para no partir un valor a la mitad
cut = cookie.rfind("; ", mid - 200, mid + 200)
if cut == -1:
    cut = mid
part1 = cookie[:cut + 2]   # incluir el "; " en la parte 1
part2 = cookie[cut + 2:]

print(f"      Cookie total: {len(cookie)} bytes")
print(f"      Parte 1: {len(part1)} bytes  |  Parte 2: {len(part2)} bytes")

for param_name, value in [("$COOKIE_PARAM_1", part1), ("$COOKIE_PARAM_2", part2)]:
    result = subprocess.run([
        "aws", "ssm", "put-parameter",
        "--name", param_name,
        "--value", value,
        "--type", "String",
        "--overwrite",
        "--region", "$REGION"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR guardando {param_name}: {result.stderr}")
        sys.exit(1)

print("      Guardadas en Parameter Store.")
EOF

# ── Paso 2b: Guardar token de Rappi en Parameter Store ──────────────────────
echo "[2b] Guardando token de Rappi en Parameter Store..."
python3 - <<EOF
import subprocess, sys
from pathlib import Path

env_vars = {}
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    env_vars[key.strip()] = value.strip()

token = env_vars.get("RAPPI_TOKEN", "")
if not token:
    print("      ERROR: RAPPI_TOKEN no encontrado en .env")
    sys.exit(1)

result = subprocess.run([
    "aws", "ssm", "put-parameter",
    "--name", "$RAPPI_PARAM",
    "--value", token,
    "--type", "String",
    "--overwrite",
    "--region", "$REGION"
], capture_output=True, text=True)
if result.returncode != 0:
    print(f"ERROR guardando token: {result.stderr}")
    sys.exit(1)

print(f"      Token guardado ({len(token)} bytes).")
EOF

# ── Paso 3: Empaquetar ───────────────────────────────────────────────────────
echo "[3/6] Empaquetando..."
rm -rf /tmp/kupi_pkg
mkdir -p /tmp/kupi_pkg

pip install -r requirements.txt -t /tmp/kupi_pkg/ -q --upgrade

cp -r kupi /tmp/kupi_pkg/
cp lambda_handler.py /tmp/kupi_pkg/

cd /tmp/kupi_pkg
zip -r /tmp/kupi_lambda.zip . -q
cd - > /dev/null

SIZE=$(du -sh /tmp/kupi_lambda.zip | cut -f1)
echo "      Zip listo: $SIZE"

# ── Paso 4: Variables de entorno (sin el cookie) ─────────────────────────────
echo "[4/6] Preparando variables de entorno..."
python3 - <<'PYEOF'
import json
from pathlib import Path

env_vars = {}
for line in Path(".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    env_vars[key.strip()] = value.strip()

# UBEREATS_COOKIE_STRING va en Parameter Store, no aquí
selected = {
    "RAPPI_DEVICE_ID": env_vars.get("RAPPI_DEVICE_ID", ""),
    "DEFAULT_LAT": env_vars.get("DEFAULT_LAT", "24.8143484"),
    "DEFAULT_LNG": env_vars.get("DEFAULT_LNG", "-107.4005298"),
    "UBEREATS_COOKIE_PARAM_NAME": "split",
    "UBEREATS_WORKER_URL": env_vars.get("UBEREATS_WORKER_URL", ""),
    "UBEREATS_WORKER_SECRET": env_vars.get("UBEREATS_WORKER_SECRET", ""),
    "SUPABASE_URL": env_vars.get("SUPABASE_URL", ""),
    "SUPABASE_SECRET_KEY": env_vars.get("SUPABASE_SECRET_KEY", ""),
    "CORS_ORIGINS": env_vars.get("CORS_ORIGINS", "*"),
    "RESEND_API_KEY": env_vars.get("RESEND_API_KEY", ""),
}

total = sum(len(k) + len(v) for k, v in selected.items())
print(f"      Variables: {', '.join(selected.keys())}")
print(f"      Tamaño total: {total} bytes")

with open("/tmp/kupi_env.json", "w") as f:
    json.dump({"Variables": selected}, f)
PYEOF

# ── Paso 5: Crear o actualizar Lambda ───────────────────────────────────────
echo "[5/6] Desplegando Lambda..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    echo "      Actualizando código..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb:///tmp/kupi_lambda.zip \
        --region $REGION > /dev/null

    aws lambda wait function-updated \
        --function-name $FUNCTION_NAME \
        --region $REGION

    echo "      Actualizando configuración..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment file:///tmp/kupi_env.json \
        --timeout 30 \
        --memory-size 512 \
        --region $REGION > /dev/null
else
    echo "      Creando función nueva..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.12 \
        --role $ROLE_ARN \
        --handler lambda_handler.handler \
        --zip-file fileb:///tmp/kupi_lambda.zip \
        --timeout 30 \
        --memory-size 512 \
        --environment file:///tmp/kupi_env.json \
        --region $REGION > /dev/null

    aws lambda wait function-active \
        --function-name $FUNCTION_NAME \
        --region $REGION
fi

# ── Paso 6: Function URL ─────────────────────────────────────────────────────
echo "[6/6] Function URL..."
if aws lambda get-function-url-config --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1; then
    echo "      Ya existe."
else
    aws lambda create-function-url-config \
        --function-name $FUNCTION_NAME \
        --auth-type NONE \
        --cors '{"AllowOrigins":["*"],"AllowMethods":["GET","POST","PATCH","DELETE","OPTIONS"],"AllowHeaders":["*"]}' \
        --region $REGION > /dev/null

    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id FunctionURLAllowPublicAccess \
        --action lambda:InvokeFunctionUrl \
        --principal "*" \
        --function-url-auth-type NONE \
        --region $REGION > /dev/null
fi

# ── Resultado ────────────────────────────────────────────────────────────────
FUNCTION_URL=$(aws lambda get-function-url-config \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query FunctionUrl \
    --output text)

echo ""
echo "================================================"
echo "  Deploy completado"
echo "  URL: ${FUNCTION_URL}"
echo "  Health check: curl ${FUNCTION_URL}health"
echo "================================================"
