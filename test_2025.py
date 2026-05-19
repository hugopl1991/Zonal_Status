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
ANO = "2025"
ESTADOS = ["MA", "PA", "MG", "RJ", "ES", "BA", "SP"]

PASTA_RASTER = r"C:\Users\lima-\Downloads\Suprimidas\Estoque_solo\Csoil_Estoque"
PASTA_SHAPE  = r"C:\Users\lima-\Downloads\Suprimidas\Suprimidas\2025"
SAIDA        = r"C:\Users\lima-\Downloads\Suprimidas\resultado_2025.xlsx"
# ──────────────────────────────────────────────────────────

FATOR_C_CO2 = 3.67

SEMESTRES = [
    ("1sem", r"supressão por estado 1sem\supressão por estado\sup_1sem_{estado}.shp"),
    ("2sem", r"Sup_2sem_UF 14012026\Sup_2sem_UF 14012026\sup_2sem_{estado}_nat_wgs84_dis.shp"),
    ("2sem", r"Sup_2sem_UF 14012026\Sup_2sem_UF 14012026\sup_2sem_{estado}_nat_wgs84_dis_qgis.shp"),
    ("2sem", r"Sup_2sem_UF 14012026\Sup_2sem_UF 14012026\sup_2sem_{estado}_exo_wgs84_dis.shp"),
]

COLUNAS_REMOVER = ["Shape_Leng", "Shape_Area"]

resultados = []

for semestre, padrao in SEMESTRES:
    for estado in ESTADOS:
        raster    = rf"{PASTA_RASTER}\{estado}_Csoil_1985-2025\raster_Csoil_MgCha_{estado}_{ANO}.tif"
        shapefile = rf"{PASTA_SHAPE}\{padrao.format(estado=estado)}"

        print(f"Processando {estado} - {semestre} ({padrao})...")

        try:
            gdf = gpd.read_file(shapefile)
            raw = zonal_stats(gdf, raster, stats=["count", "sum", "mean", "min", "max"])

            df = gdf.drop(columns="geometry")

            # Padroniza coluna ID
            if "ID" not in df.columns and "ID_1" in df.columns:
                df.insert(0, "ID", df["ID_1"])
                df = df.drop(columns="ID_1")
            elif "ID" in df.columns and "ID_1" in df.columns:
                df["ID"] = df["ID"].fillna(df["ID_1"])
                df = df.drop(columns="ID_1")

            # Padroniza coluna area_ha
            if "area_ha" not in df.columns and "SUM_area_h" in df.columns:
                df.insert(0, "area_ha", df["SUM_area_h"])
                df = df.drop(columns="SUM_area_h")
            elif "area_ha" in df.columns and "SUM_area_h" in df.columns:
                df["area_ha"] = df["area_ha"].fillna(df["SUM_area_h"])
                df = df.drop(columns="SUM_area_h")

            # Remove colunas indesejadas
            df = df.drop(columns=[c for c in COLUNAS_REMOVER if c in df.columns])

            stats_df = pd.DataFrame(raw)

            df["estado"]         = estado
            df["semestre"]       = semestre
            df["pixels"]         = stats_df["count"]
            df["mean_MgCO2e_ha"] = (stats_df["mean"] * FATOR_C_CO2).round(2)
            df["min_MgCO2e_ha"]  = (stats_df["min"]  * FATOR_C_CO2).round(2)
            df["max_MgCO2e_ha"]  = (stats_df["max"]  * FATOR_C_CO2).round(2)
            df["sum_MgCO2e_ha"]  = (stats_df["sum"]  * FATOR_C_CO2).round(2)

            resultados.append(df)
            print(f"  ✔ {estado} {semestre}: {len(df)} linhas")

        except Exception as e:
            print(f"  ⚠ {estado} {semestre} pulado: {e}")

# Junta tudo e salva
if resultados:
    df_final = pd.concat(resultados, ignore_index=True)
    df_final.to_excel(SAIDA, index=False)
    print(f"\nPronto! {len(df_final)} linhas totais salvas em '{SAIDA}'")
else:
    print("\nNenhum estado processado com sucesso.")