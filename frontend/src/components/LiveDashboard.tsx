import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Play,
  Square,
  Activity,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Zap,
  Clock,
  AlertTriangle,
  Terminal,
  RefreshCw,
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface EngineInfo {
  is_running: boolean;
  interval_seconds: number;
  strategy: string;
  risk_per_trade: number;
}

interface Order {
  id: number;
  ticker: string;
  side: string;
  order_type: string;
  quantity: number;
  price: number;
  status: string;
  created_at: string;
  filled_at: string | null;
}

interface Position {
  id: number;
  ticker: string;
  quantity: number;
  entry_price: number;
  current_price: number | null;
  status: string;
  opened_at: string;
  updated_at: string;
}

interface LogEntry {
  id: number;
  level: string;
  message: string;
  timestamp: string;
}

const STRATEGY_OPTIONS = [
  { value: 1, label: 'V1 — SMA Crossover' },
  { value: 2, label: 'V2 — SMA + RSI Filter' },
  { value: 3, label: 'V3 — ATR Risk Mgmt' },
];

export const LiveDashboard: React.FC = () => {
  // Engine control state
  const [ticker, setTicker] = useState('AAPL');
  const [strategyVersion, setStrategyVersion] = useState(1);
  const [intervalSeconds, setIntervalSeconds] = useState('60');
  const [riskPerTrade, setRiskPerTrade] = useState('1.0');
  const [broker, setBroker] = useState('mock');
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Live data state
  const [activeEngines, setActiveEngines] = useState<Record<string, EngineInfo>>({});
  const [balance, setBalance] = useState<number>(0);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  // Polling
  const [isPolling, setIsPolling] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const totalActive = Object.keys(activeEngines).length;
  const isRunning = totalActive > 0;

  // Fetch all dashboard data
  const fetchDashboardData = useCallback(async () => {
    try {
      const [statusRes, balanceRes, positionsRes, ordersRes, logsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/live/status`),
        axios.get(`${API_BASE}/api/live/balance`),
        axios.get(`${API_BASE}/api/live/positions`),
        axios.get(`${API_BASE}/api/live/orders`),
        axios.get(`${API_BASE}/api/live/logs`),
      ]);
      setActiveEngines(statusRes.data.active_engines || {});
      setBalance(balanceRes.data.balance || 0);
      setPositions(positionsRes.data.positions || []);
      setOrders(ordersRes.data.orders || []);
      setLogs(logsRes.data.logs || []);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
    }
  }, []);

  // Start polling when engines are active, stop when idle
  useEffect(() => {
    // Always fetch once on mount
    fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    if (isPolling) {
      pollIntervalRef.current = setInterval(fetchDashboardData, 3000);
    }
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [isPolling, fetchDashboardData]);

  // Auto-start polling when engine starts, stop after some time when idle
  useEffect(() => {
    if (isRunning) {
      setIsPolling(true);
    }
  }, [isRunning]);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = 0; // logs are newest-first
    }
  }, [logs]);

  const handleStart = async () => {
    setIsStarting(true);
    setActionMessage(null);
    try {
      const response = await axios.post(`${API_BASE}/api/live/start`, {
        ticker: ticker.toUpperCase(),
        strategy_version: strategyVersion,
        interval_seconds: parseInt(intervalSeconds),
        risk_per_trade: parseFloat(riskPerTrade) / 100,
        broker: broker,
      });
      setActionMessage({ type: 'success', text: response.data.message });
      setIsPolling(true);
      // Fetch data after a short delay to let engine initialize
      setTimeout(fetchDashboardData, 1000);
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || 'Failed to start engine',
      });
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async (tickerToStop: string) => {
    setIsStopping(true);
    setActionMessage(null);
    try {
      const response = await axios.post(`${API_BASE}/api/live/stop?ticker=${tickerToStop}`);
      setActionMessage({ type: 'success', text: response.data.message });
      setTimeout(fetchDashboardData, 500);
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err.response?.data?.detail || err.message || 'Failed to stop engine',
      });
    } finally {
      setIsStopping(false);
    }
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    marginBottom: '6px',
    fontSize: '0.8rem',
    fontWeight: 500,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  const formatTime = (ts: string | null) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  };

  const getLogLevelClass = (level: string) => {
    switch (level.toUpperCase()) {
      case 'ERROR': return 'log-error';
      case 'WARNING': return 'log-warning';
      default: return 'log-info';
    }
  };

  return (
    <div className="live-dashboard">
      {/* Status Banner */}
      <div className={`status-banner ${isRunning ? 'status-active' : 'status-idle'}`}>
        <div className="status-banner-left">
          <div className={`status-dot ${isRunning ? 'dot-active' : 'dot-idle'}`} />
          <span className="status-label">
            {isRunning ? `Live — ${totalActive} engine${totalActive > 1 ? 's' : ''} active` : 'Engines Idle'}
          </span>
        </div>
        <div className="status-banner-right">
          <button
            className="btn-icon"
            onClick={() => { fetchDashboardData(); }}
            title="Refresh data"
          >
            <RefreshCw size={14} />
          </button>
          {isRunning && (
            <div className="status-engines-list">
              {Object.entries(activeEngines).map(([t, info]) => (
                <span key={t} className="engine-tag">
                  <Zap size={12} />
                  {t} · {info.strategy}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Action Message */}
      {actionMessage && (
        <div className={`action-message ${actionMessage.type === 'error' ? 'msg-error' : 'msg-success'}`}>
          {actionMessage.type === 'error' ? <AlertTriangle size={14} /> : <Activity size={14} />}
          {actionMessage.text}
        </div>
      )}

      <div className="live-grid">
        {/* Left Column: Controls */}
        <div className="live-sidebar">
          {/* Engine Controls */}
          <div className="glass-panel">
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={18} style={{ color: 'var(--accent-color)' }} />
              Engine Controls
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={labelStyle}>Broker</label>
                <select 
                  value={broker} 
                  onChange={(e) => setBroker(e.target.value)}
                  disabled={isStarting}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.5)', color: 'white', border: '1px solid var(--glass-border)' }}
                >
                  <option value="mock">Mock Paper Trading</option>
                  <option value="angelone">Angel One (Live)</option>
                </select>
              </div>

              <div>
                <label style={labelStyle}>Ticker</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  placeholder={broker === 'angelone' ? "e.g. SBIN, RELIANCE" : "e.g. AAPL, MSFT"}
                  disabled={isStarting}
                />
              </div>

              <div>
                <label style={labelStyle}>Strategy</label>
                <div className="strategy-selector">
                  {STRATEGY_OPTIONS.map((s) => (
                    <button
                      key={s.value}
                      type="button"
                      className={`strategy-option ${strategyVersion === s.value ? 'active' : ''}`}
                      onClick={() => setStrategyVersion(s.value)}
                      disabled={isStarting}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={labelStyle}>Interval (sec)</label>
                  <input
                    type="number"
                    min="10"
                    value={intervalSeconds}
                    onChange={(e) => setIntervalSeconds(e.target.value)}
                    disabled={isStarting}
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
                    disabled={isStarting}
                  />
                </div>
              </div>

              <button
                className="btn-primary btn-start"
                onClick={handleStart}
                disabled={isStarting || !ticker.trim()}
              >
                {isStarting ? (
                  <span className="animate-pulse">Connecting...</span>
                ) : (
                  <>
                    <Play size={16} />
                    Start Live Engine
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Account Card */}
          <div className="glass-panel account-card">
            <div className="account-header">
              <DollarSign size={20} style={{ color: 'var(--success)' }} />
              <span>Account Balance</span>
            </div>
            <div className="account-balance">
              ${balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="account-label">Mock Paper Trading</div>
          </div>

          {/* Active Engines */}
          {isRunning && (
            <div className="glass-panel">
              <h4 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Activity size={16} style={{ color: 'var(--success)' }} />
                Active Engines
              </h4>
              <div className="active-engines-list">
                {Object.entries(activeEngines).map(([t, info]) => (
                  <div key={t} className="active-engine-item">
                    <div className="engine-info">
                      <span className="engine-ticker">{t}</span>
                      <span className="engine-meta">{info.strategy} · {info.interval_seconds}s</span>
                    </div>
                    <button
                      className="btn-stop"
                      onClick={() => handleStop(t)}
                      disabled={isStopping}
                      title="Stop engine"
                    >
                      <Square size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Market Information */}
          <div className="glass-panel" style={{ marginTop: '16px' }}>
            <h4 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={16} style={{ color: 'var(--accent-color)' }} />
              Market Information
            </h4>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <p style={{ marginBottom: '8px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Indian Market (NSE/BSE)</strong><br />
                09:15 AM - 03:30 PM (IST)
              </p>
              <p style={{ marginBottom: '8px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>US Market (NYSE/NASDAQ)</strong><br />
                07:00 PM - 01:30 AM (IST) <br/>
                <span style={{ fontSize: '0.75rem', opacity: 0.7 }}>(08:00 PM - 02:30 AM in Winter)</span>
              </p>
              <hr style={{ border: 'none', borderTop: '1px solid var(--glass-border)', margin: '12px 0' }} />
              <p>
                <strong style={{ color: 'var(--text-primary)' }}>Trading Bot</strong><br />
                The bot evaluates your strategy using live data at the specified interval. Use <em>Mock Paper Trading</em> to test strategies risk-free.
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: Data Panels */}
        <div className="live-main">
          {/* Positions Table */}
          <div className="glass-panel">
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} style={{ color: 'var(--accent-color)' }} />
              Positions
              <span className="badge">{positions.length}</span>
            </h3>
            {positions.length > 0 ? (
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Qty</th>
                      <th>Entry</th>
                      <th>Current</th>
                      <th>P&L</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => {
                      const pnl = p.current_price
                        ? (p.current_price - p.entry_price) * p.quantity
                        : 0;
                      const pnlPct = p.entry_price > 0 && p.current_price
                        ? ((p.current_price - p.entry_price) / p.entry_price * 100)
                        : 0;
                      return (
                        <tr key={p.id}>
                          <td className="cell-ticker">{p.ticker}</td>
                          <td>{p.quantity}</td>
                          <td>${p.entry_price.toFixed(2)}</td>
                          <td>{p.current_price ? `$${p.current_price.toFixed(2)}` : '—'}</td>
                          <td className={pnl >= 0 ? 'text-success' : 'text-danger'}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              {pnl >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                              ${pnl.toFixed(2)} ({pnlPct.toFixed(1)}%)
                            </span>
                          </td>
                          <td>
                            <span className={`status-chip ${p.status === 'OPEN' ? 'chip-open' : 'chip-closed'}`}>
                              {p.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <TrendingUp size={32} style={{ opacity: 0.3 }} />
                <p>No positions yet. Start an engine to begin trading.</p>
              </div>
            )}
          </div>

          {/* Orders Table */}
          <div className="glass-panel">
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={18} style={{ color: 'var(--accent-color)' }} />
              Order History
              <span className="badge">{orders.length}</span>
            </h3>
            {orders.length > 0 ? (
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Ticker</th>
                      <th>Side</th>
                      <th>Type</th>
                      <th>Qty</th>
                      <th>Price</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((o) => (
                      <tr key={o.id}>
                        <td className="cell-time">{formatTime(o.created_at)}</td>
                        <td className="cell-ticker">{o.ticker}</td>
                        <td>
                          <span className={`side-chip ${o.side === 'BUY' ? 'side-buy' : 'side-sell'}`}>
                            {o.side}
                          </span>
                        </td>
                        <td>{o.order_type}</td>
                        <td>{o.quantity}</td>
                        <td>${o.price?.toFixed(2) ?? '—'}</td>
                        <td>
                          <span className={`status-chip ${o.status === 'FILLED' ? 'chip-filled' : o.status === 'REJECTED' ? 'chip-rejected' : 'chip-pending'}`}>
                            {o.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <Clock size={32} style={{ opacity: 0.3 }} />
                <p>No orders yet.</p>
              </div>
            )}
          </div>

          {/* Activity Log */}
          <div className="glass-panel">
            <h3 style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Terminal size={18} style={{ color: 'var(--accent-color)' }} />
              Activity Log
              <span className="badge">{logs.length}</span>
            </h3>
            <div className="log-container" ref={logContainerRef}>
              {logs.length > 0 ? (
                logs.map((log) => (
                  <div key={log.id} className={`log-entry ${getLogLevelClass(log.level)}`}>
                    <span className="log-time">{formatTime(log.timestamp)}</span>
                    <span className={`log-level level-${log.level.toLowerCase()}`}>{log.level}</span>
                    <span className="log-msg">{log.message}</span>
                  </div>
                ))
              ) : (
                <div className="empty-state" style={{ minHeight: '80px' }}>
                  <Terminal size={24} style={{ opacity: 0.3 }} />
                  <p>No activity yet.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
