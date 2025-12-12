import React, { useEffect, useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { getUserActivities } from '@/utils/analytics';
import { Button } from '@/components/ui/button';

export default function UserActivityDashboard() {
  const [loading, setLoading] = useState(true);
  const [activities, setActivities] = useState([]);
  const [mostVisited, setMostVisited] = useState([]);
  const [topSearches, setTopSearches] = useState([]);

  console.log('mostVisited', mostVisited);
  const firstLoad = React.useRef(false);

  useEffect(() => {
    if (firstLoad.current) return;
    firstLoad.current = true;

    const fetchData = async () => {
      try {
        const res = await getUserActivities();

        const acts = res.activities || [];
        setActivities(acts);

        // BUILD MOST VISITED
        const pageCountMap = {};

        acts.forEach((a) => {
          if (!a.page_url) return;
          pageCountMap[a.page_url] = (pageCountMap[a.page_url] || 0) + 1;
        });

        const counted = Object.entries(pageCountMap)
          .map(([page, count]) => ({ page, count }))
          .sort((a, b) => b.count - a.count);

        const max = counted[0]?.count || 1;

        setMostVisited(
          counted.map((item) => ({
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

  //   if (loading) {
  //   return (
  //     <div className="flex justify-center items-center min-h-screen">
  //       <Loader2 className="h-10 w-10 animate-spin text-teal-400" />
  //     </div>
  //   );
  // }

  return (
    <div className="min-h-screen bg-background text-foreground py-8 px-4">
      <Button
        variant="ghost"
        onClick={() => window.history.back()}
        className="mb-4 pl-0 hover:pl-1 transition-all text-gray-400 hover:text-white hover:bg-transparent"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Dashboard
      </Button>

      <div className="container mx-auto max-w-4xl space-y-8">
        {/* === Recent Activities Card === */}
        <Card className="p-6 bg-card border-border">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Activities</h2>

          <div className="overflow-y-auto max-h-64 rounded-md border border-[#1a2533]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#0d131b] sticky top-0 z-10">
                <tr>
                  <th className="px-3 py-2 text-gray-300 font-medium">Activity</th>
                  <th className="px-3 py-2 text-gray-300 font-medium">User</th>
                  <th className="px-3 py-2 text-gray-300 font-medium">Page</th>
                  <th className="px-3 py-2 text-gray-300 font-medium">Time</th>
                </tr>
              </thead>

              <tbody>
                {activities.length === 0 && (
                  <tr>
                    <td colSpan={4} className="text-center text-gray-400 py-4">
                      No activity data yet.
                    </td>
                  </tr>
                )}

                {activities.slice(0, 50).map((a, idx) => (
                  <tr key={idx} className="border-b border-[#1a2533] hover:bg-[#141b26] transition">
                    <td className="px-3 py-2 text-gray-300">{a.activity_type}</td>
                    <td className="px-3 py-2 text-gray-400">{a.user_id}</td>
                    <td className="px-3 py-2 text-teal-300">{a.page_url}</td>
                    <td className="px-3 py-2 text-gray-500">
                      {new Date(a.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* === Most Visited Pages Card === */}
        <Card className="p-6 bg-card border-border">
          <h2 className="text-lg font-semibold text-white mb-4">Most Visited Pages</h2>

          {mostVisited.length === 0 ? (
            <p className="text-gray-400 text-sm">No page visit data.</p>
          ) : (
            <div className="space-y-6">
              {mostVisited.map((item, idx) => (
                <div key={idx}>
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-300">{item.page}</span>
                    <span className="text-gray-400">{item.percent} %</span>
                  </div>

                  <div className="h-3 bg-[#1f2735] rounded-lg overflow-hidden border border-[#2c394d]">
                    <div
                      className="h-full bg-gradient-to-r from-teal-400 to-cyan-400"
                      style={{ width: `${item.percent}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
