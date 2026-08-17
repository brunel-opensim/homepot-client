import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DeviceDeleteDialog from '../../src/components/Devices/DeviceDeleteDialog';

describe('DeviceDeleteDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const props = {
    isOpen: true,
    onClose: vi.fn(),
    onConfirm: vi.fn().mockResolvedValue(undefined),
    deviceName: 'pos-001',
    isDeleting: false,
  };

  it('renders archive mode by default with Archive Device confirm', () => {
    render(<DeviceDeleteDialog {...props} />);

    expect(screen.getByRole('button', { name: 'Archive Device' })).toBeInTheDocument();
  });

  it('calls onConfirm with archive when Archive Device is clicked', async () => {
    render(<DeviceDeleteDialog {...props} />);

    fireEvent.click(screen.getByRole('button', { name: 'Archive Device' }));

    expect(props.onConfirm).toHaveBeenCalledWith('archive');
  });

  it('switches to purge mode and requires the device name to confirm', () => {
    render(<DeviceDeleteDialog {...props} />);

    fireEvent.click(screen.getByText('Purge'));

    const confirmButton = screen.getByRole('button', { name: 'Purge Device' });
    expect(confirmButton).toBeInTheDocument();
    expect(confirmButton).toBeDisabled();

    const input = screen.getByPlaceholderText('pos-001');
    fireEvent.change(input, { target: { value: 'pos-999' } });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(input, { target: { value: 'pos-001' } });
    expect(confirmButton).toBeEnabled();
  });

  it('calls onConfirm with purge once the name matches', async () => {
    render(<DeviceDeleteDialog {...props} />);

    fireEvent.click(screen.getByText('Purge'));
    fireEvent.change(screen.getByPlaceholderText('pos-001'), {
      target: { value: 'pos-001' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Purge Device' }));

    expect(props.onConfirm).toHaveBeenCalledWith('purge');
  });
});
