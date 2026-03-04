import { useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/observables': 'Observables',
  '/feeds': 'Feeds',
  '/settings': 'Settings',
};

interface HeaderProps {
  apiKeyPrefix?: string;
  onLogout?: () => void;
  className?: string;
}

export function Header({ apiKeyPrefix, onLogout, className }: HeaderProps) {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'EmergentCTI';

  return (
    <header
      className={cn(
        'flex h-14 items-center justify-between border-b border-border bg-card px-6',
        className,
      )}
    >
      <h1 className="text-lg font-semibold text-foreground">{title}</h1>

      <div className="flex items-center gap-3">
        {apiKeyPrefix && (
          <Badge variant="outline" className="font-mono text-xs">
            Key: {apiKeyPrefix}...
          </Badge>
        )}
        {onLogout && (
          <Button variant="ghost" size="sm" onClick={onLogout}>
            Logout
          </Button>
        )}
      </div>
    </header>
  );
}
