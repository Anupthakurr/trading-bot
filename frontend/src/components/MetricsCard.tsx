import React from 'react';

interface MetricsCardProps {
  title: string;
  value: string | number;
  suffix?: string;
  isPositive?: boolean | null;
  icon?: React.ReactNode;
}

export const MetricsCard: React.FC<MetricsCardProps> = ({ title, value, suffix = '', isPositive = null, icon }) => {
  let valueClass = 'text-primary';
  if (isPositive === true) valueClass = 'text-success';
  if (isPositive === false) valueClass = 'text-danger';

  return (
    <div className="glass-panel" style={{ padding: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <p style={{ margin: 0, fontSize: '0.875rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </p>
        {icon && <span style={{ color: 'var(--text-secondary)' }}>{icon}</span>}
      </div>
      <h3 className={valueClass} style={{ fontSize: '1.5rem', margin: 0 }}>
        {value}{suffix}
      </h3>
    </div>
  );
};
