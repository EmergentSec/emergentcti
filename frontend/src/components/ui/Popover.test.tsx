// frontend/src/components/ui/Popover.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Popover } from './Popover';

describe('Popover', () => {
  it('opens on trigger click and closes on click-away', () => {
    render(
      <Popover trigger={<button>Export</button>}>
        <div>panel-content</div>
      </Popover>,
    );
    expect(screen.queryByText('panel-content')).toBeNull();
    fireEvent.click(screen.getByText('Export'));
    expect(screen.getByText('panel-content')).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText('panel-content')).toBeNull();
  });
});
