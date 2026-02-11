import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';

export function Header() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-card/95 backdrop-blur px-6">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-medium text-muted-foreground">
          EmergentCTI
        </h2>
      </div>

      <div className="flex items-center gap-3">
        {/* Theme toggle */}
        <Button variant="ghost" size="icon" onClick={toggleTheme} title="Toggle theme">
          <span className="text-lg">{theme === 'dark' ? '\u263C' : '\u263E'}</span>
        </Button>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger onClick={() => setMenuOpen(!menuOpen)}>
            <div className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-accent transition-colors cursor-pointer">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-primary text-sm font-semibold">
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-sm font-medium leading-tight">
                  {user?.username || 'User'}
                </p>
                <p className="text-xs text-muted-foreground capitalize">
                  {user?.role || 'analyst'}
                </p>
              </div>
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent open={menuOpen} onClose={() => setMenuOpen(false)}>
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                navigate('/settings');
                setMenuOpen(false);
              }}
            >
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} destructive>
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
