"""Optional PyTorch GRU one-step model with recursive forecast."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from app.services.forecast.constants import MIN_HISTORY_FOR_FULL
from app.services.forecast.models_arima import forecast_arima


def forecast_rnn(series: pd.Series, horizon: int, last_period: pd.Timestamp, seq_len: int = 12) -> list[float]:
    del last_period  # horizon uses recursive history only
    if len(series) < max(MIN_HISTORY_FOR_FULL, seq_len + 4) or horizon < 1:
        return forecast_arima(series, horizon)
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        return forecast_arima(series, horizon)

    class TinyGRU(nn.Module):
        def __init__(self, hidden: int = 32):
            super().__init__()
            self.gru = nn.GRU(1, hidden, batch_first=True)
            self.fc = nn.Linear(hidden, 1)

        def forward(self, x):
            out, _ = self.gru(x)
            return self.fc(out[:, -1, :])

    try:
        y = series.values.astype(np.float64).reshape(-1, 1)
        scaler = StandardScaler()
        ys = scaler.fit_transform(y).flatten()
        X_list, t_list = [], []
        for i in range(seq_len, len(ys)):
            X_list.append(ys[i - seq_len : i])
            t_list.append(ys[i])
        if len(X_list) < 8:
            return forecast_arima(series, horizon)
        X = np.stack(X_list, axis=0)[..., np.newaxis].astype(np.float32)
        t = np.array(t_list, dtype=np.float32)
        n_val = min(4, max(1, len(X) // 4))
        X_tr, t_tr = X[:-n_val], t[:-n_val]
        X_va, t_va = X[-n_val:], t[-n_val:]

        device = torch.device("cpu")
        model = TinyGRU().to(device)
        opt = torch.optim.Adam(model.parameters(), lr=0.05)
        loss_fn = nn.MSELoss()
        Xt = torch.from_numpy(X_tr).to(device)
        tt = torch.from_numpy(t_tr).to(device)
        model.train()
        for _ in range(120):
            opt.zero_grad()
            pred = model(Xt).squeeze(-1)
            loss = loss_fn(pred, tt)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            va_loss = loss_fn(model(torch.from_numpy(X_va).to(device)).squeeze(-1), torch.from_numpy(t_va).to(device))
        if torch.isnan(va_loss):
            return forecast_arima(series, horizon)

        hist = ys.tolist()
        preds: list[float] = []
        for _ in range(horizon):
            window = np.array(hist[-seq_len:], dtype=np.float32).reshape(1, seq_len, 1)
            with torch.no_grad():
                p_s = model(torch.from_numpy(window).to(device)).cpu().numpy().reshape(-1)[0]
            p = float(scaler.inverse_transform([[p_s]])[0, 0])
            preds.append(p)
            hist.append(float(scaler.transform([[p]])[0, 0]))
        return preds
    except Exception:
        return forecast_arima(series, horizon)
