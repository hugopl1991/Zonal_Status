"""
Análise Zonal Estatística – Estoque de Carbono (Vale)
======================================================
Script unificado para Biomassa (TAGB_BGB) e Solo (Csoil), anos 2024 e 2025.

Pipeline por produto × ano:
  1. Para cada estado, abre o(s) shapefile(s) de áreas suprimidas.
  2. Calcula área em hectares (EPSG:5880).
  3. Extrai estatísticas zonais (count, sum, mean, min, max) do raster
     de estoque de carbono (MgC/ha) via exactextract.
  4. Converte valores de C para CO₂e (× 3,67) e calcula totais absolutos
     multiplicando pela área do pixel (0,09 ha).
  5. Salva Excel + Shapefile por produto/ano.
  6. Grava log de auditoria em arquivo .log na pasta raiz.

Uso:
    python Zonal_shp.py
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
from exactextract import exact_extract

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ════════════════════════════════════════════════════════════════════════════

FATOR_C_CO2   = 3.67   # MgC → MgCO₂e
AREA_PIXEL_HA = 0.09   # área de cada pixel em hectares (300 m × 300 m)
CRS_AREA      = "EPSG:5880"  # Albers — para cálculo de área
CRS_SAIDA     = "EPSG:4326"  # WGS-84 — para saída

ESTADOS = ["MA", "PA", "MG", "ES"]
#ESTADOS = ["MA", "PA", "MG", "RJ", "ES", "BA", "SP"]

# Colunas do shapefile original que não devem ir para as saídas
COLUNAS_EXCLUIR = ["Shape_Leng", "Shape_Area"]

DIR_RAIZ = Path(r"C:\Users\lima-\Downloads\Suprimidas")

# ════════════════════════════════════════════════════════════════════════════
# LOG DE AUDITORIA
# ════════════════════════════════════════════════════════════════════════════

def configurar_log() -> logging.Logger:
    """Configura logger que grava simultaneamente no console e em arquivo .log."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_log = DIR_RAIZ / f"zonal_log_{ts}.log"

    logger = logging.getLogger("zonal")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(arquivo_log, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    logger.info(f"Log iniciado → {arquivo_log}")
    return logger

log = configurar_log()

# ════════════════════════════════════════════════════════════════════════════
# CATÁLOGO DE PRODUTOS (rasters de carbono)
# ════════════════════════════════════════════════════════════════════════════

PRODUTOS = {
    "bio": {
        "descricao":    "Biomassa (TAGB + BGB)",
        "pasta_raster": DIR_RAIZ / "Dados" / "TAGB_BGB_Estoque",
        "subpasta":     "{estado}_TAGB_BGB_1985-2025",
        "arquivo":      "raster_TAGB_BGB_MgCha_{estado}_{ano}.tif",
    },
    "solo": {
        "descricao":    "Carbono do Solo (Csoil)",
        "pasta_raster": DIR_RAIZ / "Dados" / "Csoil_Estoque",
        "subpasta":     "{estado}_Csoil_1985-2025",
        "arquivo":      "raster_Csoil_MgCha_{estado}_{ano}.tif",
    },
}

# ════════════════════════════════════════════════════════════════════════════
# CATÁLOGO DE ANOS / SHAPEFILES
# ════════════════════════════════════════════════════════════════════════════

CONFIGS_ANO = {
    "2024": {
        "pasta_shape": DIR_RAIZ / "Dados" / "Suprimidas" / "2024",
        "semestres": [
            ("", "sup24_v12_{estado}.shp"),
        ],
    },
    "2025": {
        "pasta_shape": DIR_RAIZ / "Dados" / "Suprimidas" / "2025",
        "semestres": [
            ("1sem", "supressão por estado 1sem/supressão por estado/sup_1sem_{estado}.shp"),
            ("2sem", "Sup_2sem_UF 14012026/Sup_2sem_UF 14012026/sup_2sem_{estado}_nat_wgs84_dis.shp"),
            ("2sem", "Sup_2sem_UF 14012026/Sup_2sem_UF 14012026/sup_2sem_{estado}_nat_wgs84_dis_qgis.shp"),
            ("2sem", "Sup_2sem_UF 14012026/Sup_2sem_UF 14012026/sup_2sem_{estado}_exo_wgs84_dis.shp"),
        ],
    },
}

# ════════════════════════════════════════════════════════════════════════════
# ETAPAS DO PIPELINE
# ════════════════════════════════════════════════════════════════════════════

def etapa_preparar(caminho_shp: str) -> gpd.GeoDataFrame:
    """
    Lê shapefile, calcula área em hectares (Albers) e retorna em WGS-84.
    Não adiciona feat_id — o índice posicional é suficiente internamente.
    """
    gdf = gpd.read_file(caminho_shp)
    gdf = gdf.to_crs(CRS_AREA)
    gdf["area_c_ha"] = (gdf.geometry.area / 10_000).round(4)
    gdf = gdf.to_crs(CRS_SAIDA)
    return gdf

def etapa_extrair(caminho_raster: str, gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Extrai estatísticas zonais do raster para cada feição do GeoDataFrame.
    Reprojecta temporariamente para o CRS do raster antes da extração.
    """
    with rasterio.open(caminho_raster) as src:
        raster_crs = src.crs

    stats = exact_extract(
        caminho_raster,
        gdf.to_crs(raster_crs),
        ["count", "sum", "mean", "min", "max"],
        output="pandas",
    ).reset_index(drop=True)

    return stats

def etapa_enriquecer(gdf: gpd.GeoDataFrame, stats: pd.DataFrame, produto: str) -> pd.DataFrame:
    """
    Monta o DataFrame tabular (sem geometria) com colunas de carbono convertidas
    para MgCO₂e. Não inclui feat_id.
    """
    df = (
        gdf
        .drop(columns="geometry")
        .drop(columns=COLUNAS_EXCLUIR, errors="ignore")
        .reset_index(drop=True)
    )

    df["produto"]        = produto
    df["cnt_pix"]        = stats["count"].round(1)
    df["mean_MgCO2e_ha"] = (stats["mean"] * FATOR_C_CO2).round(2)
    df["min_MgCO2e_ha"]  = (stats["min"]  * FATOR_C_CO2).round(2)
    df["max_MgCO2e_ha"]  = (stats["max"]  * FATOR_C_CO2).round(2)
    df["sum_MgCO2e_ha"]  = (stats["sum"]  * FATOR_C_CO2).round(2)            # por pixel
    df["sum_MgCO2e"]     = (stats["sum"]  * FATOR_C_CO2 * AREA_PIXEL_HA).round(2)  # total absoluto

    return df

def etapa_normalizar_2025(obj):
    """
    Harmoniza nomes de colunas específicos do 2025 em qualquer DataFrame
    ou GeoDataFrame:  ID_1 → ID    |    SUM_area_h → area_ha
    Modifica o objeto in-place e também o retorna.
    """
    # Unifica ID
    if "ID" not in obj.columns and "ID_1" in obj.columns:
        obj.insert(0, "ID", obj.pop("ID_1"))
    elif "ID" in obj.columns and "ID_1" in obj.columns:
        obj["ID"] = obj["ID"].fillna(obj.pop("ID_1"))

    # Unifica area_ha
    if "area_ha" not in obj.columns and "SUM_area_h" in obj.columns:
        obj.insert(0, "area_ha", obj.pop("SUM_area_h"))
    elif "area_ha" in obj.columns and "SUM_area_h" in obj.columns:
        obj["area_ha"] = obj["area_ha"].fillna(obj.pop("SUM_area_h"))

    return obj

def etapa_salvar(
    tabelas: list[pd.DataFrame],
    geodataframes: list[gpd.GeoDataFrame],
    saida_xlsx: Path,
    saida_shp: Path,
) -> bool:
    """
    Consolida e grava os resultados em Excel e Shapefile.
    Nenhuma coluna feat_id é incluída nos arquivos de saída.
    """
    sucesso = False

    if tabelas:
        pd.concat(tabelas, ignore_index=True).to_excel(str(saida_xlsx), index=False)
        log.info(f"Excel salvo → {saida_xlsx.name}")
        sucesso = True

    if geodataframes:
        gdf_final = gpd.GeoDataFrame(
            pd.concat(geodataframes, ignore_index=True),
            geometry="geometry",
            crs=CRS_SAIDA,
        )
        gdf_final.to_file(str(saida_shp), encoding="utf-8")
        log.info(f"Shapefile salvo → {saida_shp.name}  ({len(gdf_final)} feições)")
        sucesso = True

    if not sucesso:
        log.warning("Nenhum dado processado com sucesso.")

    return sucesso

# ════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR
# ════════════════════════════════════════════════════════════════════════════

def processar(ano: str, config_ano: dict, produto_key: str, produto_cfg: dict) -> bool:
    """
    Executa o pipeline completo para um produto × ano.
    Itera sobre semestres e estados, acumulando resultados antes de salvar.
    """
    tabelas       = []
    geodataframes = []

    for semestre, padrao in config_ano["semestres"]:
        for estado in ESTADOS:
            lbl = f"{estado} {semestre}".strip()

            caminho_shp = str(config_ano["pasta_shape"] / padrao.format(estado=estado))
            caminho_ras = str(
                produto_cfg["pasta_raster"]
                / produto_cfg["subpasta"].format(estado=estado)
                / produto_cfg["arquivo"].format(estado=estado, ano=ano)
            )

            try:
                gdf   = etapa_preparar(caminho_shp)
                stats = etapa_extrair(caminho_ras, gdf)

                df = etapa_enriquecer(gdf, stats, produto_key)

                if ano == "2025":
                    df = etapa_normalizar_2025(df)

                # Adiciona identificadores de contexto
                df["estado"]   = estado
                df["semestre"] = semestre
                df["ano"]      = ano
                tabelas.append(df)

                # GeoDataFrame para o shapefile de saída (sem feat_id)
                gdf_out = gdf.drop(columns=COLUNAS_EXCLUIR, errors="ignore").reset_index(drop=True)
                if ano == "2025":
                    etapa_normalizar_2025(gdf_out)

                gdf_out["produto"]  = produto_key
                gdf_out["estado"]   = estado
                gdf_out["semestre"] = semestre
                gdf_out["ano"]      = ano
                gdf_out["area_c_ha"]  = gdf["area_c_ha"]
                gdf_out["cnt_pix"]  = stats["count"].round(1)
                gdf_out["mean"]     = (stats["mean"] * FATOR_C_CO2).round(2)
                gdf_out["min"]      = (stats["min"]  * FATOR_C_CO2).round(2)
                gdf_out["max"]      = (stats["max"]  * FATOR_C_CO2).round(2)
                gdf_out["sum_bruta"]   = (stats["sum"]  * FATOR_C_CO2).round(2)
                gdf_out["sum_conv"]  = (stats["sum"]  * FATOR_C_CO2 * AREA_PIXEL_HA).round(2)
                geodataframes.append(gdf_out)

                log.info(f"✔ {lbl}")

            except Exception as exc:
                log.warning(f"✗ {lbl}: {exc}")
                log.debug(traceback.format_exc())

    return etapa_salvar(
        tabelas, geodataframes,
        DIR_RAIZ / f"resultado_{produto_key}_{ano}.xlsx",
        DIR_RAIZ / f"resultado_{produto_key}_{ano}.shp",
    )

# ════════════════════════════════════════════════════════════════════════════
# ENTRADA DO SCRIPT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    log.info("=" * 60)
    log.info("MASTER – ANÁLISE ZONAL ESTATÍSTICA (VALE)")
    log.info("Biomassa + Solo  |  2024 + 2025")
    log.info("=" * 60)

    sucessos = falhas = 0
    total = len(PRODUTOS) * len(CONFIGS_ANO)

    for produto_key, produto_cfg in PRODUTOS.items():
        for ano, config_ano in CONFIGS_ANO.items():
            log.info(f"▶  {produto_cfg['descricao']}  |  Ano: {ano}")

            ok = processar(ano, config_ano, produto_key, produto_cfg)

            if ok:
                log.info(f"CONCLUÍDO: {produto_key.upper()} {ano}")
                sucessos += 1
            else:
                log.error(f"FALHA: {produto_key.upper()} {ano}")
                falhas += 1

    log.info("=" * 60)
    log.info("RELATÓRIO FINAL")
    log.info(f"Sucessos : {sucessos}  |  Falhas : {falhas}  |  Total : {total}")
    if falhas == 0:
        log.info("TODOS OS PROCESSAMENTOS CONCLUÍDOS COM SUCESSO!")
    else:
        log.warning(f"{falhas} processamento(s) com falha — revise o log acima.")