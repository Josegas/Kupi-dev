"""
Punto de entrada para AWS Lambda.
Envuelve la app de FastAPI con Mangum para requests HTTP.
Si el evento es un job programado (EventBridge), lo rutea directamente.
"""
from mangum import Mangum
from kupi.api.main import app

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    # EventBridge / invocación directa con payload de job
    if isinstance(event, dict) and event.get("job"):
        job = event["job"]
        if job == "sample_prices":
            from kupi.jobs.price_sampler import run
            return run()
        if job == "warmup":
            return {"status": "warm"}
    # Request HTTP normal (API Gateway / Function URL)
    return _mangum_handler(event, context)
