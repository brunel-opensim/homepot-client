import { describe, it, expect } from 'vitest';
import {
  isOwnCommand,
  foreignCommands,
  lastAttributedCommand,
  lastActorLabel,
  newForeignCommands,
} from './deviceActivity';

const ME = 'tech@example.com';
const COLLEAGUE = 'other@example.com';

const command = (id, issued_by, extra = {}) => ({
  command_id: id,
  command_type: 'restart',
  status: 'completed',
  created_at: '2026-09-29T10:00:00Z',
  issued_by,
  ...extra,
});

describe('isOwnCommand', () => {
  it('is true when the actor matches the signed-in user', () => {
    expect(isOwnCommand(command('1', ME), ME)).toBe(true);
  });

  it('is false when somebody else issued it', () => {
    expect(isOwnCommand(command('1', COLLEAGUE), ME)).toBe(false);
  });

  it('is false when the command has no recorded actor', () => {
    expect(isOwnCommand(command('1', null), ME)).toBe(false);
  });

  it('is false when there is no signed-in user to compare against', () => {
    expect(isOwnCommand(command('1', ME), null)).toBe(false);
  });

  it('tolerates a missing command', () => {
    expect(isOwnCommand(null, ME)).toBe(true);
  });
});

describe('foreignCommands', () => {
  it('returns only commands from other people', () => {
    const history = [command('1', ME), command('2', COLLEAGUE), command('3', ME)];
    expect(foreignCommands(history, ME).map((c) => c.command_id)).toEqual(['2']);
  });

  it('never reports unattributed commands as foreign', () => {
    const history = [command('1', null), command('2', undefined)];
    expect(foreignCommands(history, ME)).toEqual([]);
  });

  it('returns an empty list without a signed-in user', () => {
    expect(foreignCommands([command('1', COLLEAGUE)], null)).toEqual([]);
  });

  it('tolerates a non-array history', () => {
    expect(foreignCommands(null, ME)).toEqual([]);
  });
});

describe('lastAttributedCommand / lastActorLabel', () => {
  it('finds the newest command that names an actor', () => {
    const history = [command('2', COLLEAGUE), command('1', ME)];
    expect(lastAttributedCommand(history).command_id).toEqual('2');
    expect(lastActorLabel(history)).toEqual(COLLEAGUE);
  });

  it('skips leading commands with no actor', () => {
    const history = [command('3', null), command('2', ME), command('1', COLLEAGUE)];
    expect(lastActorLabel(history)).toEqual(ME);
  });

  it('returns null when nothing records an actor', () => {
    expect(lastActorLabel([command('1', null)])).toBeNull();
    expect(lastActorLabel([])).toBeNull();
  });
});

describe('newForeignCommands', () => {
  it('reports a colleague command the page has not seen before', () => {
    const history = [command('2', COLLEAGUE), command('1', ME)];
    expect(newForeignCommands(history, ['1'], ME).map((c) => c.command_id)).toEqual(['2']);
  });

  it('reports nothing once the page has already seen the command', () => {
    const history = [command('2', COLLEAGUE), command('1', ME)];
    expect(newForeignCommands(history, ['2', '1'], ME)).toEqual([]);
  });

  it('does not report the current user own commands', () => {
    const history = [command('2', ME)];
    expect(newForeignCommands(history, ['1'], ME)).toEqual([]);
  });
});
