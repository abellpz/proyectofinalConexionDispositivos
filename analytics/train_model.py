import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

np.random.seed(42)
n_samples = 3000

# Variables sintéticas
nivel_actual = np.random.uniform(0.5, 4.5, n_samples)
dh_dt = np.random.normal(0.01, 0.08, n_samples)
lluvia_1h = np.random.exponential(5.0, n_samples)
lluvia_prev_6h = np.random.uniform(0.0, 60.0, n_samples)

# Regla de verdad terreno: Desbordamiento en T+60 min (1: Sí, 0: No)
prob_desborde = (
    0.35 * (nivel_actual > 3.0) +
    0.30 * (dh_dt > 0.12) +
    0.25 * (lluvia_1h > 25.0) +
    0.20 * (lluvia_prev_6h > 40.0)
)
target = (prob_desborde + np.random.normal(0, 0.05, n_samples) > 0.6).astype(int)

df = pd.DataFrame({
    'nivel_rio_m': nivel_actual,
    'dH_dt_m_min': dh_dt,
    'lluvia_1h_mm': lluvia_1h,
    'lluvia_prev_6h_mm': lluvia_prev_6h,
    'target_desborde_60m': target
})

X = df[['nivel_rio_m', 'dH_dt_m_min', 'lluvia_1h_mm', 'lluvia_prev_6h_mm']]
y = df['target_desborde_60m']

clf = RandomForestClassifier(n_estimators=80, max_depth=6, random_state=42)
clf.fit(X, y)

joblib.dump(clf, "modelo_inundacion.joblib")
print("[*] Modelo exportado: modelo_inundacion.joblib")
print(classification_report(y, clf.predict(X)))