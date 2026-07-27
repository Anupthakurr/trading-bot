"""
Configuration loader for the QuantEngine backtesting framework.

Loads settings from config.yaml and merges with CLI argument overrides.
Provides a typed Settings dataclass for type-safe access throughout the framework.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ── Path Constants ───────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_CONFIG_PATH = os.path.join(_BACKEND_DIR, "config.yaml")


# ── Dataclasses ──────────────────────────────────────────────
@dataclass
class ExecutionConfig:
    """Trade execution simulation settings."""
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    slippage_model: str = "fixed"        # "fixed" or "random"
    max_position_pct: float = 1.0

@dataclass
class DataConfig:
    """Data fetching settings."""
    default_symbols: List[str] = field(default_factory=lambda: ["AAPL"])
    default_timeframe: str = "1D"
    default_start: str = "2022-01-01"
    default_end: str = "2024-12-31"
    cache_ttl_hours: int = 24
    provider: str = "yfinance"

@dataclass
class WalkForwardConfig:
    """Walk-forward analysis settings."""
    train_pct: float = 0.60
    validation_pct: float = 0.20
    test_pct: float = 0.20
    n_splits: int = 3

@dataclass
class RobustnessConfig:
    """Robustness testing settings."""
    monte_carlo_iterations: int = 1000
    confidence_levels: List[float] = field(default_factory=lambda: [0.05, 0.25, 0.50, 0.75, 0.95])
    sensitivity_variation_pct: float = 0.20

@dataclass
class OptimizationConfig:
    """Optimization settings."""
    method: str = "grid"
    random_iterations: int = 500
    rank_by: str = "sharpe_ratio"
    top_n: int = 10
    param_grids: Dict[str, Dict[str, list]] = field(default_factory=dict)

@dataclass
class ReportingConfig:
    """Report generation settings."""
    formats: List[str] = field(default_factory=lambda: ["html", "csv", "json"])
    embed_charts: bool = True
    chart_dpi: int = 150
    chart_style: str = "dark_background"

@dataclass
class Settings:
    """Master settings container for the entire framework."""
    # General
    initial_capital: float = 100000.0
    currency: str = "USD"
    log_level: str = "INFO"
    output_dir: str = "results"
    data_cache_dir: str = "data_cache"

    # Sub-configs
    data: DataConfig = field(default_factory=DataConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    walk_forward: WalkForwardConfig = field(default_factory=WalkForwardConfig)
    robustness: RobustnessConfig = field(default_factory=RobustnessConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)

    # Strategy parameter defaults (raw dicts from YAML)
    strategies: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ── Loader ───────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(
    config_path: Optional[str] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Settings:
    """
    Load settings from YAML config file, optionally merged with CLI overrides.

    Args:
        config_path: Path to YAML config file. Defaults to backend/config.yaml.
        cli_overrides: Dict of CLI argument overrides to merge on top of YAML.

    Returns:
        Fully populated Settings instance.
    """
    path = config_path or _DEFAULT_CONFIG_PATH

    # Load YAML
    raw: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", path)
    else:
        logger.warning("Config file not found at %s — using defaults", path)

    # Merge CLI overrides
    if cli_overrides:
        raw = _deep_merge(raw, cli_overrides)

    # Build Settings from raw dict
    general = raw.get("general", {})
    settings = Settings(
        initial_capital=general.get("initial_capital", 100000.0),
        currency=general.get("currency", "USD"),
        log_level=general.get("log_level", "INFO"),
        output_dir=general.get("output_dir", "results"),
        data_cache_dir=general.get("data_cache_dir", "data_cache"),
    )

    # Data config
    data_raw = raw.get("data", {})
    settings.data = DataConfig(
        default_symbols=data_raw.get("default_symbols", ["AAPL"]),
        default_timeframe=data_raw.get("default_timeframe", "1D"),
        default_start=data_raw.get("default_start", "2022-01-01"),
        default_end=data_raw.get("default_end", "2024-12-31"),
        cache_ttl_hours=data_raw.get("cache_ttl_hours", 24),
        provider=data_raw.get("provider", "yfinance"),
    )

    # Execution config
    exec_raw = raw.get("execution", {})
    settings.execution = ExecutionConfig(
        commission_pct=exec_raw.get("commission_pct", 0.001),
        slippage_pct=exec_raw.get("slippage_pct", 0.0005),
        slippage_model=exec_raw.get("slippage_model", "fixed"),
        max_position_pct=exec_raw.get("max_position_pct", 1.0),
    )

    # Optimization config
    opt_raw = raw.get("optimization", {})
    settings.optimization = OptimizationConfig(
        method=opt_raw.get("method", "grid"),
        random_iterations=opt_raw.get("random_iterations", 500),
        rank_by=opt_raw.get("rank_by", "sharpe_ratio"),
        top_n=opt_raw.get("top_n", 10),
        param_grids=opt_raw.get("param_grids", {}),
    )

    # Walk-forward config
    wf_raw = raw.get("walk_forward", {})
    settings.walk_forward = WalkForwardConfig(
        train_pct=wf_raw.get("train_pct", 0.60),
        validation_pct=wf_raw.get("validation_pct", 0.20),
        test_pct=wf_raw.get("test_pct", 0.20),
        n_splits=wf_raw.get("n_splits", 3),
    )

    # Robustness config
    rob_raw = raw.get("robustness", {})
    settings.robustness = RobustnessConfig(
        monte_carlo_iterations=rob_raw.get("monte_carlo_iterations", 1000),
        confidence_levels=rob_raw.get("confidence_levels", [0.05, 0.25, 0.50, 0.75, 0.95]),
        sensitivity_variation_pct=rob_raw.get("sensitivity_variation_pct", 0.20),
    )

    # Reporting config
    rpt_raw = raw.get("reporting", {})
    settings.reporting = ReportingConfig(
        formats=rpt_raw.get("formats", ["html", "csv", "json"]),
        embed_charts=rpt_raw.get("embed_charts", True),
        chart_dpi=rpt_raw.get("chart_dpi", 150),
        chart_style=rpt_raw.get("chart_style", "dark_background"),
    )

    # Strategy defaults
    settings.strategies = raw.get("strategies", {})

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    return settings
