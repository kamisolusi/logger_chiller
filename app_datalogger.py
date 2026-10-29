"""
Data Logger Chiller CH-01
Aplikasi Streamlit untuk melihat data logger mesin chiller.

Cara menjalankan:
    pip install streamlit pandas plotly
    streamlit run app_datalogger.py

File chiller_log.csv harus berada di folder yang sama,
atau unggah CSV sendiri dari sidebar.
"""

import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Data Logger Chiller", page_icon="❄️", layout="wide")

# ------------------------------------------------------------------
# Warna & gaya
# ------------------------------------------------------------------
LATAR = "#EEF2F5"
TINTA = "#1C2733"
ES = "#2A7AB0"       # biru air dingin
ES_MUDA = "#CFE3F1"
KUNING = "#D98E04"   # peringatan
MERAH = "#C0392B"    # alarm
HIJAU = "#2E8B57"    # running

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Semi+Condensed:wght@500;600;700&display=swap');

    .stApp {{ background: {LATAR}; }}
    html, body, [class*="css"], .stApp {{
        font-family: 'Barlow', system-ui, sans-serif;
        color: {TINTA};
    }}
    h1, h2, h3 {{
        font-family: 'Barlow Semi Condensed', 'Barlow', sans-serif !important;
        color: {TINTA} !important;
    }}
    section[data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 3px solid {ES};
    }}

    .panel-atas {{
        display: flex; flex-wrap: wrap; align-items: flex-end;
        justify-content: space-between; gap: 1rem;
        border-bottom: 3px solid {ES};
        padding-bottom: 0.8rem; margin-bottom: 1rem;
    }}
    .judul {{
        font-family: 'Barlow Semi Condensed', sans-serif;
        font-weight: 700; font-size: clamp(2rem, 4vw, 3rem); line-height: 1;
    }}
    .judul small {{
        display: block; font-family: 'Barlow', sans-serif;
        font-weight: 400; font-size: 1rem; opacity: 0.7; margin-top: 0.4rem;
    }}
    .lampu {{
        display: inline-flex; align-items: center; gap: 0.5rem;
        background: #FFFFFF; padding: 0.5rem 0.9rem; border-radius: 999px;
        font-weight: 600;
    }}
    .lampu i {{
        width: 12px; height: 12px; border-radius: 50%; display: inline-block;
    }}

    .gauge-baris {{
        display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
        gap: 0.6rem; margin-bottom: 1.2rem;
    }}
    .gauge {{
        background: #FFFFFF; padding: 0.7rem 0.9rem; border-radius: 6px;
        border-top: 4px solid {ES};
    }}
    .gauge.warn {{ border-top-color: {KUNING}; }}
    .gauge.alarm {{ border-top-color: {MERAH}; }}
    .gauge .nama {{ font-size: 0.85rem; opacity: 0.75; }}
    .gauge .nilai {{
        font-family: 'Barlow Semi Condensed', sans-serif;
        font-size: 1.7rem; font-weight: 600; line-height: 1.2;
    }}
    .gauge .satuan {{ font-size: 0.9rem; opacity: 0.6; margin-left: 0.2rem; }}
    .gauge .rentang {{ font-size: 0.8rem; opacity: 0.6; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Daftar 20 signal: nama kolom -> (label, satuan, kelompok, batas bawah, batas atas)
# ------------------------------------------------------------------
SIGNAL = {
    "CHW_Supply_Temp_C":    ("Suhu CHW supply", "°C", "Air dingin (CHW)", 5.5, 8.5),
    "CHW_Return_Temp_C":    ("Suhu CHW return", "°C", "Air dingin (CHW)", 8, 15),
    "CHW_Flow_m3h":         ("Debit CHW", "m³/h", "Air dingin (CHW)", 160, 200),
    "CW_Supply_Temp_C":     ("Suhu CW supply", "°C", "Air kondensor (CW)", 25, 34),
    "CW_Return_Temp_C":     ("Suhu CW return", "°C", "Air kondensor (CW)", 28, 40),
    "CW_Flow_m3h":          ("Debit CW", "m³/h", "Air kondensor (CW)", 200, 240),
    "Evap_Pressure_kPa":    ("Tekanan evaporator", "kPa", "Refrigeran", 330, 400),
    "Cond_Pressure_kPa":    ("Tekanan kondensor", "kPa", "Refrigeran", 750, 1100),
    "Suction_Temp_C":       ("Suhu suction", "°C", "Refrigeran", 2, 6),
    "Discharge_Temp_C":     ("Suhu discharge", "°C", "Refrigeran", 50, 75),
    "Oil_Pressure_kPa":     ("Tekanan oli", "kPa", "Kompresor", 280, 320),
    "Oil_Temp_C":           ("Suhu oli", "°C", "Kompresor", 40, 55),
    "Compressor_Current_A": ("Arus kompresor", "A", "Kompresor", 0, 400),
    "Compressor_Power_kW":  ("Daya kompresor", "kW", "Kompresor", 0, 250),
    "Motor_Winding_Temp_C": ("Suhu belitan motor", "°C", "Kompresor", 40, 80),
    "Vibration_mm_s":       ("Getaran", "mm/s", "Kompresor", 0, 4.5),
    "Cooling_Load_kW":      ("Beban pendinginan", "kW", "Performa", 0, 1300),
    "COP":                  ("COP", "", "Performa", 4.0, 7.5),
    "Ambient_Temp_C":       ("Suhu lingkungan", "°C", "Performa", 20, 36),
    "Run_Status":           ("Status running", "", "Performa", 0, 1),
}
NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]


def label(kol):
    nama, satuan = SIGNAL[kol][0], SIGNAL[kol][1]
    return f"{nama} ({satuan})" if satuan else nama


# ------------------------------------------------------------------
# Muat data
# ------------------------------------------------------------------
def ke_angka(kolom):
    """Ubah kolom teks jadi angka, termasuk format koma desimal (12,5)."""
    if not pd.api.types.is_numeric_dtype(kolom):
        kolom = kolom.astype(str).str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(kolom, errors="coerce")


@st.cache_data
def baca_mentah(isi_file: bytes):
    """Baca CSV dengan deteksi pemisah otomatis (koma atau titik koma)."""
    return pd.read_csv(io.BytesIO(isi_file), sep=None, engine="python")


def siapkan(mentah, kolom_waktu):
    df = mentah.copy()
    teks = df[kolom_waktu].astype(str).str.strip()
    # Coba format ISO dulu (2025-01-31 08:00), lalu format Indonesia (31/01/2025 08:00)
    waktu = pd.to_datetime(teks, errors="coerce", format="ISO8601")
    if waktu.isna().mean() > 0.5:
        waktu = pd.to_datetime(teks, errors="coerce", dayfirst=True)
    df["Timestamp"] = waktu
    if kolom_waktu != "Timestamp":
        df = df.drop(columns=[kolom_waktu])
    df = df.dropna(subset=["Timestamp"])
    for kol in df.columns:
        if kol != "Timestamp":
            df[kol] = ke_angka(df[kol])
    df = df.dropna(axis=1, how="all")
    return df.sort_values("Timestamp").reset_index(drop=True)


file_bawaan = Path(__file__).parent / "chiller_log.csv"
if "data" not in st.session_state:
    if file_bawaan.exists():
        mentah = baca_mentah(file_bawaan.read_bytes())
        st.session_state.data = siapkan(mentah, "Timestamp")
        st.session_state.nama_sumber = "chiller_log.csv (bawaan)"
    else:
        st.session_state.data = None
        st.session_state.nama_sumber = None

with st.sidebar:
    st.markdown("### ❄️ Sumber data")
    if st.session_state.nama_sumber:
        st.caption(f"Sedang dipakai: **{st.session_state.nama_sumber}**")

    unggah = st.file_uploader("Unggah CSV baru", type="csv")
    if unggah is not None:
        try:
            mentah = baca_mentah(unggah.getvalue())
        except Exception as e:
            st.error(f"File tidak bisa dibaca sebagai CSV: {e}")
            mentah = None

        if mentah is not None:
            st.write(f"Terbaca **{len(mentah):,}** baris, **{mentah.shape[1]}** kolom.")
            kolom = list(mentah.columns)
            tebakan = next((i for i, k in enumerate(kolom)
                            if any(x in str(k).lower() for x in ["time", "waktu", "tanggal", "date"])), 0)
            kolom_waktu = st.selectbox("Kolom waktu", kolom, index=tebakan)
            with st.expander("Lihat 5 baris pertama"):
                st.dataframe(mentah.head(), hide_index=True)

            if st.button("▶ Proses CSV", type="primary", use_container_width=True):
                hasil = siapkan(mentah, kolom_waktu)
                if hasil.empty:
                    st.error(f"Kolom '{kolom_waktu}' tidak berisi tanggal/waktu yang valid. Pilih kolom waktu yang lain.")
                else:
                    st.session_state.data = hasil
                    st.session_state.nama_sumber = unggah.name
                    st.session_state.pop("signal_terpilih", None)
                    st.success(f"CSV diproses: {len(hasil):,} baris, {hasil.shape[1] - 1} signal.")

    if file_bawaan.exists() and st.session_state.nama_sumber != "chiller_log.csv (bawaan)":
        if st.button("Kembali ke data bawaan", use_container_width=True):
            st.session_state.data = siapkan(baca_mentah(file_bawaan.read_bytes()), "Timestamp")
            st.session_state.nama_sumber = "chiller_log.csv (bawaan)"
            st.session_state.pop("signal_terpilih", None)
            st.rerun()

df = st.session_state.data
if df is None:
    st.info("Unggah file CSV data logger dari sidebar, lalu klik **Proses CSV**.")
    st.stop()

# Kolom yang tidak dikenal tetap ditampilkan sebagai signal di kelompok "Lainnya".
# Batasnya diambil dari min/max data, jadi tidak memicu alarm.
for kol in df.columns:
    if kol != "Timestamp" and kol not in SIGNAL:
        SIGNAL[kol] = (kol, "", "Lainnya", float(df[kol].min()), float(df[kol].max()))

tersedia = [k for k in SIGNAL if k in df.columns]
KELOMPOK = list(dict.fromkeys(SIGNAL[k][2] for k in tersedia))

# ------------------------------------------------------------------
# Sidebar: filter waktu & signal
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📅 Filter waktu")

    daftar_tahun = sorted(df["Timestamp"].dt.year.unique())
    tahun = st.selectbox("Tahun", ["Semua"] + daftar_tahun, index=len(daftar_tahun))

    d = df if tahun == "Semua" else df[df["Timestamp"].dt.year == tahun]
    daftar_bulan = sorted(d["Timestamp"].dt.month.unique())
    bulan = st.selectbox(
        "Bulan", ["Semua"] + daftar_bulan,
        format_func=lambda b: b if b == "Semua" else NAMA_BULAN[b - 1],
    )

    if bulan != "Semua":
        d = d[d["Timestamp"].dt.month == bulan]
    daftar_hari = sorted(d["Timestamp"].dt.day.unique())
    hari = st.selectbox("Hari (tanggal)", ["Semua"] + daftar_hari)

    if hari != "Semua":
        d = d[d["Timestamp"].dt.day == hari]
        jam = st.slider("Rentang jam", 0, 23, (0, 23))
        d = d[d["Timestamp"].dt.hour.between(*jam)]

    st.markdown("### 📈 Filter signal")
    kelompok = st.multiselect("Kelompok", KELOMPOK, default=KELOMPOK)
    pilihan_signal = [k for k in tersedia if SIGNAL[k][2] in kelompok]
    signal = st.multiselect(
        "Signal", pilihan_signal,
        default=([k for k in ["CHW_Supply_Temp_C", "CHW_Return_Temp_C",
                              "Compressor_Power_kW", "Vibration_mm_s"] if k in pilihan_signal]
                 or pilihan_signal[:4]),
        format_func=label,
        key="signal_terpilih",
    )

    st.markdown("### ⚙️ Opsi")
    hanya_jalan = st.toggle("Hanya saat mesin running", value=True)
    resolusi = st.radio("Resolusi data", ["Per jam", "Rata-rata harian"], horizontal=True)
    tampil_batas = st.toggle("Tampilkan garis batas alarm", value=True)

data = d.copy()
if hanya_jalan and "Run_Status" in data.columns:
    data = data[data["Run_Status"] == 1]
if resolusi == "Rata-rata harian" and not data.empty:
    data = data.set_index("Timestamp").resample("D").mean(numeric_only=True).dropna(how="all").reset_index()

# ------------------------------------------------------------------
# Panel atas
# ------------------------------------------------------------------
terakhir = df.iloc[-1]
jalan = int(terakhir.get("Run_Status", 1)) == 1
warna_lampu = HIJAU if jalan else MERAH
teks_lampu = "Running" if jalan else "Stop"

periode = "Semua data" if tahun == "Semua" else str(tahun)
if bulan != "Semua":
    periode = f"{NAMA_BULAN[bulan - 1]} {periode}"
if hari != "Semua":
    periode = f"{hari} {periode}"

st.markdown(
    f"""
    <div class="panel-atas">
        <div class="judul">Chiller CH-01
            <small>Periode: {periode} &nbsp;|&nbsp; {len(data):,} titik data</small>
        </div>
        <div class="lampu"><i style="background:{warna_lampu}"></i>{teks_lampu}
            <span style="font-weight:400;opacity:.7">
            &nbsp;data terakhir {terakhir['Timestamp']:%d/%m/%Y %H:%M}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not signal:
    st.info("Pilih minimal satu signal di sidebar untuk menampilkan grafik.")
    st.stop()
if data.empty:
    st.warning("Tidak ada data pada periode ini. Ubah filter waktu atau matikan opsi 'Hanya saat mesin running'.")
    st.stop()


def status(kol, nilai):
    bawah, atas = SIGNAL[kol][3], SIGNAL[kol][4]
    if nilai < bawah or nilai > atas:
        return "alarm"
    margin = (atas - bawah) * 0.1
    if nilai < bawah + margin or nilai > atas - margin:
        return "warn"
    return ""


# Kartu nilai terakhir pada periode terpilih
kartu = []
for kol in signal:
    nilai = data[kol].iloc[-1]
    kartu.append(
        f'<div class="gauge {status(kol, nilai)}">'
        f'<div class="nama">{SIGNAL[kol][0]}</div>'
        f'<div class="nilai">{nilai:,.2f}<span class="satuan">{SIGNAL[kol][1]}</span></div>'
        f'<div class="rentang">batas {SIGNAL[kol][3]} – {SIGNAL[kol][4]}</div></div>'
    )
st.markdown(f'<div class="gauge-baris">{"".join(kartu)}</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# Tab
# ------------------------------------------------------------------
tab_grafik, tab_ringkas, tab_alarm, tab_data = st.tabs(
    ["Grafik trend", "Ringkasan statistik", "Kejadian alarm", "Data mentah"]
)

with tab_grafik:
    mode = st.radio("Tampilan", ["Grafik terpisah", "Gabung dalam satu grafik"], horizontal=True)
    palet = [ES, "#7B4FA0", "#1A9C8C", KUNING, "#B5476B", "#4F6D8A", "#8A6D1F", "#3B9C3B"]

    if mode == "Grafik terpisah":
        fig = make_subplots(rows=len(signal), cols=1, shared_xaxes=True,
                            vertical_spacing=0.04 if len(signal) > 1 else 0,
                            subplot_titles=[label(k) for k in signal])
        for i, kol in enumerate(signal, start=1):
            warna = palet[(i - 1) % len(palet)]
            fig.add_trace(go.Scatter(x=data["Timestamp"], y=data[kol], name=label(kol),
                                     line=dict(color=warna, width=1.6), showlegend=False),
                          row=i, col=1)
            if tampil_batas:
                for batas in (SIGNAL[kol][3], SIGNAL[kol][4]):
                    fig.add_hline(y=batas, line=dict(color=MERAH, width=1, dash="dash"),
                                  opacity=0.6, row=i, col=1)
        fig.update_layout(height=max(260, 210 * len(signal)))
    else:
        st.caption("Nilai dinormalisasi ke 0–100% agar signal dengan satuan berbeda bisa dibandingkan.")
        fig = go.Figure()
        for i, kol in enumerate(signal):
            s = data[kol]
            norm = (s - s.min()) / (s.max() - s.min()) * 100 if s.max() != s.min() else s * 0
            fig.add_trace(go.Scatter(x=data["Timestamp"], y=norm, name=label(kol),
                                     line=dict(color=palet[i % len(palet)], width=1.6),
                                     customdata=s, hovertemplate="%{customdata:.2f}<extra>" + label(kol) + "</extra>"))
        fig.update_layout(height=480, yaxis_title="% dari rentang",
                          legend=dict(orientation="h", y=-0.15))

    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(family="Barlow, sans-serif", color=TINTA),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="#E3E9EE")
    fig.update_yaxes(gridcolor="#E3E9EE")
    st.plotly_chart(fig, use_container_width=True)

with tab_ringkas:
    ringkas = pd.DataFrame({
        "Signal": [label(k) for k in signal],
        "Minimum": [data[k].min() for k in signal],
        "Rata-rata": [data[k].mean() for k in signal],
        "Maksimum": [data[k].max() for k in signal],
        "Std. deviasi": [data[k].std() for k in signal],
        "Batas bawah": [SIGNAL[k][3] for k in signal],
        "Batas atas": [SIGNAL[k][4] for k in signal],
        "Jumlah alarm": [int(((data[k] < SIGNAL[k][3]) | (data[k] > SIGNAL[k][4])).sum()) for k in signal],
    })
    st.dataframe(ringkas.round(2), hide_index=True, use_container_width=True)

with tab_alarm:
    kejadian = []
    for kol in signal:
        bawah, atas = SIGNAL[kol][3], SIGNAL[kol][4]
        luar = data[(data[kol] < bawah) | (data[kol] > atas)]
        for _, r in luar.iterrows():
            kejadian.append({
                "Waktu": r["Timestamp"],
                "Signal": label(kol),
                "Nilai": round(r[kol], 2),
                "Jenis": "Terlalu tinggi" if r[kol] > atas else "Terlalu rendah",
                "Batas": f"{bawah} – {atas}",
            })
    if kejadian:
        tabel_alarm = pd.DataFrame(kejadian).sort_values("Waktu", ascending=False)
        st.write(f"Ditemukan **{len(tabel_alarm)}** nilai di luar batas pada signal yang dipilih.")
        st.dataframe(tabel_alarm, hide_index=True, use_container_width=True)
    else:
        st.success("Tidak ada nilai di luar batas pada periode dan signal yang dipilih.")

with tab_data:
    tampil = data[["Timestamp"] + signal]
    st.dataframe(tampil, hide_index=True, use_container_width=True, height=420)
    st.download_button(
        "Unduh data terfilter (CSV)",
        data=tampil.to_csv(index=False).encode("utf-8"),
        file_name=f"chiller_{periode.replace(' ', '_')}.csv",
        mime="text/csv",
    )
