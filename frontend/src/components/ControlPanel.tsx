import React, { useState } from 'react';
import { Play, Info } from 'lucide-react';

interface ControlPanelProps {
  onRunBacktest: (params: any) => void;
  isLoading: boolean;
}

const STRATEGY_INFO: Record<number, { name: string; description: string }> = {
  1: {
    name: 'V1 — SMA Crossover',
    description: 'Classic moving average crossover. Goes long when the short MA crosses above the long MA.',
  },
  2: {
    name: 'V2 — SMA + RSI Filter',
    description: 'Adds an RSI filter to V1. Avoids buying when the asset is overbought (RSI > 70).',
  },
  3: {
    name: 'V3 — ATR Risk Management',
    description: 'Builds on V2 with ATR-based stop losses and dynamic position sizing for proper risk management.',
  },
};

export const ControlPanel: React.FC<ControlPanelProps> = ({ onRunBacktest, isLoading }) => {
  const [ticker, setTicker] = useState('AAPL');
  
  // Default to last 2 years
  const today = new Date();
  const twoYearsAgo = new Date();
  twoYearsAgo.setFullYear(today.getFullYear() - 2);
  
  const [startDate, setStartDate] = useState(twoYearsAgo.toISOString().split('T')[0]);
  const [endDate, setEndDate] = useState(today.toISOString().split('T')[0]);
  const [shortWindow, setShortWindow] = useState('20');
  const [longWindow, setLongWindow] = useState('50');
  const [strategyVersion, setStrategyVersion] = useState(1);

  // V2 / V3 parameters
  const [rsiPeriod, setRsiPeriod] = useState('14');

  // V3 parameters
  const [atrMultiplier, setAtrMultiplier] = useState('2.0');
  const [riskPerTrade, setRiskPerTrade] = useState('1.0'); // shown as %, sent as decimal

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRunBacktest({
      ticker: ticker.toUpperCase(),
      start_date: startDate,
      end_date: endDate,
      short_window: parseInt(shortWindow),
      long_window: parseInt(longWindow),
      initial_capital: 100000,
      strategy_version: strategyVersion,
      rsi_period: parseInt(rsiPeriod),
      atr_multiplier: parseFloat(atrMultiplier),
      risk_per_trade: parseFloat(riskPerTrade) / 100, // convert % to decimal
    });
  };

  const labelStyle: React.CSSProperties = { display: 'block', marginBottom: '8px', fontSize: '0.875rem' };
  const sectionTitle: React.CSSProperties = {
    fontSize: '0.75rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: 'var(--text-secondary)',
    marginBottom: '12px',
    marginTop: '8px',
  };

  return (
    <div className="glass-panel">
      <h2 style={{ marginBottom: '24px' }}>Strategy Parameters</h2>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        
        {/* Strategy Version Selector */}
        <div>
          <label style={labelStyle}>Strategy Version</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {[1, 2, 3].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setStrategyVersion(v)}
                style={{
                  padding: '10px 14px',
                  borderRadius: '10px',
                  border: strategyVersion === v
                    ? '2px solid var(--accent-color)'
                    : '1px solid var(--glass-border)',
                  background: strategyVersion === v
                    ? 'rgba(59, 130, 246, 0.15)'
                    : 'rgba(15, 23, 42, 0.4)',
                  color: strategyVersion === v ? 'var(--accent-color)' : 'var(--text-secondary)',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  fontWeight: strategyVersion === v ? 600 : 400,
                  fontSize: '0.85rem',
                }}
              >
                {STRATEGY_INFO[v].name}
              </button>
            ))}
          </div>
          {/* Strategy description */}
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
            marginTop: '10px',
            padding: '10px 12px',
            borderRadius: '8px',
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.15)',
          }}>
            <Info size={16} style={{ color: 'var(--accent-color)', marginTop: '2px', flexShrink: 0 }} />
            <p style={{ margin: 0, fontSize: '0.8rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
              {STRATEGY_INFO[strategyVersion].description}
            </p>
          </div>
        </div>

        {/* Divider */}
        <hr style={{ border: 'none', borderTop: '1px solid var(--glass-border)', margin: '4px 0' }} />

        {/* Asset & Date */}
        <div style={sectionTitle}>Market Data</div>

        <div>
          <label style={labelStyle}>Asset Ticker</label>
          <input 
            type="text" 
            value={ticker} 
            onChange={(e) => setTicker(e.target.value)} 
            placeholder="e.g. AAPL, MSFT, BTC-USD"
            required
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div>
            <label style={labelStyle}>Start Date</label>
            <input 
              type="date" 
              value={startDate} 
              onChange={(e) => setStartDate(e.target.value)} 
              required
            />
          </div>
          <div>
            <label style={labelStyle}>End Date</label>
            <input 
              type="date" 
              value={endDate} 
              onChange={(e) => setEndDate(e.target.value)} 
              required
            />
          </div>
        </div>

        {/* Divider */}
        <hr style={{ border: 'none', borderTop: '1px solid var(--glass-border)', margin: '4px 0' }} />

        {/* Moving Average Params (all versions) */}
        <div style={sectionTitle}>Moving Averages</div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div>
            <label style={labelStyle}>Short MA Window</label>
            <input 
              type="number" 
              min="1"
              value={shortWindow} 
              onChange={(e) => setShortWindow(e.target.value)} 
              required
            />
          </div>
          <div>
            <label style={labelStyle}>Long MA Window</label>
            <input 
              type="number" 
              min="2"
              value={longWindow} 
              onChange={(e) => setLongWindow(e.target.value)} 
              required
            />
          </div>
        </div>

        {/* V2+ RSI Params */}
        {strategyVersion >= 2 && (
          <>
            <hr style={{ border: 'none', borderTop: '1px solid var(--glass-border)', margin: '4px 0' }} />
            <div style={sectionTitle}>RSI Filter</div>
            <div>
              <label style={labelStyle}>RSI Period</label>
              <input 
                type="number" 
                min="2"
                value={rsiPeriod} 
                onChange={(e) => setRsiPeriod(e.target.value)} 
                required
              />
            </div>
          </>
        )}

        {/* V3 Risk Management Params */}
        {strategyVersion === 3 && (
          <>
            <hr style={{ border: 'none', borderTop: '1px solid var(--glass-border)', margin: '4px 0' }} />
            <div style={sectionTitle}>Risk Management</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <label style={labelStyle}>ATR Multiplier</label>
                <input 
                  type="number" 
                  min="0.5"
                  step="0.1"
                  value={atrMultiplier} 
                  onChange={(e) => setAtrMultiplier(e.target.value)} 
                  required
                />
              </div>
              <div>
                <label style={labelStyle}>Risk / Trade (%)</label>
                <input 
                  type="number" 
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={riskPerTrade} 
                  onChange={(e) => setRiskPerTrade(e.target.value)} 
                  required
                />
              </div>
            </div>
          </>
        )}

        <button 
          type="submit" 
          className="btn-primary" 
          disabled={isLoading}
          style={{ marginTop: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
        >
          {isLoading ? (
            <span className="animate-pulse">Running Simulation...</span>
          ) : (
            <>
              <Play size={18} />
              Run Backtest
            </>
          )}
        </button>

      </form>
    </div>
  );
};
