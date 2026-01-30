import { lazy, Suspense } from 'react';

// Lazy load client and admin views
const SplitChatView = lazy(() => import('./components/SplitChatView'));
const ClientApp = lazy(() => import('./client/ClientApp'));
const ClientOnboarding = lazy(() => import('./client/ClientOnboarding'));

function LoadingFallback() {
  return (
    <div className="h-screen flex items-center justify-center bg-gray-100 dark:bg-[#0a0a0f]">
      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function App() {
  // Normalize pathname (remove trailing slash)
  const pathname = window.location.pathname.replace(/\/$/, '') || '/';

  // Route to appropriate view
  // Order matters: check specific routes before prefix matches
  const getView = () => {
    // Onboarding routes (check BEFORE /client prefix match)
    if (pathname === '/client_input' || pathname === '/onboard') {
      return <ClientOnboarding />;
    }
    // Client dashboard (any path starting with /client)
    if (pathname.startsWith('/client')) {
      return <ClientApp />;
    }
    // Admin view (default)
    return <SplitChatView />;
  };

  return (
    <Suspense fallback={<LoadingFallback />}>
      {getView()}
    </Suspense>
  );
}

export default App;
