import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

interface EquityChartProps {
  data: any[];
}

export const EquityChart: React.FC<EquityChartProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="glass-panel" style={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p>No data to display. Run a backtest first.</p>
      </div>
    );
  }

  // Format tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-panel" style={{ padding: '12px', minWidth: '200px' }}>
          <p style={{ margin: '0 0 8px', fontWeight: 600 }}>{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ color: entry.color }}>{entry.name}:</span>
              <span style={{ fontWeight: 600 }}>
                {entry.name === 'Equity' ? '$' : ''}
                {Number(entry.value).toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-panel" style={{ height: '500px', width: '100%' }}>
      <h3 style={{ marginBottom: '16px' }}>Performance Chart</h3>
      <ResponsiveContainer width="100%" height="90%">
        <ComposedChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
          <XAxis 
            dataKey="Date" 
            stroke="var(--text-secondary)" 
            tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} 
            tickFormatter={(tick) => tick.substring(0, 7)} // Just show YYYY-MM
            minTickGap={30}
          />
          <YAxis 
            yAxisId="left"
            stroke="var(--text-secondary)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
            tickFormatter={(value) => `$${(value / 1000)}k`}
          />
          <YAxis 
            yAxisId="right" 
            orientation="right" 
            stroke="var(--text-secondary)"
            tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
            domain={['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }}/>
          <Line 
            yAxisId="left"
            type="monotone" 
            dataKey="Equity" 
            name="Strategy Equity" 
            stroke="var(--accent-color)" 
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 8, fill: 'var(--accent-hover)', stroke: '#fff', strokeWidth: 2 }}
          />
          <Line 
            yAxisId="right"
            type="monotone" 
            dataKey="Close" 
            name="Asset Price" 
            stroke="var(--text-secondary)" 
            strokeWidth={1}
            dot={false}
            opacity={0.5}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};
