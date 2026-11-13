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

  it('renders a purge-only confirmation', () => {
    render(<DeviceDeleteDialog {...props} />);

    expect(screen.getByRole('heading', { name: 'Purge Device' })).toBeInTheDocument();
    expect(screen.queryByText('Archive')).not.toBeInTheDocument();
  });

  it('requires the device name before purge can be confirmed', () => {
    render(<DeviceDeleteDialog {...props} />);

    const confirmButton = screen.getByRole('button', { name: 'Purge Device' });
    expect(confirmButton).toBeDisabled();

    const input = screen.getByPlaceholderText('pos-001');
    fireEvent.change(input, { target: { value: 'pos-999' } });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(input, { target: { value: 'pos-001' } });
    expect(confirmButton).toBeEnabled();
  });

  it('calls onConfirm once the name matches', async () => {
    render(<DeviceDeleteDialog {...props} />);

    fireEvent.change(screen.getByPlaceholderText('pos-001'), {
      target: { value: 'pos-001' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Purge Device' }));

    expect(props.onConfirm).toHaveBeenCalledTimes(1);
  });
});
