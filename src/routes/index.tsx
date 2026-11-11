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
      <p>The interactive map requires JavaScript. You can still read the guide and version documents.</p>
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

function LoadingExplorer() {
  return (
    <div className="atlas-app explorer-loading-shell" aria-busy="true">
      <header className="site-header">
        <a className="brand" href={import.meta.env.BASE_URL}><span><h1>Future Risk Index</h1></span></a>
      </header>
      <main className="explorer-loading"><p role="status">Loading map…</p></main>
    </div>
  );
}

function Home() {
  return (
    <>
      <noscript>
        <style>{'.explorer-loading-shell{display:none}'}</style>
        <Introduction />
      </noscript>
      <ClientOnly fallback={<LoadingExplorer />}>
        <Suspense fallback={<LoadingExplorer />}><Explorer /></Suspense>
      </ClientOnly>
    </>
  );
}
