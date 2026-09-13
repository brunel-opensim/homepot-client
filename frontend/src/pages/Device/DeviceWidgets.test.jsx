import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { Sparkline } from './DeviceWidgets';

function pathOf(container) {
  const path = container.querySelector('path[stroke]');
  if (!path) return null;
  return path.getAttribute('d');
}

function areaDOf(container) {
  const area = Array.from(container.querySelectorAll('path')).find(
    (p) => p.getAttribute('fill') !== 'none'
  );
  if (!area) return null;
  return area.getAttribute('d');
}

describe('Sparkline', () => {
  it('renders a visible horizontal line for a constant series', () => {
    const { container } = render(<Sparkline data={[4.6, 4.6, 4.6, 4.6]} height={40} />);
    expect(pathOf(container)).toBe('M0,20 L 48,20 L 96,20 L 144,20');
  });

  it('draws a constant series as a clean line, not a solid bar', () => {
    const { container } = render(<Sparkline data={[4.6, 4.6, 4.6, 4.6]} height={40} />);
    expect(areaDOf(container)).toBeNull();
  });

  it('spans the full height and fills an area for a varying series', () => {
    const { container } = render(<Sparkline data={[10, 20]} height={40} />);
    expect(pathOf(container)).toBe('M0,40 L 144,0');
    expect(areaDOf(container)).toBe('M0,40 L 144,0 L 144,40 L 0,40 Z');
  });

  it('ignores non-numeric samples', () => {
    const { container } = render(<Sparkline data={[1, null, undefined, NaN, 3]} height={40} />);
    expect(pathOf(container)).toBe('M0,40 L 144,0');
  });

  it('renders the empty svg when there are no numeric samples', () => {
    const { container } = render(<Sparkline data={[null, undefined]} height={40} />);
    expect(container.querySelector('path')).toBeNull();
  });
});
