import { lazy, Suspense } from 'react';
import { ClientOnly, createFileRoute } from '@tanstack/react-router';
import WelcomePrimer from '../components/WelcomePrimer';
import { releases } from '../data/releases';

const Explorer = lazy(() => import('../App'));

export const Route = createFileRoute('/')({ component: Home });

function Introduction() {
  return (
    <main className="site-introduction">
      <h1>Future Risk Index</h1>
      <p role="status">Loading the interactive map…</p>
      <noscript>The interactive map requires JavaScript. You can still read the guide and version documents.</noscript>
      <nav aria-label="Version documentation">
        {releases.map(item => <p key={item.id}>
          {item.title}: <a href={`${import.meta.env.BASE_URL}versions/${item.id}/methodology.html`}>Methodology</a>
          {' · '}<a href={`${import.meta.env.BASE_URL}versions/${item.id}/data.html`}>Data</a>
        </p>)}
      </nav>
      <WelcomePrimer />
    </main>
  );
}

function Home() {
  return (
    <ClientOnly fallback={<Introduction />}>
      <Suspense fallback={<Introduction />}><Explorer /></Suspense>
    </ClientOnly>
  );
}
