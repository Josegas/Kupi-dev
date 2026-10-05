/**
 * Cloudflare Worker - Proxy para UberEats
 * Lambda no puede llamar a UberEats directamente (IPs de AWS bloqueadas).
 * Este Worker recibe la petición de Lambda, la reenvía a UberEats desde
 * el edge de Cloudflare, y devuelve la respuesta.
 */
export default {
  async fetch(request, env) {
    // Verificar clave secreta para que solo Lambda pueda usar este proxy
    const secret = request.headers.get("x-kupi-secret");
    if (!env.KUPI_SECRET || secret !== env.KUPI_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }

    // El body contiene: { url, method, headers, body }
    let payload;
    try {
      payload = await request.json();
    } catch {
      return new Response("Invalid JSON body", { status: 400 });
    }

    const { url, method = "POST", headers = {}, body } = payload;

    if (!url || !url.startsWith("https://www.ubereats.com/")) {
      return new Response("URL no permitida", { status: 403 });
    }

    try {
      const upstreamResponse = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });

      const responseText = await upstreamResponse.text();
      return new Response(responseText, {
        status: upstreamResponse.status,
        headers: {
          "Content-Type": upstreamResponse.headers.get("Content-Type") || "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: String(err) }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      });
    }
  },
};
