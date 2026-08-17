import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SiteDeleteDialog from '../../src/components/Sites/SiteDeleteDialog';

vi.mock('../../src/utils/analytics', () => ({
  trackActivity: vi.fn().mockResolvedValue(undefined),
}));

describe('SiteDeleteDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const props = {
    isOpen: true,
    onClose: vi.fn(),
    onConfirm: vi.fn().mockResolvedValue(undefined),
    siteName: 'Head Office',
    isDeleting: false,
  };

  it('renders archive mode by default with Archive Site confirm', () => {
    render(<SiteDeleteDialog {...props} />);

    expect(screen.getByRole('button', { name: 'Archive Site' })).toBeInTheDocument();
  });

  it('calls onConfirm with archive when Archive Site is clicked', async () => {
    render(<SiteDeleteDialog {...props} />);

    fireEvent.click(screen.getByRole('button', { name: 'Archive Site' }));

    expect(props.onConfirm).toHaveBeenCalledWith('archive');
  });

  it('switches to purge mode and requires the site name to confirm', () => {
    render(<SiteDeleteDialog {...props} />);

    fireEvent.click(screen.getByText('Purge'));

    const confirmButton = screen.getByRole('button', { name: 'Purge Site' });
    expect(confirmButton).toBeInTheDocument();
    expect(confirmButton).toBeDisabled();

    const input = screen.getByPlaceholderText('Head Office');
    fireEvent.change(input, { target: { value: 'wrong name' } });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(input, { target: { value: 'Head Office' } });
    expect(confirmButton).toBeEnabled();
  });

  it('calls onConfirm with purge once the name matches', async () => {
    render(<SiteDeleteDialog {...props} />);

    fireEvent.click(screen.getByText('Purge'));
    fireEvent.change(screen.getByPlaceholderText('Head Office'), {
      target: { value: 'Head Office' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Purge Site' }));

    expect(props.onConfirm).toHaveBeenCalledWith('purge');
  });

  it('resets mode and confirmation text when reopened', () => {
    const { rerender } = render(<SiteDeleteDialog {...props} />);

    fireEvent.click(screen.getByText('Purge'));
    fireEvent.change(screen.getByPlaceholderText('Head Office'), {
      target: { value: 'Head Office' },
    });

    rerender(<SiteDeleteDialog {...props} isOpen={false} />);
    rerender(<SiteDeleteDialog {...props} isOpen={true} />);

    expect(screen.getByRole('button', { name: 'Archive Site' })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Head Office')).not.toBeInTheDocument();
  });
});
