import { useCallback, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Plus, X } from '@phosphor-icons/react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '../ui/Button';
import { getFocusable, trapTab } from '../ui/focus';
import { EmergentLogo } from '../common/EmergentLogo';
import { DRAWER_ATTR, Header } from './Header';
import { Sidebar } from './Sidebar';
import { PAGE_HEADING_ID, PageHeader } from './PageHeader';
import { getPageMeta } from './navigation';
import { DESKTOP_QUERY, useMediaQuery } from './useMediaQuery';

const SIDEBAR_ID = 'app-sidebar';

interface AppLayoutProps {
  /** @deprecated — the shell reads useAuth() directly; kept for back-compat with App.tsx */
  username?: string;
  /** @deprecated — the shell reads useAuth() directly; kept for back-compat with App.tsx */
  onLogout?: () => void;
}

/**
 * App shell: full-width top bar; sidebar below it (persistent and collapsible
 * at `lg`+, an overlay drawer below `lg`); dark page-header band from route
 * meta; centred content column.
 */
export function AppLayout(_props: AppLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const isDesktop = useMediaQuery(DESKTOP_QUERY);

  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
    menuButtonRef.current?.focus();
  }, []);

  // Closing the drawer by navigating unmounts the focused link; send focus to
  // the new page's heading instead of letting it fall to <body>.
  const drawerOpenRef = useRef(drawerOpen);
  drawerOpenRef.current = drawerOpen;
  const [headingFocusTick, setHeadingFocusTick] = useState(0);
  const closeDrawerToContent = useCallback(() => {
    setDrawerOpen(false);
    setHeadingFocusTick((t) => t + 1);
  }, []);

  useEffect(() => {
    if (headingFocusTick === 0) return;
    const target = document.getElementById(PAGE_HEADING_ID) ?? document.getElementById('main-content');
    target?.focus();
  }, [headingFocusTick]);

  const onMenuClick = () => {
    if (isDesktop) setCollapsed((c) => !c);
    else setDrawerOpen((o) => !o);
  };

  // Leaving the narrow layout dismisses the drawer.
  useEffect(() => {
    if (isDesktop) setDrawerOpen(false);
  }, [isDesktop]);

  // Navigating (including browser back/forward) closes the drawer.
  useEffect(() => {
    if (drawerOpenRef.current) closeDrawerToContent();
  }, [location.pathname, closeDrawerToContent]);

  // Drawer: move focus in, trap Tab, close on Esc, lock page scroll.
  useEffect(() => {
    if (!drawerOpen) return;
    const panel = drawerRef.current;
    const active = panel?.querySelector<HTMLElement>('[aria-current="page"]');
    (active ?? getFocusable(panel)[0] ?? panel)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeDrawer();
      } else {
        trapTab(e, drawerRef.current);
      }
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [drawerOpen, closeDrawer]);

  const meta = getPageMeta(location.pathname);
  const showSidebar = isDesktop && !collapsed;
  // Add Observable belongs to the Observables list only (not detail pages).
  const onObservablesList = location.pathname.replace(/\/+$/, '') === '/observables';

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:rounded-lg focus:bg-card focus:px-3 focus:py-2 focus:text-sm focus:shadow-lg"
      >
        Skip to content
      </a>

      <Header
        onMenuClick={onMenuClick}
        menuExpanded={isDesktop ? !collapsed : drawerOpen}
        menuControls={SIDEBAR_ID}
        menuButtonRef={menuButtonRef}
        drawerOpen={drawerOpen}
        onDismissDrawer={() => setDrawerOpen(false)}
        showAppearance={isDesktop && collapsed}
      />

      <div className="flex">
        {showSidebar && (
          <Sidebar
            id={SIDEBAR_ID}
            className="sticky top-14 h-[calc(100vh-3.5rem)] shrink-0 border-r border-border"
          />
        )}

        <div className="min-w-0 flex-1">
          {meta && (
            <PageHeader
              title={meta.title}
              subtitle={meta.subtitle}
              icon={meta.icon}
              actions={
                isAdmin && onObservablesList ? (
                  <Button
                    variant="masthead"
                    title="Add Observable"
                    className="w-9 px-0 sm:w-auto sm:px-3.5"
                    onClick={() => navigate('/observables?create=1')}
                  >
                    <Plus size={14} weight="bold" aria-hidden="true" />
                    <span className="sr-only sm:not-sr-only">Add Observable</span>
                  </Button>
                ) : null
              }
            />
          )}
          <main id="main-content" tabIndex={-1} className="mx-auto max-w-[1320px] px-4 py-6 focus:outline-none sm:px-6">
            <Outlet />
          </main>
        </div>
      </div>

      {!isDesktop && drawerOpen && (
        <div className="fixed inset-0 z-40">
          <div
            data-testid="drawer-backdrop"
            aria-hidden="true"
            className="absolute inset-0 bg-overlay backdrop-blur-[2px]"
            onClick={closeDrawer}
          />
          <div
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            {...{ [DRAWER_ATTR]: '' }}
            tabIndex={-1}
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-card shadow-2xl focus:outline-none"
          >
            <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-4">
              <EmergentLogo size={24} className="shrink-0 text-foreground" />
              <span className="flex-1 truncate text-[15px] font-semibold tracking-tight">EmergentCTI</span>
              <button
                type="button"
                aria-label="Close navigation"
                onClick={closeDrawer}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-hover hover:text-foreground"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <Sidebar id={SIDEBAR_ID} className="min-h-0 w-full flex-1" onNavigate={closeDrawerToContent} />
          </div>
        </div>
      )}
    </div>
  );
}

export default AppLayout;
