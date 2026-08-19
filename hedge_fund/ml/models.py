"""ML models for trading signal prediction."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from ..utils.logger import get_logger

log = get_logger("ml.models")


class ScalpingModel:
    """XGBoost classifier predicting up / down / flat."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self._params = params or {
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "multi:softprob",
            "num_class": 3,
            "eval_metric": "mlogloss",
            "use_label_encoder": False,
        }
        self._model: Any = None

    def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        import xgboost as xgb

        self._model = xgb.XGBClassifier(**self._params)
        self._model.fit(X, y)
        preds = self._model.predict(X)
        accuracy = float(np.mean(preds == y))
        log.info("ScalpingModel trained – accuracy {:.4f} on {} samples", accuracy, len(y))
        return {"accuracy": accuracy}

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not trained")
        return self._model.predict_proba(X)

    def feature_importance(self) -> dict[str, float]:
        if self._model is None:
            return {}
        imp = self._model.get_booster().get_score(importance_type="gain")
        return dict(sorted(imp.items(), key=lambda kv: kv[1], reverse=True))

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._model, f)
        log.info("ScalpingModel saved to {}", path)

    def load(self, path: str | Path) -> None:
        with open(path, "rb") as f:
            self._model = pickle.load(f)
        log.info("ScalpingModel loaded from {}", path)


