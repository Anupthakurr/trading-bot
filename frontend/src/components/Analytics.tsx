import React from 'react';
import { 
  BarChart3, 
  TrendingDown, 
  Activity, 
  PieChart, 
  Percent, 
  Target, 
  ShieldAlert, 
  Zap,
  TrendingUp,
  LineChart
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart as RePieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { MetricsCard } from './MetricsCard';

interface AnalyticsProps {
  results: any;
}

export const Analytics: React.FC<AnalyticsProps> = ({ results }) => {
  if (!results || !results.metrics) {
    return (
      <div className="glass-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '500px' }}>
        <BarChart3 size={64} style={{ color: 'var(--text-secondary)', marginBottom: '16px', opacity: 0.5 }} />
        <h3 style={{ color: 'var(--text-secondary)' }}>No Analytics Available</h3>
        <p>Run a backtest first to view advanced quantitative analytics.</p>
      </div>
    );
  }

  const { metrics, chart_data } = results;

  // Format drawdown data for the area chart
  const drawdownData = chart_data.map((point: any) => ({
    date: new Date(point.Date).toLocaleDateString(),
    drawdown: point.Drawdown || 0,
  }));

  // Format trade distribution data for pie chart
  const tradeData = [
    { name: 'Winning Days', value: metrics.winning_trades, color: 'var(--success)' },
    { name: 'Losing Days', value: metrics.losing_trades, color: 'var(--danger)' },
  ];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'rgba(15, 23, 42, 0.9)',
          border: '1px solid var(--glass-border)',
          padding: '12px',
          borderRadius: '8px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          color: 'var(--text-primary)'
        }}>
          <p style={{ margin: '0 0 6px 0', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>{label}</p>
          <p style={{ margin: 0, fontWeight: 600, color: 'var(--danger)' }}>
            Drawdown: {payload[0].value.toFixed(2)}%
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {results.is_live && (
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 14px',
          borderRadius: '20px',
          background: 'rgba(16, 185, 129, 0.12)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--success)',
          alignSelf: 'flex-start'
        }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 8px var(--success)' }}></span>
          Live Trading Mode
        </div>
      )}

      {/* KPI Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '16px'
      }}>
        <MetricsCard 
          title="Win Rate" 
          value={metrics.win_rate_pct} 
          suffix="%" 
          isPositive={metrics.win_rate_pct > 50}
          icon={<Target size={20} />}
        />
        <MetricsCard 
          title="Sharpe Ratio" 
          value={metrics.sharpe_ratio} 
          isPositive={metrics.sharpe_ratio > 1}
          icon={<Activity size={20} />}
        />
        <MetricsCard 
          title="Sortino Ratio" 
          value={metrics.sortino_ratio} 
          isPositive={metrics.sortino_ratio > 1.5}
          icon={<Zap size={20} />}
        />
        <MetricsCard 
          title="Calmar Ratio" 
          value={metrics.calmar_ratio} 
          isPositive={metrics.calmar_ratio > 1}
          icon={<ShieldAlert size={20} />}
        />
        <MetricsCard 
          title="Alpha" 
          value={metrics.alpha_pct} 
          suffix="%"
          isPositive={metrics.alpha_pct > 0}
          icon={<TrendingUp size={20} />}
        />
        <MetricsCard 
          title="Beta" 
          value={metrics.beta} 
          isPositive={metrics.beta < 1}
          icon={<LineChart size={20} />}
        />
      </div>

      {/* Charts Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '2fr 1fr',
        gap: '24px',
        alignItems: 'start'
      }}>
        
        {/* Drawdown Curve */}
        <div className="glass-panel" style={{ height: '400px', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingDown size={18} style={{ color: 'var(--danger)' }} />
            Underwater Drawdown Curve
          </h3>
          <div style={{ flex: 1, minHeight: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={drawdownData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--danger)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--danger)" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis 
                  dataKey="date" 
                  stroke="var(--text-secondary)" 
                  fontSize={12} 
                  tickMargin={10}
                  tickFormatter={(val) => {
                    const d = new Date(val);
                    return `${d.getMonth()+1}/${d.getDate()}`;
                  }}
                  minTickGap={40}
                />
                <YAxis 
                  stroke="var(--text-secondary)" 
                  fontSize={12} 
                  tickFormatter={(val) => `${val}%`}
                  domain={['auto', 0]}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area 
                  type="monotone" 
                  dataKey="drawdown" 
                  stroke="var(--danger)" 
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorDrawdown)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Trade Distribution */}
        <div className="glass-panel" style={{ height: '400px', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <PieChart size={18} style={{ color: 'var(--accent-color)' }} />
            Trade Distribution
          </h3>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {metrics.winning_trades === 0 && metrics.losing_trades === 0 ? (
              <p style={{ color: 'var(--text-secondary)' }}>No trade data available</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <RePieChart>
                  <Pie
                    data={tradeData}
                    cx="50%"
                    cy="45%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={5}
                    dataKey="value"
                    stroke="none"
                  >
                    {tradeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      background: 'rgba(15, 23, 42, 0.9)', 
                      border: '1px solid var(--glass-border)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)'
                    }} 
                    itemStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Legend 
                    verticalAlign="bottom" 
                    height={36} 
                    iconType="circle"
                    formatter={(value, entry: any) => <span style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>{value}</span>}
                  />
                </RePieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
