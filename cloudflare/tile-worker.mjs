/* global TILE_ASSETS, caches */
// TILE_ASSETS is injected by prepare_pages.mjs from the hashed release manifests.
// Pages ignores Range; Cloudflare's Cache API provides native byte-range responses.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const spec = TILE_ASSETS[url.pathname];
    if (!spec || request.method !== 'GET') return env.ASSETS.fetch(request);
    const range = request.headers.get('Range');
    if (range && !/^bytes=\d+-\d*$/.test(range)) return new Response(null, {status: 416});
    if (range && Number(range.slice(6).split('-')[0]) >= spec.size) {
      return new Response(null, {status: 416, headers: {'Content-Range': `bytes */${spec.size}`}});
    }
    const cacheUrl = new URL(`/__tile_cache/${spec.sha256}`, url.origin);
    const key = new Request(cacheUrl);
    const lookup = new Request(cacheUrl, {headers: range ? {Range: range} : {}});
    const cache = caches.default;
    let response = await cache.match(lookup);
    if (!response) {
      const full = await env.ASSETS.fetch(new Request(url, {headers: {'Accept-Encoding': 'identity'}}));
      if (full.status !== 200) return full;
      const headers = new Headers(full.headers);
      headers.set('Content-Length', String(spec.size));
      headers.set('Cache-Control', 'public, max-age=86400');
      headers.set('ETag', `"${spec.sha256}"`);
      headers.set('Accept-Ranges', 'bytes');
      await cache.put(key, new Response(full.body, {headers}));
      response = await cache.match(lookup);
    }
    if (!response) return new Response('Tile cache unavailable; retry shortly.', {status: 503});
    const result = new Response(response.body, response);
    result.headers.set('Cache-Control', 'public, max-age=0, must-revalidate');
    result.headers.set('X-Robots-Tag', 'noindex, nofollow');
    return result;
  },
};
