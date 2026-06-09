"""
Análise Zonal Estatística - Estoque de Carbono
===============================================
"""

import geopandas as gpd
import pandas as pd
import rasterio
from exactextract import exact_extract

# ── CONFIGURE AQUI ────────────────────────────────────────
ANO = "2024"
ESTADOS = ["MA", "PA", "MG", "RJ", "ES", "BA", "SP"]

PASTA_RASTER = r"C:\Users\lima-\Downloads\Suprimidas\Dados\TAGB_BGB_Estoque"
PASTA_SHAPE  = r"C:\Users\lima-\Downloads\Suprimidas\Dados\Suprimidas\2024"
SAIDA        = r"C:\Users\lima-\Downloads\Suprimidas\resultado_2024.xlsx"
SAIDA_SHP    = r"C:\Users\lima-\Downloads\Suprimidas\resultado_2024.shp"
# ──────────────────────────────────────────────────────────

FATOR_C_CO2   = 3.67
AREA_PIXEL_HA = 0.09  # 30m x 30m em hectares

resultados    = []
geodataframes = []

for estado in ESTADOS:
    raster    = rf"{PASTA_RASTER}\{estado}_1985-2025\raster_TAGB_BGB_MgCha_{estado}_{ANO}.tif"
    shapefile = rf"{PASTA_SHAPE}\sup24_v12_{estado}.shp"

    print(f"Processando {estado}...")

    try:
        gdf = gpd.read_file(shapefile)

        gdf = gdf.to_crs("EPSG:5880")
        gdf["area_calc_ha"] = (gdf.geometry.area / 10000).round(4)
        gdf = gdf.to_crs("EPSG:4326")

        with rasterio.open(raster) as src:
            raster_crs = src.crs

        gdf_reproj = gdf.to_crs(raster_crs)

        stats_df = exact_extract(
            raster, gdf_reproj,
            ["count", "sum", "mean", "min", "max"],
            output="pandas"
        ).reset_index(drop=True)

        # ── Tabela sem geometria (Excel — nomes longos OK) ─
        df = gdf.drop(columns="geometry").reset_index(drop=True)
        df["estado"]         = estado
        df["count_pixels"]   = stats_df["count"].round(1)
        df["mean_MgCO2e_ha"] = (stats_df["mean"] * FATOR_C_CO2).round(2)
        df["min_MgCO2e_ha"]  = (stats_df["min"]  * FATOR_C_CO2).round(2)
        df["max_MgCO2e_ha"]  = (stats_df["max"]  * FATOR_C_CO2).round(2)
        df["sum_MgCO2e_ha"]  = (stats_df["sum"]  * FATOR_C_CO2).round(2)
        df["sum_MgCO2e"]     = (stats_df["sum"]  * FATOR_C_CO2 * AREA_PIXEL_HA).round(2)
        resultados.append(df)

        # ── GeoDataFrame (Shapefile — nomes ≤ 10 chars) ───
        gdf_stats = gdf.copy().reset_index(drop=True)
        gdf_stats["estado"]    = estado
        gdf_stats["area_ha"]   = gdf_stats["area_calc_ha"]  # substitui area_calc_ha
        gdf_stats["cnt_pix"]   = stats_df["count"].round(1) # substitui count_pixels
        gdf_stats["mean"]      = (stats_df["mean"] * FATOR_C_CO2).round(2)
        gdf_stats["min"]       = (stats_df["min"]  * FATOR_C_CO2).round(2)
        gdf_stats["max"]       = (stats_df["max"]  * FATOR_C_CO2).round(2)
        gdf_stats["sum_bruta"] = (stats_df["sum"]  * FATOR_C_CO2).round(2)
        gdf_stats["sum_conv"]  = (stats_df["sum"]  * FATOR_C_CO2 * AREA_PIXEL_HA).round(2)  # substitui sum_convertida

        # Remove colunas com nomes longos que vieram do shapefile original
        gdf_stats = gdf_stats.drop(columns=["area_calc_ha"], errors="ignore")

        geodataframes.append(gdf_stats)

        print(f"  ✔ {estado}: {len(df)} linhas")

    except Exception as e:
        print(f"  ⚠ {estado} pulado: {e}")

# ── SAÍDAS ────────────────────────────────────────────────
if resultados:
    df_final = pd.concat(resultados, ignore_index=True)
    df_final.to_excel(SAIDA, index=False)
    print(f"\nExcel salvo: {len(df_final)} linhas → {SAIDA}")

if geodataframes:
    gdf_final = pd.concat(geodataframes, ignore_index=True)
    gdf_final = gpd.GeoDataFrame(gdf_final, geometry="geometry", crs="EPSG:4326")
    gdf_final.to_file(SAIDA_SHP, encoding="utf-8")
    print(f"Shapefile salvo: {len(gdf_final)} feições → {SAIDA_SHP}")

if not resultados:
    print("\nNenhum dado processado com sucesso.")