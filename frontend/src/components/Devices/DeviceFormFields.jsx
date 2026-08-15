import React from 'react';

const labelClass = 'text-sm font-medium leading-none text-gray-300';
const inputClass =
  'flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50';
const readOnlyInputClass =
  'flex h-10 w-full rounded-md border border-border bg-background/50 px-3 py-2 text-sm text-gray-500 shadow-sm transition-colors focus-visible:outline-none disabled:cursor-not-allowed';

export default function DeviceFormFields({ formData, handleChange, sites, readOnly = false }) {
  return (
    <>
      {/* Site Selection */}
      <div className="space-y-2">
        <label htmlFor="site_id" className={labelClass}>
          {readOnly ? 'Assigned Site' : 'Assign to Site'}{' '}
          {!readOnly && <span className="text-red-400">*</span>}
        </label>
        <select
          id="site_id"
          name="site_id"
          required={!readOnly}
          disabled={readOnly}
          className={readOnly ? readOnlyInputClass : inputClass}
          value={formData.site_id}
          onChange={handleChange}
        >
          <option value="" disabled>
            Select a site
          </option>
          {sites.map((site) => (
            <option key={site.id} value={site.site_id}>
              {site.name} ({site.site_id})
            </option>
          ))}
        </select>
        {!readOnly && sites.length === 0 && (
          <p className="text-xs text-yellow-500">No sites available. Please create a site first.</p>
        )}
      </div>

      {/* Device Basic Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label htmlFor="name" className={labelClass}>
            Device Name <span className="text-red-400">*</span>
          </label>
          <input
            id="name"
            name="name"
            type="text"
            required
            className={inputClass}
            placeholder="e.g. Front Desk POS"
            value={formData.name}
            onChange={handleChange}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="device_id" className={labelClass}>
            Device ID {!readOnly && <span className="text-red-400">*</span>}
          </label>
          <input
            id="device_id"
            name="device_id"
            type="text"
            required={!readOnly}
            disabled={readOnly}
            className={readOnly ? readOnlyInputClass : inputClass}
            placeholder="e.g. dev-001"
            value={formData.device_id}
            onChange={handleChange}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="device_type" className={labelClass}>
          Device Type <span className="text-red-400">*</span>
        </label>
        <select
          id="device_type"
          name="device_type"
          required
          className={inputClass}
          value={formData.device_type}
          onChange={handleChange}
        >
          <option value="pos_terminal">POS Terminal</option>
          <option value="iot_sensor">IoT Sensor</option>
          <option value="industrial_controller">Industrial Controller</option>
          <option value="gateway">Gateway</option>
          <option value="unknown">Other</option>
        </select>
      </div>

      {/* Optional Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label htmlFor="ip_address" className={labelClass}>
            IP Address
          </label>
          <input
            id="ip_address"
            name="ip_address"
            type="text"
            className={inputClass}
            placeholder="e.g. 192.168.1.100"
            value={formData.ip_address}
            onChange={handleChange}
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="mac_address" className={labelClass}>
            MAC Address
          </label>
          <input
            id="mac_address"
            name="mac_address"
            type="text"
            className={inputClass}
            placeholder="e.g. 00:1A:2B:3C:4D:5E"
            value={formData.mac_address}
            onChange={handleChange}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="firmware_version" className={labelClass}>
          Firmware Version
        </label>
        <input
          id="firmware_version"
          name="firmware_version"
          type="text"
          className={inputClass}
          placeholder="e.g. v1.2.3"
          value={formData.firmware_version}
          onChange={handleChange}
        />
      </div>
    </>
  );
}
