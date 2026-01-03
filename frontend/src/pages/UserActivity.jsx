import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  Loader2,
  Activity,
  Users,
  FileText,
  Clock,
  MousePointer,
  Search,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getUserActivities } from '@/utils/analytics';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

export default function UserActivityDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [activities, setActivities] = useState([]);
  const [mostVisited, setMostVisited] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    uniqueUsers: 0,
    topPage: 'N/A',
  });

  const firstLoad = React.useRef(false);

  useEffect(() => {
    if (firstLoad.current) return;
    firstLoad.current = true;

    const fetchData = async () => {
      try {
        const res = await getUserActivities(100); // Fetch more for better stats

        const acts = res.activities || [];
        setActivities(acts);

        // Calculate Stats
        const uniqueUsers = new Set(acts.map((a) => a.user_id).filter(Boolean)).size;

        // Build Most Visited
        const pageCountMap = {};
        acts.forEach((a) => {
          if (!a.page_url) return;
          pageCountMap[a.page_url] = (pageCountMap[a.page_url] || 0) + 1;
        });

        const counted = Object.entries(pageCountMap)
          .map(([page, count]) => ({ page, count }))
          .sort((a, b) => b.count - a.count);

        const max = counted[0]?.count || 1;
        const topPage = counted[0]?.page || 'N/A';

        setStats({
          total: acts.length,
          uniqueUsers,
          topPage,
        });

        setMostVisited(
          counted.slice(0, 10).map((item) => ({
            ...item,
            percent: Math.round((item.count / max) * 100),
          }))
        );
      } catch (err) {
        console.error('Failed to load analytics:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getActivityIcon = (type) => {
    switch (type) {
      case 'page_view':
        return <FileText className="w-4 h-4 text-blue-400" />;
      case 'click':
        return <MousePointer className="w-4 h-4 text-green-400" />;
      case 'search':
        return <Search className="w-4 h-4 text-purple-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Activity className="w-4 h-4 text-slate-400" />;
    }
  };

  const getActivityBadge = (type) => {
    let colorClass = 'bg-slate-800 text-slate-400 border-slate-700';
    if (type === 'page_view') colorClass = 'bg-blue-900/30 text-blue-400 border-blue-800';
    if (type === 'click') colorClass = 'bg-green-900/30 text-green-400 border-green-800';
    if (type === 'search') colorClass = 'bg-purple-900/30 text-purple-400 border-purple-800';
    if (type === 'error') colorClass = 'bg-red-900/30 text-red-400 border-red-800';

    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${colorClass}`}
      >
        {type.replace('_', ' ')}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex justify-center items-center">
        <Loader2 className="h-8 w-8 text-teal-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-200">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <Button
            variant="ghost"
            onClick={() => navigate('/dashboard')}
            className="pl-0 hover:pl-1 transition-all text-slate-400 hover:text-white hover:bg-transparent mb-2"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Button>
          <h1 className="text-3xl font-bold text-white tracking-tight">User Activity</h1>
          <p className="text-slate-400 mt-1">
            Track user interactions, page views, and system usage.
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Total Activities</CardTitle>
              <Activity className="h-4 w-4 text-teal-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">{stats.total}</div>
              <p className="text-xs text-slate-500 mt-1">Recorded events</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Active Users</CardTitle>
              <Users className="h-4 w-4 text-blue-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-white">{stats.uniqueUsers}</div>
              <p className="text-xs text-slate-500 mt-1">Unique sessions</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900/50 border-slate-800">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Top Page</CardTitle>
              <FileText className="h-4 w-4 text-purple-400" />
            </CardHeader>
            <CardContent>
              <div className="text-lg font-bold text-white truncate" title={stats.topPage}>
                {stats.topPage}
              </div>
              <p className="text-xs text-slate-500 mt-1">Most visited</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Activities Table */}
          <Card className="lg:col-span-2 bg-slate-900/50 border-slate-800 flex flex-col">
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
                <Clock className="w-5 h-5 text-slate-400" />
                Recent Activities
              </CardTitle>
            </CardHeader>
            <div className="flex-1 overflow-auto max-h-[600px]">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-slate-900/80 text-slate-400 sticky top-0 z-10 backdrop-blur-sm">
                  <tr>
                    <th className="px-6 py-3 font-medium">Type</th>
                    <th className="px-6 py-3 font-medium">User</th>
                    <th className="px-6 py-3 font-medium">Details</th>
                    <th className="px-6 py-3 font-medium text-right">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {activities.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-6 py-12 text-center text-slate-500">
                        No activity data recorded yet.
                      </td>
                    </tr>
                  ) : (
                    activities.slice(0, 50).map((a, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/50 transition-colors">
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-2">
                            {getActivityIcon(a.activity_type)}
                            {getActivityBadge(a.activity_type)}
                          </div>
                        </td>
                        <td className="px-6 py-3 text-slate-300 font-mono text-xs">
                          {a.user_id || 'Anonymous'}
                        </td>
                        <td
                          className="px-6 py-3 text-slate-400 max-w-xs truncate"
                          title={a.page_url}
                        >
                          {a.page_url}
                        </td>
                        <td className="px-6 py-3 text-right text-slate-500 text-xs whitespace-nowrap">
                          {new Date(a.timestamp).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Most Visited Pages */}
          <Card className="bg-slate-900/50 border-slate-800 h-fit">
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-slate-400" />
                Most Visited Pages
              </CardTitle>
            </CardHeader>
            <CardContent>
              {mostVisited.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">
                  No page visit data available.
                </p>
              ) : (
                <div className="space-y-5">
                  {mostVisited.map((item, idx) => (
                    <div key={idx} className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span
                          className="text-slate-300 font-medium truncate max-w-[200px]"
                          title={item.page}
                        >
                          {item.page}
                        </span>
                        <span className="text-slate-400 font-mono">{item.count} visits</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-teal-500 to-emerald-500 rounded-full transition-all duration-500"
                          style={{ width: `${item.percent}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
