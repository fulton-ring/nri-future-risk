import { createRootRoute, HeadContent, Outlet, Scripts } from '@tanstack/react-router';
import appCss from '../index.css?url';

const title = 'Future Climate Risk Index';
const description = 'Explore how climate change affects county economic losses and risk. Compare FEMA hazard projections, emissions pathways and time periods.';
const canonical = 'https://fulton-ring.github.io/nri-future-risk/';

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1.0, viewport-fit=cover' },
      { title },
      { name: 'description', content: description },
      { name: 'author', content: 'Public Environmental Data Partners and Fulton Ring' },
      { property: 'og:title', content: title },
      { property: 'og:description', content: description },
      { property: 'og:url', content: canonical },
      { property: 'og:type', content: 'website' },
    ],
    links: [
      { rel: 'stylesheet', href: appCss },
      { rel: 'canonical', href: canonical },
    ],
  }),
  component: RootDocument,
});

function RootDocument() {
  return (
    <html lang="en">
      <head><HeadContent /></head>
      <body>
        <Outlet />
        <script defer src="https://cloud.umami.is/script.js" data-website-id="0202318a-3c45-4eb5-bc1b-c8d0ca99240b" />
        <Scripts />
      </body>
    </html>
  );
}
