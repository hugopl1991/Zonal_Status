import geopandas as gpd

# Caminhos dos shapefiles
shp_desmatamento = r"C:\Users\lima-\Downloads\Suprimidas\Dados\PRODES\Mata\prodes_biome_mata_atlantica_v20260330_acc.shp"
shp_mascara = r"C:\Users\lima-\Downloads\Dados_Hugo\Shape\Compilado.shp"

# Ler os arquivos
desmat = gpd.read_file(shp_desmatamento)
mascara = gpd.read_file(shp_mascara)

# Garantir que estão no mesmo CRS
if desmat.crs != mascara.crs:
    mascara = mascara.to_crs(desmat.crs)

# Fazer o recorte (clip)
desmat_recortado = gpd.clip(desmat, mascara)

# Salvar o resultado
saida = r"C:\Users\lima-\Downloads\Suprimidas\Dados\PRODES\Mata\desmatamento_recortado_acc.shp"
desmat_recortado.to_file(saida)

print("Recorte concluído! Arquivo salvo em:", saida)