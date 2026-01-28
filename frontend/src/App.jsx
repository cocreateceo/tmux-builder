import { lazy, Suspense } from 'react';

// Lazy load client and admin views
const SplitChatView = lazy(() => import('./components/SplitChatView'));
const ClientApp = lazy(() => import('./client/ClientApp'));

function LoadingFallback() {
  return (
    <div className="h-screen flex items-center justify-center bg-gray-100 dark:bg-[#0a0a0f]">
      <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function App() {
  // Check if we're on the client route
  const isClientRoute = window.location.pathname.startsWith('/client');

  return (
    <Suspense fallback={<LoadingFallback />}>
      {isClientRoute ? <ClientApp /> : <SplitChatView />}
    </Suspense>
  );
}

export default App;
