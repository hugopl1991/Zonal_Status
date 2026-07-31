import geopandas as gpd
import pandas as pd
import rasterio
from exactextract import exact_extract

# ── CONFIGURE AQUI ────────────────────────────────────────
ANOS    = range(2008, 2026)
ESTADOS = ["PA", "MA"]

SHAPEFILE    = r"C:\Users\lima-\Downloads\Suprimidas\Dados\PRODES\Amazonia\PRODES_2008_2025\desmatamento_res_bio.shp"
PASTA_RASTER = r"C:\Users\lima-\Downloads\Suprimidas\Dados\TAGB_BGB_Estoque"
SAIDA        = r"C:\Users\lima-\Downloads\Suprimidas\amazonia_2010_2025_res_bio.xlsx"
SAIDA_SHP    = r"C:\Users\lima-\Downloads\Suprimidas\amazonia_2010_2025_res_bio.shp"
# ──────────────────────────────────────────────────────────

FATOR_C_CO2   = 3.67
AREA_PIXEL_HA = 0.09

print("Carregando shapefile...")
gdf_total = gpd.read_file(SHAPEFILE)
gdf_total["feat_id"] = range(len(gdf_total))  # ID único por feição

# Calcula área real em hectares
gdf_total = gdf_total.to_crs("EPSG:5880")
gdf_total["area_calc_ha"] = (gdf_total.geometry.area / 10000).round(4)
gdf_total = gdf_total.to_crs("EPSG:4326")

resultados = []

for estado in ESTADOS:
    gdf_estado = gdf_total[gdf_total["state"] == estado]

    for ano in ANOS:
        gdf = gdf_estado[gdf_estado["year"] == ano].copy()

        if len(gdf) == 0:
            print(f"  ⚠ {estado} / {ano}: nenhuma feição, pulando...")
            continue

        raster = rf"{PASTA_RASTER}\{estado}_1985-2025\raster_TAGB_BGB_MgCha_{estado}_{ano}.tif"
        print(f"  Processando {estado} / {ano} ({len(gdf)} feições)...")

        try:
            with rasterio.open(raster) as src:
                raster_crs = src.crs

            gdf_reproj = gdf.to_crs(raster_crs)

            resultado = exact_extract(
                raster, gdf_reproj,
                ["count", "sum", "mean", "min", "max"],
                output="pandas"
            ).reset_index(drop=True)

            df = gdf.drop(columns="geometry").reset_index(drop=True)
            df = df.drop(columns=["Shape_Leng", "Shape_Area"], errors="ignore")

            df["cnt_pix"]   = resultado["count"].round(1)
            df["mean"]      = (resultado["mean"] * FATOR_C_CO2).round(2)
            df["min"]       = (resultado["min"]  * FATOR_C_CO2).round(2)
            df["max"]       = (resultado["max"]  * FATOR_C_CO2).round(2)
            df["sum_bruta"] = (resultado["sum"]  * FATOR_C_CO2).round(2)
            df["sum_conv"]  = (resultado["sum"]  * AREA_PIXEL_HA * FATOR_C_CO2).round(2)

            resultados.append(df)
            print(f"  ✔ {estado} / {ano}: ok")

        except Exception as e:
            print(f"  ⚠ {estado} / {ano} pulado: {e}")

if resultados:
    df_final = pd.concat(resultados, ignore_index=True)

    # Salva Excel
    df_final.to_excel(SAIDA, index=False)
    print(f"Excel salvo: {len(df_final)} linhas")

    # Reanexa geometria pelo feat_id (1-para-1, sem multiplicar feições)
    gdf_geom = gdf_total[["feat_id", "geometry"]].copy()
    gdf_resultado = df_final.merge(gdf_geom, on="feat_id", how="left")
    gdf_resultado = gpd.GeoDataFrame(gdf_resultado, geometry="geometry", crs="EPSG:4326")
    gdf_resultado = gdf_resultado.drop(columns=["feat_id"])

    gdf_resultado.to_file(SAIDA_SHP, encoding="utf-8")
    print(f"Shapefile salvo: {len(gdf_resultado)} feições")

else:
    print("\nNenhum dado processado com sucesso.")