#!/bin/bash
# Rota el token de Rappi sin redesplegar toda la Lambda.
# Uso: edita RAPPI_TOKEN en .env, luego corre: bash scripts/rotate-rappi-token.sh

set -e

FUNCTION_NAME="kupi-api"
REGION="us-east-1"
RAPPI_PARAM="/kupi/rappi-token"

echo "=== Rotando token de Rappi ==="

if [ ! -f .env ]; then
    echo "ERROR: No se encontró .env. Corre desde la raíz del proyecto."
    exit 1
fi

# Leer nuevo token del .env
TOKEN=$(python3 -c "
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    line = line.strip()
    if line.startswith('RAPPI_TOKEN='):
        print(line.partition('=')[2])
        break
")

if [ -z "$TOKEN" ]; then
    echo "ERROR: RAPPI_TOKEN no encontrado en .env"
    exit 1
fi

echo "Token leído (${#TOKEN} bytes)."

# Actualizar Parameter Store
echo "Actualizando Parameter Store..."
aws ssm put-parameter \
    --name "$RAPPI_PARAM" \
    --value "$TOKEN" \
    --type "String" \
    --overwrite \
    --region "$REGION" > /dev/null

echo "Parameter Store actualizado."

# Forzar cold start de Lambda para que cargue el nuevo token
echo "Forzando reinicio de Lambda..."
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --description "token-rotated-$(date +%s)" \
    --region "$REGION" > /dev/null

aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

echo ""
echo "Listo. El nuevo token estará activo en la próxima petición a Lambda."
