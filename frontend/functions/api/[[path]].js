export async function onRequest({ request, env }) {
  let backendOrigin
  try {
    backendOrigin = new URL(env?.VERCYRA_API_ORIGIN)
  } catch {
    return new Response('API proxy is not configured', { status: 503 })
  }

  if (
    backendOrigin.protocol !== 'https:' ||
    backendOrigin.pathname !== '/' ||
    backendOrigin.search ||
    backendOrigin.hash ||
    backendOrigin.username ||
    backendOrigin.password
  ) {
    return new Response('API proxy configuration must be an HTTPS origin', {
      status: 503,
    })
  }

  const target = new URL(request.url)
  target.protocol = backendOrigin.protocol
  target.host = backendOrigin.host

  return fetch(new Request(target, request))
}
