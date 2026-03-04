import { cn } from '@/lib/utils';
import { Button } from '../ui/Button';

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export function Pagination({ page, pages, total, onPageChange, className }: PaginationProps) {
  return (
    <div className={cn('flex items-center justify-between', className)}>
      <p className="text-sm text-muted-foreground">
        Page {page} of {pages} ({total} total)
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
