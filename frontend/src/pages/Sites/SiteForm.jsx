import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Save } from 'lucide-react';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function SiteForm() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEditMode = !!id;

  const [formData, setFormData] = useState({
    name: '',
    site_id: '',
    location: '',
    description: '',
  });
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(isEditMode);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) {
      setInitialLoading(false);
      return;
    }

    const fetchSite = async () => {
      try {
        const data = await api.sites.get(id);
        setFormData({
          name: data.name || '',
          site_id: data.site_id || data.id || '',
          location: data.location || '',
          description: data.description || '',
        });
      } catch (err) {
        console.error('Failed to fetch site:', err);
        setError('Failed to load site details.');
      } finally {
        setInitialLoading(false);
      }
    };

    fetchSite();
  }, [id]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isEditMode) {
        await api.sites.update(id, formData);
      } else {
        await api.sites.create(formData);
      }
      navigate('/sites');
    } catch (err) {
      console.error('Failed to save site:', err);
      setError(api.apiHelpers?.formatError(err) || 'Failed to save site. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground py-6 px-4">
      <div className="container mx-auto max-w-2xl">
        <Button
          variant="ghost"
          onClick={() => navigate('/sites')}
          className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Sites
        </Button>

        <div className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight text-white">
            {isEditMode ? 'Edit Site' : 'Create New Site'}
          </h1>
          <p className="text-gray-400">
            {isEditMode
              ? 'Update site details and configuration.'
              : 'Add a new physical location to your network.'}
          </p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-md mb-6 text-sm">
            {error}
          </div>
        )}

        <Card className="p-6 bg-card border-border">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label htmlFor="name" className="text-sm font-medium leading-none text-gray-300">
                Site Name <span className="text-red-400">*</span>
              </label>
              <input
                id="name"
                name="name"
                type="text"
                required
                className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. Main Office, Warehouse A"
                value={formData.name}
                onChange={handleChange}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="site_id" className="text-sm font-medium leading-none text-gray-300">
                Site ID <span className="text-red-400">*</span>
              </label>
              <input
                id="site_id"
                name="site_id"
                type="text"
                required
                className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. site-123"
                value={formData.site_id}
                onChange={handleChange}
                disabled={isEditMode} // Assuming ID shouldn't change after creation
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="location" className="text-sm font-medium leading-none text-gray-300">
                Location
              </label>
              <input
                id="location"
                name="location"
                type="text"
                className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="e.g. New York, NY"
                value={formData.location}
                onChange={handleChange}
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="description"
                className="text-sm font-medium leading-none text-gray-300"
              >
                Description
              </label>
              <textarea
                id="description"
                name="description"
                className="flex min-h-[80px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="Optional description of this site..."
                value={formData.description}
                onChange={handleChange}
              />
            </div>

            <div className="flex justify-end gap-4 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate('/sites')}
                className="border-[#1f2735] bg-transparent text-gray-300 hover:bg-[#1f2735] hover:text-white"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loading}
                className="bg-teal-600 hover:bg-teal-700 text-white"
              >
                {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {isEditMode ? 'Update Site' : 'Create Site'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
