"""ML model training and evaluation on MOEX data."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from ..utils.logger import get_logger

log = get_logger("ml.model_trainer")


# ---------------------------------------------------------------------------
# LSTM definition
# ---------------------------------------------------------------------------

class _LSTMClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64,
                 num_layers: int = 2, num_classes: int = 3,
                 dropout: float = 0.3) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout,
        )
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


# ---------------------------------------------------------------------------
# ModelTrainer
# ---------------------------------------------------------------------------

class ModelTrainer:
    """Trains and evaluates ML models on MOEX data."""

    def __init__(self, model_dir: str = "hedge_fund/ml/models") -> None:
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # XGBoost
    # ------------------------------------------------------------------

    def train_xgboost(
        self,
        X_train: np.ndarray | pd.DataFrame,
        y_train: np.ndarray | pd.Series,
        X_val: np.ndarray | pd.DataFrame,
        y_val: np.ndarray | pd.Series,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Train XGBoost classifier. Returns (model, metrics)."""
        import xgboost as xgb

        y_tr = np.asarray(y_train)
        classes, counts = np.unique(y_tr, return_counts=True)
        max_count = counts.max()
        weights = {int(c): max_count / cnt for c, cnt in zip(classes, counts)}
        sample_weight = np.array([weights[int(v)] for v in y_tr])

        default_params: dict[str, Any] = {
            "max_depth": 6,
            "learning_rate": 0.05,
            "n_estimators": 500,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "multi:softmax",
            "num_class": len(classes),
            "eval_metric": "mlogloss",
            "use_label_encoder": False,
            "verbosity": 0,
            "n_jobs": -1,
        }
        if params:
            default_params.update(params)

        model = xgb.XGBClassifier(**default_params)
        model.fit(
            X_train, y_train,
            sample_weight=sample_weight,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        metrics = self.evaluate(model, X_val, y_val)
        log.info("XGBoost trained — val acc={:.4f} f1={:.4f}",
                 metrics["accuracy"], metrics["f1_weighted"])
        return model, metrics

    # ------------------------------------------------------------------
    # LightGBM
    # ------------------------------------------------------------------

    def train_lightgbm(
        self,
        X_train: np.ndarray | pd.DataFrame,
        y_train: np.ndarray | pd.Series,
        X_val: np.ndarray | pd.DataFrame,
        y_val: np.ndarray | pd.Series,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Train LightGBM classifier. Returns (model, metrics)."""
        import lightgbm as lgb

        y_tr = np.asarray(y_train)
        classes = np.unique(y_tr)

        default_params: dict[str, Any] = {
            "max_depth": 6,
            "learning_rate": 0.05,
            "n_estimators": 500,
            "min_child_samples": 20,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "multiclass",
            "num_class": len(classes),
            "metric": "multi_logloss",
            "class_weight": "balanced",
            "verbosity": -1,
            "n_jobs": -1,
        }
        if params:
            default_params.update(params)

        model = lgb.LGBMClassifier(**default_params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
        )
        metrics = self.evaluate(model, X_val, y_val)
        log.info("LightGBM trained — val acc={:.4f} f1={:.4f}",
                 metrics["accuracy"], metrics["f1_weighted"])
        return model, metrics

    # ------------------------------------------------------------------
    # LSTM (PyTorch)
    # ------------------------------------------------------------------

    def train_lstm(
        self,
        X_train: np.ndarray | pd.DataFrame,
        y_train: np.ndarray | pd.Series,
        X_val: np.ndarray | pd.DataFrame,
        y_val: np.ndarray | pd.Series,
        sequence_length: int = 20,
        epochs: int = 50,
    ) -> tuple[nn.Module, dict[str, Any]]:
        """Train LSTM for sequence prediction using PyTorch."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        X_tr = np.asarray(X_train, dtype=np.float32)
        y_tr = np.asarray(y_train, dtype=np.int64)
        X_v = np.asarray(X_val, dtype=np.float32)
        y_v = np.asarray(y_val, dtype=np.int64)

        # Remap labels to 0-based contiguous
        unique_labels = np.unique(np.concatenate([y_tr, y_v]))
        label_map = {int(l): i for i, l in enumerate(unique_labels)}
        y_tr = np.array([label_map[int(v)] for v in y_tr])
        y_v = np.array([label_map[int(v)] for v in y_v])
        num_classes = len(unique_labels)

        def _make_sequences(X: np.ndarray, y: np.ndarray, seq_len: int):
            xs, ys = [], []
            for i in range(seq_len, len(X)):
                xs.append(X[i - seq_len : i])
                ys.append(y[i])
            return np.array(xs), np.array(ys)

        X_tr_seq, y_tr_seq = _make_sequences(X_tr, y_tr, sequence_length)
        X_v_seq, y_v_seq = _make_sequences(X_v, y_v, sequence_length)

        if len(X_tr_seq) == 0:
            log.warning("Not enough data for LSTM sequence_length={}", sequence_length)
            raise ValueError("Insufficient data for LSTM sequences")

        input_size = X_tr_seq.shape[2]
        model = _LSTMClassifier(input_size, num_classes=num_classes).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        criterion = nn.CrossEntropyLoss()

        train_t = torch.tensor(X_tr_seq, device=device)
        train_y = torch.tensor(y_tr_seq, device=device)
        val_t = torch.tensor(X_v_seq, device=device)
        val_y = torch.tensor(y_v_seq, device=device)

        best_val_loss = float("inf")
        patience, wait = 10, 0
        batch_size = 256

        for epoch in range(1, epochs + 1):
            model.train()
            indices = torch.randperm(len(train_t))
            epoch_loss = 0.0
            for start in range(0, len(train_t), batch_size):
                idx = indices[start : start + batch_size]
                logits = model(train_t[idx])
                loss = criterion(logits, train_y[idx])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            model.eval()
            with torch.no_grad():
                val_logits = model(val_t)
                val_loss = criterion(val_logits, val_y).item()
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                wait = 0
            else:
                wait += 1
                if wait >= patience:
                    log.info("LSTM early stop at epoch {}", epoch)
                    break

        model.eval()
        with torch.no_grad():
            preds = model(val_t).argmax(dim=1).cpu().numpy()

        # Map predictions back to original labels
        inv_map = {v: k for k, v in label_map.items()}
        preds_orig = np.array([inv_map[p] for p in preds])
        y_v_orig = np.array([inv_map[v] for v in y_v_seq])

        metrics = self._compute_metrics(preds_orig, y_v_orig)
        metrics["label_map"] = label_map
        log.info("LSTM trained — val acc={:.4f} f1={:.4f}",
                 metrics["accuracy"], metrics["f1_weighted"])
        return model, metrics

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, model: Any, X_test: np.ndarray | pd.DataFrame,
                 y_test: np.ndarray | pd.Series) -> dict[str, Any]:
        """Returns accuracy, precision, recall, f1, classification_report, confusion_matrix."""
        preds = model.predict(X_test)
        return self._compute_metrics(preds, np.asarray(y_test))

    @staticmethod
    def _compute_metrics(preds: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
        return {
            "accuracy": float(accuracy_score(y_true, preds)),
            "precision_weighted": float(precision_score(y_true, preds, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_true, preds, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_true, preds, average="weighted", zero_division=0)),
            "classification_report": classification_report(y_true, preds, zero_division=0),
            "confusion_matrix": confusion_matrix(y_true, preds).tolist(),
        }

    # ------------------------------------------------------------------
    # Walk-forward validation
    # ------------------------------------------------------------------

    def walk_forward_validate(
        self,
        X: np.ndarray | pd.DataFrame,
        y: np.ndarray | pd.Series,
        model_type: str = "xgboost",
        n_splits: int = 5,
        train_pct: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Time-series walk-forward validation (no shuffling)."""
        X_arr = np.asarray(X)
        y_arr = np.asarray(y)
        n = len(X_arr)
        min_train = int(n * train_pct)
        fold_size = (n - min_train) // n_splits

        if fold_size < 10:
            log.warning("Not enough data for {} walk-forward splits", n_splits)
            return []

        results: list[dict[str, Any]] = []
        for i in range(n_splits):
            val_start = min_train + i * fold_size
            val_end = val_start + fold_size if i < n_splits - 1 else n
            if val_start >= n:
                break

            X_tr, y_tr = X_arr[:val_start], y_arr[:val_start]
            X_vl, y_vl = X_arr[val_start:val_end], y_arr[val_start:val_end]

            if model_type == "xgboost":
                model, metrics = self.train_xgboost(X_tr, y_tr, X_vl, y_vl)
            elif model_type == "lightgbm":
                model, metrics = self.train_lightgbm(X_tr, y_tr, X_vl, y_vl)
            else:
                raise ValueError(f"Unsupported model_type for walk-forward: {model_type}")

            metrics["fold"] = i
            metrics["train_size"] = len(X_tr)
            metrics["val_size"] = len(X_vl)
            results.append(metrics)
            log.info("Fold {}: acc={:.4f}", i, metrics["accuracy"])

        return results

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_model(self, model: Any, name: str, metrics: dict[str, Any]) -> None:
        """Save model to model_dir with metadata JSON."""
        import joblib

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"{name}_{ts}"

        if isinstance(model, nn.Module):
            model_path = self.model_dir / f"{fname}.pt"
            torch.save(model.state_dict(), model_path)
        else:
            model_path = self.model_dir / f"{fname}.pkl"
            joblib.dump(model, model_path)

        meta = {
            "name": name,
            "timestamp": ts,
            "model_file": model_path.name,
            "metrics": {
                k: v for k, v in metrics.items()
                if k not in ("classification_report", "confusion_matrix")
            },
        }
        meta_path = self.model_dir / f"{fname}_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        log.info("Saved model {} → {}", name, model_path)

    def load_model(self, name: str) -> tuple[Any, dict[str, Any]]:
        """Load the latest model + metadata matching *name*."""
        import joblib

        meta_files = sorted(self.model_dir.glob(f"{name}_*_meta.json"))
        if not meta_files:
            raise FileNotFoundError(f"No saved model found for '{name}'")

        meta_path = meta_files[-1]
        meta = json.loads(meta_path.read_text())
        model_file = self.model_dir / meta["model_file"]

        if model_file.suffix == ".pt":
            log.info("Loading PyTorch model from {}", model_file)
            state = torch.load(model_file, weights_only=True)
            return state, meta
        else:
            model = joblib.load(model_file)
            log.info("Loaded model {} from {}", name, model_file)
            return model, meta
