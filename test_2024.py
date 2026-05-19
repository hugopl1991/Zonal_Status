"""
Análise Zonal Estatística - Estoque de Carbono
===============================================
Calcula estatísticas zonais de rasters de estoque de carbono
para cada polígono de um shapefile de áreas suprimidas.

Dependências:
    pip install geopandas rasterstats pandas
"""

import geopandas as gpd
import pandas as pd
from rasterstats import zonal_stats

# ── CONFIGURE AQUI ────────────────────────────────────────
ANO = "2024"
ESTADOS = ["MA", "PA", "MG", "RJ", "ES", "BA", "SP"]

PASTA_RASTER = r"C:\Users\lima-\Downloads\Suprimidas\Estoque_solo\Csoil_Estoque"
PASTA_SHAPE  = r"C:\Users\lima-\Downloads\Suprimidas\Suprimidas\2024"
SAIDA        = r"C:\Users\lima-\Downloads\Suprimidas\resultado_2024.xlsx"
# ──────────────────────────────────────────────────────────

FATOR_C_CO2 = 3.67

resultados = []

for estado in ESTADOS:
    raster    = rf"{PASTA_RASTER}\{estado}_Csoil_1985-2025\raster_Csoil_MgCha_{estado}_{ANO}.tif"
    shapefile = rf"{PASTA_SHAPE}\sup24_v12_{estado}.shp"

    print(f"Processando {estado}...")

    try:
        gdf = gpd.read_file(shapefile)
        raw = zonal_stats(gdf, raster, stats=["count", "sum", "mean", "min", "max"])

        df = gdf.drop(columns="geometry")
        stats_df = pd.DataFrame(raw)

        df["estado"]         = estado
        df["count_pixels"]         = stats_df["count"]
        df["mean_MgCO2e"] = (stats_df["mean"] * FATOR_C_CO2).round(2)
        df["min_MgCO2e"]  = (stats_df["min"]  * FATOR_C_CO2).round(2)
        df["max_MgCO2e"]  = (stats_df["max"]  * FATOR_C_CO2).round(2)
        df["sum_MgCO2e"]  = (stats_df["sum"]  * FATOR_C_CO2).round(2)

        resultados.append(df)
        print(f"  ✔ {estado}: {len(df)} linhas")

    except Exception as e:
        print(f"  ⚠ {estado} pulado: {e}")

# Junta tudo e salva
if resultados:
    df_final = pd.concat(resultados, ignore_index=True)
    df_final.to_excel(SAIDA, index=False)
    print(f"\nPronto! {len(df_final)} linhas totais salvas em '{SAIDA}'")
else:
    print("\nNenhum estado processado com sucesso.")