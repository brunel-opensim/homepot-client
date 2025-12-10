import React, { useState } from 'react';
import { X, Plus, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function DeviceAddDialog({ isOpen, onClose, onAdd, isAdding }) {
  const [formData, setFormData] = useState({
    name: '',
    device_id: '',
    device_type: '',
    ip_address: '',
    config: '{\n  "gateway_url": ""\n}',
  });
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Validate JSON config
    let parsedConfig = {};
    try {
      parsedConfig = JSON.parse(formData.config);
    } catch {
      setError('Invalid JSON in Config field');
      return;
    }

    try {
      await onAdd({
        ...formData,
        config: parsedConfig,
      });
    } catch (err) {
      // Parent should handle the error and maybe throw it back if it wants the dialog to show it?
      // Or parent sets a prop?
      // Let's assume onAdd throws if it fails.
      console.error(err);
      setError(err.message || 'Failed to add device');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg bg-[#141a24] p-6 shadow-lg border border-[#1f2735] animate-in fade-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Plus className="h-5 w-5 text-teal-500" />
            Add New Device
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-md mb-6 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="name" className="text-sm font-medium leading-none text-gray-300">
              Device Name <span className="text-red-400">*</span>
            </label>
            <input
              id="name"
              name="name"
              type="text"
              required
              className="flex h-10 w-full rounded-md border border-[#1f2735] bg-[#0b0e13] px-3 py-2 text-sm text-white shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 focus-visible:outline-none focus-visible:border-teal-500 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="e.g. POS Terminal 1"
              value={formData.name}
              onChange={handleChange}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label htmlFor="device_id" className="text-sm font-medium leading-none text-gray-300">
                Device ID <span className="text-red-400">*</span>
              </label>
              <input
                id="device_id"
                name="device_id"
                type="text"
                required
                className="flex h-10 w-full rounded-md border border-[#1f2735] bg-[#0b0e13] px-3 py-2 text-sm text-white shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 focus-visible:outline-none focus-visible:border-teal-500 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. pos-terminal-001"
                value={formData.device_id}
                onChange={handleChange}
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="device_type"
                className="text-sm font-medium leading-none text-gray-300"
              >
                Device Type <span className="text-red-400">*</span>
              </label>
              <input
                id="device_type"
                name="device_type"
                type="text"
                required
                className="flex h-10 w-full rounded-md border border-[#1f2735] bg-[#0b0e13] px-3 py-2 text-sm text-white shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 focus-visible:outline-none focus-visible:border-teal-500 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. pos_terminal"
                value={formData.device_type}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="ip_address" className="text-sm font-medium leading-none text-gray-300">
              IP Address <span className="text-red-400">*</span>
            </label>
            <input
              id="ip_address"
              name="ip_address"
              type="text"
              required
              className="flex h-10 w-full rounded-md border border-[#1f2735] bg-[#0b0e13] px-3 py-2 text-sm text-white shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 focus-visible:outline-none focus-visible:border-teal-500 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="e.g. 192.168.1.10"
              value={formData.ip_address}
              onChange={handleChange}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="config" className="text-sm font-medium leading-none text-gray-300">
              Configuration (JSON)
            </label>
            <textarea
              id="config"
              name="config"
              className="flex min-h-[100px] w-full rounded-md border border-[#1f2735] bg-[#0b0e13] px-3 py-2 text-sm text-white shadow-sm font-mono placeholder:text-gray-500 focus-visible:outline-none focus-visible:border-teal-500 disabled:cursor-not-allowed disabled:opacity-50"
              value={formData.config}
              onChange={handleChange}
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isAdding}
              className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isAdding}
              className="bg-transparent text-teal-400 border border-teal-400 hover:bg-teal-400/10"
            >
              {isAdding ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                'Add Device'
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
