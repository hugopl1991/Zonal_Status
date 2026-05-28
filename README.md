# Análise Zonal de Estoque de Carbono

Calcula estatísticas zonais de rasters de estoque de carbono sobre áreas suprimidas, convertendo MgC/ha para MgCO2e.

## Instalação

```bash
pip install geopandas rasterio rasterstats pandas openpyxl
```

## Como usar

1. Edite os caminhos no topo do script (`PASTA_RASTER`, `PASTA_SHAPE`, `SAIDA`)
2. Execute:

```bash
python zonal_carbono_2024.py  # ano completo
python zonal_carbono_2025.py  # 1º e 2º semestre
```

Estados com arquivos ausentes são pulados automaticamente.

## Saída

Arquivo `.xlsx` com uma linha por feição e as colunas `estado`, `area_ha`, `pixels`, `mean_MgCO2e_ha`, `min_MgCO2e_ha`, `max_MgCO2e_ha` e `sum_MgCO2e_ha`.

> Conversão aplicada: MgC × 3,67 = MgCO2e

---

## Observações

- O script reprojeita automaticamente o shapefile para o CRS do raster se forem diferentes
- Colunas `Shape_Leng` e `Shape_Area` são removidas automaticamente
- A coluna `ID_1` é renomeada para `ID` quando necessário (shapefiles do 2º semestre)
