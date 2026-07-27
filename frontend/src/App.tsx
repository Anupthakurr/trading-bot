import { useState } from 'react';
import axios from 'axios';
import { Activity, DollarSign, TrendingUp, AlertTriangle } from 'lucide-react';
import { ControlPanel } from './components/ControlPanel';
import { MetricsCard } from './components/MetricsCard';
import { EquityChart } from './components/EquityChart';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<any>(null);
  const [strategyLabel, setStrategyLabel] = useState('');

  const STRATEGY_NAMES: Record<number, string> = {
    1: 'V1 — SMA Crossover',
    2: 'V2 — SMA + RSI Filter',
    3: 'V3 — ATR Risk Management',
  };

  const handleRunBacktest = async (params: any) => {
    setIsLoading(true);
    setError(null);
    try {
      // Connect to the Python FastAPI backend
      const response = await axios.post('http://localhost:8000/api/backtest', params);
      setResults(response.data);
      setStrategyLabel(STRATEGY_NAMES[params.strategy_version] || 'Unknown');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'An error occurred during backtesting');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header style={{ marginBottom: '16px' }}>
        <h1>QuantEngine</h1>
        <p>Algorithmic Trading Backtest Simulator</p>
      </header>

      {error && (
        <div className="glass-panel text-danger" style={{ border: '1px solid var(--danger)' }}>
          <p style={{ color: 'var(--danger)', fontWeight: 500 }}>Error: {error}</p>
        </div>
      )}

      <div className="dashboard-grid">
        <aside>
          <ControlPanel onRunBacktest={handleRunBacktest} isLoading={isLoading} />
        </aside>
        
        <main>
          {results ? (
            <>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '20px',
                background: 'rgba(59, 130, 246, 0.12)',
                border: '1px solid rgba(59, 130, 246, 0.25)',
                marginBottom: '16px',
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'var(--accent-color)',
              }}>
                <Activity size={14} />
                {strategyLabel}
              </div>
              <div className="metrics-grid">
                <MetricsCard 
                  title="Total Return" 
                  value={results.metrics.total_return_pct} 
                  suffix="%" 
                  isPositive={results.metrics.total_return_pct >= 0}
                  icon={<TrendingUp size={20} />}
                />
                <MetricsCard 
                  title="Buy & Hold Return" 
                  value={results.metrics.buy_and_hold_return_pct} 
                  suffix="%" 
                  isPositive={results.metrics.buy_and_hold_return_pct >= 0}
                />
                <MetricsCard 
                  title="Sharpe Ratio" 
                  value={results.metrics.sharpe_ratio} 
                  isPositive={results.metrics.sharpe_ratio > 1}
                  icon={<Activity size={20} />}
                />
                <MetricsCard 
                  title="Max Drawdown" 
                  value={results.metrics.max_drawdown_pct} 
                  suffix="%" 
                  isPositive={false} // Drawdown is inherently negative
                  icon={<AlertTriangle size={20} />}
                />
              </div>
              <EquityChart data={results.chart_data} />
            </>
          ) : (
            <div className="glass-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '500px' }}>
              <DollarSign size={64} style={{ color: 'var(--text-secondary)', marginBottom: '16px', opacity: 0.5 }} />
              <h3 style={{ color: 'var(--text-secondary)' }}>Ready to run simulation</h3>
              <p>Configure parameters on the left and click "Run Backtest"</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
