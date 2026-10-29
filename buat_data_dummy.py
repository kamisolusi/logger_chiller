"""
Membuat data dummy data logger mesin chiller (20 signal, interval 1 jam).
Jalankan: python buat_data_dummy.py
Hasil   : chiller_log.csv
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

waktu = pd.date_range("2025-01-01 00:00", "2026-06-30 23:00", freq="h")
n = len(waktu)
jam = waktu.hour.values
hari_ke = waktu.dayofyear.values
akhir_pekan = waktu.dayofweek.values >= 5

# Suhu lingkungan: pola harian + musiman (iklim tropis)
ambient = 28 + 4 * np.sin((jam - 9) / 24 * 2 * np.pi) \
          + 1.2 * np.sin((hari_ke - 100) / 365 * 2 * np.pi) + rng.normal(0, 0.6, n)

# Status operasi: mati malam hari di akhir pekan + sesekali trip
run = np.ones(n)
run[akhir_pekan & ((jam < 6) | (jam >= 22))] = 0
trip = rng.random(n) < 0.004
for i in np.where(trip)[0]:
    run[i:i + rng.integers(2, 6)] = 0

# Beban pendinginan (0-1) mengikuti jam kerja dan suhu luar
beban = np.clip(0.35 + 0.45 * ((jam >= 8) & (jam <= 18)) + 0.04 * (ambient - 28)
                + rng.normal(0, 0.05, n), 0.2, 1.0) * run

cooling_load = 1200 * beban                                  # kW
chw_supply = np.where(run == 1, 6.8 + rng.normal(0, 0.25, n), ambient - 2)
chw_flow = np.where(run == 1, 180 + rng.normal(0, 4, n), 0)   # m3/h
delta_chw = np.where(run == 1, cooling_load / (chw_flow * 1.163 + 1e-9), 0)
chw_return = chw_supply + delta_chw

cw_flow = np.where(run == 1, 220 + rng.normal(0, 5, n), 0)
cw_supply = np.where(run == 1, ambient + 2.5 + rng.normal(0, 0.3, n), ambient)
comp_power = np.where(run == 1, cooling_load / (5.6 - 0.06 * (ambient - 28)) + rng.normal(0, 5, n), 0)
cw_return = cw_supply + np.where(run == 1, (cooling_load + comp_power) / (cw_flow * 1.163 + 1e-9), 0)
cop = np.where(run == 1, cooling_load / np.maximum(comp_power, 1), 0)
comp_current = comp_power * 1000 / (np.sqrt(3) * 400 * 0.9)

evap_press = np.where(run == 1, 360 + 8 * (chw_supply - 7) + rng.normal(0, 5, n), 500)
cond_press = np.where(run == 1, 900 + 25 * (cw_return - 35) + rng.normal(0, 10, n), 650)
suction_temp = np.where(run == 1, chw_supply - 3 + rng.normal(0, 0.4, n), ambient)
discharge_temp = np.where(run == 1, 55 + 0.03 * comp_power + rng.normal(0, 1, n), ambient + 3)
oil_press = np.where(run == 1, 300 + rng.normal(0, 6, n), 0)
oil_temp = np.where(run == 1, 45 + 0.01 * comp_power + rng.normal(0, 0.8, n), ambient + 5)
winding_temp = np.where(run == 1, 60 + 0.05 * comp_power + rng.normal(0, 1.5, n), ambient + 8)
vibration = np.where(run == 1, 1.8 + 0.6 * beban + rng.normal(0, 0.15, n), 0.05)

# Sisipkan beberapa anomali agar ada yang melewati batas alarm
anomali = rng.choice(n, 40, replace=False)
vibration[anomali] += rng.uniform(2.5, 4.0, 40)
discharge_temp[anomali[:15]] += rng.uniform(15, 25, 15)

df = pd.DataFrame({
    "Timestamp": waktu,
    "CHW_Supply_Temp_C": chw_supply,
    "CHW_Return_Temp_C": chw_return,
    "CW_Supply_Temp_C": cw_supply,
    "CW_Return_Temp_C": cw_return,
    "CHW_Flow_m3h": chw_flow,
    "CW_Flow_m3h": cw_flow,
    "Evap_Pressure_kPa": evap_press,
    "Cond_Pressure_kPa": cond_press,
    "Suction_Temp_C": suction_temp,
    "Discharge_Temp_C": discharge_temp,
    "Oil_Pressure_kPa": oil_press,
    "Oil_Temp_C": oil_temp,
    "Compressor_Current_A": comp_current,
    "Compressor_Power_kW": comp_power,
    "Cooling_Load_kW": cooling_load,
    "COP": cop,
    "Motor_Winding_Temp_C": winding_temp,
    "Vibration_mm_s": vibration,
    "Ambient_Temp_C": ambient,
    "Run_Status": run.astype(int),
})
kolom = df.columns[1:]
df[kolom] = df[kolom].round(2)
df.to_csv("chiller_log.csv", index=False)
print(f"chiller_log.csv dibuat: {len(df):,} baris, {df.shape[1] - 1} signal")