class SwingModel:
    """LightGBM regressor predicting forward returns."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self._params = params or {
            "n_estimators": 500,
            "max_depth": 8,
            "learning_rate": 0.03,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "objective": "regression",
            "metric": "mse",
            "verbosity": -1,
        }
        self._model: Any = None

    def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        import lightgbm as lgb

        self._model = lgb.LGBMRegressor(**self._params)
        self._model.fit(X, y)
        preds = self._model.predict(X)
        mse = float(np.mean((preds - y) ** 2))
        log.info("SwingModel trained – MSE {:.6f} on {} samples", mse, len(y))
        return {"mse": mse}

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not trained")
        return self._model.predict(X)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self._model, f)

    def load(self, path: str | Path) -> None:
        with open(path, "rb") as f:
            self._model = pickle.load(f)


class LSTMModel:
    """PyTorch 2-layer LSTM with attention and dropout."""

    def __init__(
        self,
        input_size: int = 64,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        lr: float = 1e-3,
        epochs: int = 50,
        batch_size: int = 64,
        seq_len: int = 30,
    ) -> None:
        self._input_size = input_size
        self._hidden_size = hidden_size
        self._num_layers = num_layers
        self._dropout = dropout
        self._lr = lr
        self._epochs = epochs
        self._batch_size = batch_size
        self._seq_len = seq_len
        self._model: Any = None
        self._device: Any = None

    def _build_model(self) -> Any:
        import torch
        import torch.nn as nn

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._device = device

        class _Attention(nn.Module):
            def __init__(self, hidden: int) -> None:
                super().__init__()
                self.attn = nn.Linear(hidden, 1)

            def forward(self, lstm_out: torch.Tensor) -> torch.Tensor:
                weights = torch.softmax(self.attn(lstm_out), dim=1)
                return (weights * lstm_out).sum(dim=1)

        class _LSTMNet(nn.Module):
            def __init__(self, inp: int, hid: int, layers: int, drop: float) -> None:
                super().__init__()
                self.lstm = nn.LSTM(inp, hid, layers, batch_first=True, dropout=drop)
                self.attention = _Attention(hid)
                self.dropout = nn.Dropout(drop)
                self.fc = nn.Linear(hid, 3)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                out, _ = self.lstm(x)
                ctx = self.attention(out)
                ctx = self.dropout(ctx)
                return self.fc(ctx)

        model = _LSTMNet(self._input_size, self._hidden_size, self._num_layers, self._dropout).to(device)
        log.info("LSTM model on device {}", device)
        return model

    def _make_sequences(self, X: np.ndarray) -> np.ndarray:
        seqs = []
        for i in range(self._seq_len, len(X)):
            seqs.append(X[i - self._seq_len : i])
        return np.array(seqs, dtype=np.float32)

    def train(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        self._model = self._build_model()
        X_seq = self._make_sequences(X)
        y_seq = y[self._seq_len:]

        dataset = TensorDataset(
            torch.tensor(X_seq, dtype=torch.float32),
            torch.tensor(y_seq, dtype=torch.long),
        )
        loader = DataLoader(dataset, batch_size=self._batch_size, shuffle=True)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=self._lr)
        criterion = nn.CrossEntropyLoss()

        self._model.train()
        final_loss = 0.0
        for epoch in range(self._epochs):
            epoch_loss = 0.0
            for xb, yb in loader:
                xb, yb = xb.to(self._device), yb.to(self._device)
                optimizer.zero_grad()
                out = self._model(xb)
                loss = criterion(out, yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
                optimizer.step()
                epoch_loss += loss.item()
            final_loss = epoch_loss / max(len(loader), 1)
            if (epoch + 1) % 10 == 0:
                log.info("LSTM epoch {}/{} loss={:.4f}", epoch + 1, self._epochs, final_loss)

        return {"final_loss": final_loss}

    def predict(self, X: np.ndarray) -> np.ndarray:
        import torch

        if self._model is None:
            raise RuntimeError("Model not trained")
        self._model.eval()
        X_seq = self._make_sequences(X)
        with torch.no_grad():
            t = torch.tensor(X_seq, dtype=torch.float32).to(self._device)
            out = self._model(t)
            proba = torch.softmax(out, dim=1).cpu().numpy()
        return proba

    def save(self, path: str | Path) -> None:
        import torch

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._model.state_dict(), path)

    def load(self, path: str | Path) -> None:
        import torch

        self._model = self._build_model()
        self._model.load_state_dict(torch.load(path, map_location=self._device))
        self._model.eval()


class EnsembleModel:
    """Weighted combination of models with adaptive weight adjustment."""

    def __init__(
        self,
        scalping: ScalpingModel | None = None,
        swing: SwingModel | None = None,
        lstm: LSTMModel | None = None,
        weights: dict[str, float] | None = None,
        adjustment_rate: float = 0.05,
    ) -> None:
        self._models: dict[str, Any] = {}
        if scalping:
            self._models["scalping"] = scalping
        if swing:
            self._models["swing"] = swing
        if lstm:
            self._models["lstm"] = lstm

        default_w = 1.0 / max(len(self._models), 1)
        self._weights = weights or {k: default_w for k in self._models}
        self._adjustment_rate = adjustment_rate
        self._accuracy_history: dict[str, list[float]] = {k: [] for k in self._models}

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._models:
            raise RuntimeError("No models registered")

        combined: np.ndarray | None = None
        total_w = 0.0
        for name, model in self._models.items():
            w = self._weights.get(name, 0.0)
            if w <= 0:
                continue
            preds = model.predict(X)
            if preds.ndim == 1:
                preds = preds.reshape(-1, 1)
            if combined is None:
                combined = np.zeros_like(preds)
            if combined.shape == preds.shape:
                combined += w * preds
                total_w += w

        if combined is None or total_w == 0:
            raise RuntimeError("All model weights are zero")
        return combined / total_w

    def update_weights(self, actual: np.ndarray, predictions: dict[str, np.ndarray]) -> None:
        """Adjust weights based on recent prediction accuracy."""
        for name in self._models:
            if name not in predictions:
                continue
            preds = predictions[name]
            if preds.ndim > 1:
                pred_classes = preds.argmax(axis=1)
            else:
                pred_classes = (preds > 0).astype(int)
            acc = float(np.mean(pred_classes == actual))
            self._accuracy_history[name].append(acc)
            if len(self._accuracy_history[name]) > 20:
                self._accuracy_history[name] = self._accuracy_history[name][-20:]

        if not any(self._accuracy_history[n] for n in self._models):
            return

        avg_accs = {}
        for name in self._models:
            hist = self._accuracy_history[name]
            avg_accs[name] = float(np.mean(hist)) if hist else 0.5

        total = sum(avg_accs.values())
        if total > 0:
            for name in self._models:
                target = avg_accs[name] / total
                current = self._weights.get(name, 0.0)
                self._weights[name] = current + self._adjustment_rate * (target - current)

        log.info("Ensemble weights updated: {}", {k: round(v, 3) for k, v in self._weights.items()})

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)
