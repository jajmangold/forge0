"""Hyperparameter optimization with Optuna."""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

optuna: Any = None

try:
    import optuna as _optuna  # pyright: ignore[reportMissingImports]
    optuna = _optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False


class HyperOptimizer:
    """Optimize hyperparameters with Optuna."""
    
    def __init__(self, study_name: str = "forge0", storage: str | None = None):
        self.study_name = study_name
        self.storage = storage or f"sqlite:///{os.path.expanduser('~')}/forge0_optuna.db"
        self.study = None
    
    def create_study(self, direction: str = "maximize"):
        """Create or load a study."""
        if not OPTUNA_AVAILABLE:
            return None
        
        self.study = optuna.create_study(
            study_name=self.study_name,
            direction=direction,
            storage=self.storage,
            load_if_exists=True,
        )
        return self.study
    
    def optimize(
        self, 
        objective: Callable, 
        n_trials: int = 100,
        timeout: int | None = None,
    ):
        """Run optimization."""
        if not self.study:
            self.create_study()
        
        if self.study:
            self.study.optimize(
                objective, 
                n_trials=n_trials,
                timeout=timeout,
            )
    
    @property
    def best_params(self) -> dict[str, Any]:
        """Get best parameters."""
        if self.study:
            return self.study.best_params
        return {}
    
    @property
    def best_value(self) -> float | None:
        """Get best value."""
        if self.study:
            return self.study.best_value
        return None
    
    def suggest_params(self, trial, param_config: dict[str, Any]):
        """Suggest parameters from config."""
        params = {}
        
        for name, config in param_config.items():
            param_type = config.get("type", "float")
            
            if param_type == "float":
                params[name] = trial.suggest_float(
                    name,
                    config["low"],
                    config["high"],
                    step=config.get("step"),
                    log=config.get("log", False),
                )
            elif param_type == "int":
                params[name] = trial.suggest_int(
                    name,
                    config["low"],
                    config["high"],
                    step=config.get("step"),
                    log=config.get("log", False),
                )
            elif param_type == "categorical":
                params[name] = trial.suggest_categorical(name, config["choices"])
        
        return params


# Global optimizer instance
optimizer = HyperOptimizer()


# Example: Optimize agent parameters
AGENT_PARAM_CONFIG = {
    "temperature": {"type": "float", "low": 0.0, "high": 1.0, "step": 0.1},
    "max_tokens": {"type": "int", "low": 1000, "high": 10000, "step": 1000},
    "model": {"type": "categorical", "choices": ["mimo-v2.5", "mimo-v2.5-pro"]},
}


def create_agent_objective(agent_func: Callable):
    """Create an objective function for agent optimization."""
    def objective(trial):
        params = optimizer.suggest_params(trial, AGENT_PARAM_CONFIG)
        
        result = agent_func(**params)
        
        return result.get("score", 0.0)
    
    return objective
