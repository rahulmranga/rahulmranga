/**
 * Routes rahulrangarao.dev/app/* to the Fly app, leaving every other path on
 * GitHub Pages. Cloudflare already proxies this zone, so this Worker runs
 * before the origin is chosen and Pages never sees these requests.
 *
 * A Worker rather than an Origin Rule because rewriting the origin *host* in a
 * rule is a paid feature; Workers are free to 100k requests/day.
 */
const ORIGIN = "rahul-rangarao.fly.dev";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = ORIGIN;
    url.protocol = "https:";
    url.port = "";

    // Rebuild rather than mutate: a Request's headers are immutable once bound.
    const headers = new Headers(request.headers);
    // Fly routes on Host, so it must be the Fly hostname. Keep the original
    // for the app, and pass the real client IP through for rate limiting.
    headers.set("X-Forwarded-Host", "rahulrangarao.dev");
    headers.set("X-Forwarded-Proto", "https");
    const ip = request.headers.get("CF-Connecting-IP");
    if (ip) headers.set("CF-Connecting-IP", ip);

    return fetch(new Request(url, {
      method: request.method,
      headers,
      body: request.body,
      redirect: "manual",
    }));
  },
};
