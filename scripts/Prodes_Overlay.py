""" 
Automatização de todos os processamentos de desmatamento (Via Docker e config.yaml).
Saída consolidada em GeoPackages por Bioma. 
Inclui cálculo da área original do PRODES (area_p_ha) e da área recortada (area_c_ha). 
"""

import os 
import sys 
import yaml 
import logging 
from datetime import datetime 
from pathlib import Path 
import geopandas as gpd 
import pandas as pd 
import rasterio 
from exactextract import exact_extract 

# Carregamento das configurações globais e definições
with open("config.yaml", "r", encoding="utf-8") as f: # Abre o arquivo 'config.yaml'
    CFG = yaml.safe_load(f) 

DIR_RAIZ = Path(os.environ.get("DIR_RAIZ", CFG["global"]["dir_raiz"])) # Define o diretório de trabalho base, priorizando a variável de ambiente, senão utiliza o valor do YAML
FATOR_C_CO2 = CFG["global"]["fator_c_co2"] # Extrai a constante de conversão de Carbono para Dióxido de Carbono Equivalente (CO2e) do YAML
AREA_PIXEL_HA = CFG["global"]["area_pixel_ha"] # Extrai a área predefinida de cada pixel do raster (em hectares)
CRS_AREA = CFG["global"]["crs_area"] # Extrai o Sistema de Referência de Coordenadas (CRS) apropriado para cálculos precisos de área (ex: EPSG:5880)
CRS_SAIDA = CFG["global"]["crs_saida"] # Extrai o Sistema de Referência de Coordenadas em que os dados finais serão salvos (ex: EPSG:4326)
C_DECIMAIS = CFG["global"]["c_decimais"] # Quantidade de casa decimais usadas no arrendodamento.

ESTADOS = CFG["prodes"]["estados"] # Lê a lista de estados da federação a serem iterados dentro das chaves do PRODES
SHP_MASCARA = Path(CFG["prodes"]["shp_mascara"]) # Define o caminho do shapefile usado como máscara de recorte como um objeto Path
GPKG_AMAZONIA = DIR_RAIZ / CFG["prodes"]["gpkg_amazonia"] # Constrói de forma segura o caminho para o banco de dados da Amazônia concatenando com a raiz
GPKG_MATA = DIR_RAIZ / CFG["prodes"]["gpkg_mata"] # Constrói de forma segura o caminho para o banco de dados da Mata Atlântica concatenando com a raiz
PRODUTOS = CFG["produtos"] # Armazena os subprodutos disponíveis que estão definidos dentro do arquivo de configuração YAML
STATE = CFG["prodes"]["state_gpkg"] # Padrão usado na tabela de atributos do PRODES
YEAR = CFG["prodes"]["year_gpkg"] # Padrão usado na tabela de atributos do PRODES 

CAMINHO_CSV_PROC = CFG["prodes"]["processamentos_csv"] # Constrói o caminho completo para o CSV
df_processamentos = pd.read_csv(CAMINHO_CSV_PROC, sep=",") # Lê o CSV usando o pandas

PROCESSAMENTOS = {} 

# Itera sobre as linhas do CSV e traduz as regras
for index, row in df_processamentos.iterrows():
    # Remove valores nulos (NaN) da linha para simular o comportamento do YAML
    cfg = row.dropna().to_dict()
    # Extrai a 'chave' (ex: anual_bio) e a remove do dicionário de configuração
    chave = cfg.pop("chave")
    # Garante que os anos sejam números inteiros (o pandas pode lê-los como float por causa das células vazias)
    if "ano_inicio" in cfg: cfg["ano_inicio"] = int(cfg["ano_inicio"])
    if "ano_fim" in cfg: cfg["ano_fim"] = int(cfg["ano_fim"])
    if "ano_raster" in cfg: cfg["ano_raster"] = int(cfg["ano_raster"])
    # Reconstrói o objeto range() nativo do Python se for do tipo anual.
    # IMPORTANTE: no processamentos.csv, "ano_fim" representa o ÚLTIMO ANO A SER
    # PROCESSADO (inclusive) — não o limite exclusivo que range() espera.
    # Por isso somamos +1 aqui dentro do script, e não pedimos para quem
    # edita o CSV lembrar de escrever um ano a mais manualmente.
    if cfg["tipo"] == "anual":
        cfg["anos"] = range(cfg["ano_inicio"], cfg["ano_fim"] + 1)
        cfg["saida_base"] = f"{cfg['saida_base']}_{cfg['ano_inicio']}_{cfg['ano_fim']}"
    elif cfg["tipo"] == "acumulado":
        cfg["saida_base"] = f"{cfg['saida_base']}_{cfg['ano_raster']}"    
    # Injeta a variável global da máscara
    cfg["shp_mascara"] = SHP_MASCARA
    # Substitui o texto pelo respectivo objeto Path configurado no script
    if cfg["gpkg"] == "amazonia":
        cfg["gpkg"] = GPKG_AMAZONIA
    elif cfg["gpkg"] == "mata":
        cfg["gpkg"] = GPKG_MATA   
    # Guarda as configurações processadas no dicionário principal
    PROCESSAMENTOS[chave] = cfg


def configurar_log() -> logging.Logger:
    """
    Configura e inicializa o rastreador de log para o sistema.
    
    Entrada:
        Nenhuma.
        
    Saída:
        Retorna a instância configurada do objeto logger da biblioteca de logging.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S") # Gera uma string de texto (timestamp) formatada com ano, mês, dia, hora, minuto e segundo
    logger = logging.getLogger("prodes") # Inicializa e nomeia um objeto logger como 'prodes'
    logger.setLevel(logging.DEBUG) # Configura a severidade mínima que será registrada (tudo de DEBUG para cima será gravado)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S") # Prepara um formato estruturado padronizado para a escrita das mensagens do log

    for handler in [logging.FileHandler(DIR_RAIZ / f"prodes_log_{ts}.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)]: # Inicia um laço configurando a gravação física (arquivo txt) e ao mesmo tempo a exibição no terminal (stdout)
        handler.setFormatter(fmt) # Associa o formatador (criado acima) à atual saída iterada no loop
        logger.addHandler(handler) # Acopla esse manipulador recém-configurado à instância principal do logger
    return logger # Retorna o objeto logger pronto para ser invocado pelo resto do script
log = configurar_log()

def etapa_overlay_preparar(config: dict) -> gpd.GeoDataFrame:
    """
    Prepara os dados de entrada recortando a camada por uma máscara e gerando as áreas.
    
    Entrada:
        config: Dicionário contendo os metadados do processamento de uma camada específica.
        
    Saída:
        Retorna um GeoDataFrame manipulado e convertido para o CRS de saída.
    """
    log.info(f"Carregando camada '{config['layer']}'...") 
    gdf = gpd.read_file(str(config["gpkg"]), layer=config["layer"])

    # Calcula área original de cada feição PRODES (antes do overlay)
    log.info("Calculando area_p_ha (area original do PRODES — EPSG:5880)...") 
    try: 
        gdf["area_p_ha"] = (gdf.to_crs(CRS_AREA).geometry.area / 10_000).round(C_DECIMAIS) # Reprojeta o vetor ao CRS métrico, calcula a área e divide por 10 mil (para transformar metros quadrados para hectares), arredondando para duas casas
    except Exception as e: 
        log.warning(f"Erro ao calcular area_p_ha: {e}") 
        gdf["area_p_ha"] = None 
    log.info("Carregando máscara e realizando interseção espacial (overlay)...")
    mascara = gpd.read_file(str(config["shp_mascara"])).to_crs(gdf.crs)
    
    # Realiza a interseção: recorta pela máscara E herda todos os atributos dela
    gdf = gpd.overlay(gdf, mascara, how='intersection').to_crs(CRS_AREA)
    
    # Calcula a área final recortada # Comentário explicitando a próxima ação matemática (área do pós-recorte)
    log.info("Calculando area_c_ha (área recortada — EPSG:5880)...") 
    gdf["area_c_ha"] = (gdf.geometry.area / 10_000).round(C_DECIMAIS) # A partir do objeto reprojetado, calcula novamente a área base (m²), transforma para Hectares e mantém até dois decimais

    return gdf.to_crs(CRS_SAIDA)

def extrair_raster(gdf_subset: gpd.GeoDataFrame, caminho: Path) -> gpd.GeoDataFrame:
    """
    Extrai as estatísticas zonais cruzando a geometria do subset com um raster específico.
    
    Entrada:
        gdf_subset: GeoDataFrame do subconjunto filtrado.
        caminho: Caminho do arquivo raster de onde os dados serão extraídos.
        
    Saída:
        Retorna o GeoDataFrame do subconjunto alimentado com os cálculos do raster (mean, max, sum, etc.).
    """
    with rasterio.open(caminho) as src: # Cria um gerenciador de contexto do Python que abrirá a imagem (tif) e garantirá seu fechamento de memória em seguida
        stats = exact_extract(str(caminho), gdf_subset.to_crs(src.crs), ["count", "sum", "mean", "min", "max"], output="pandas") # Usando C/C++ por baixo, extrai em um pd.DataFrame contagem, soma, mínima e máxima, enquanto faz o ajuste do CRS do recorte para ficar alinhado à imagem

    gdf_res = gdf_subset.drop(columns=["Shape_Leng", "Shape_Area"], errors="ignore").reset_index(drop=True) # Remove colunas de área em inglês vindas do shape e reseta todos os index do recorte para sequencial (0, 1, 2)

    return gdf_res.assign( # Devolve os dados, injetando instantaneamente as colunas retornadas pela lib externa do raster e manipulando cada uma delas no ato
        cnt_pix=stats["count"].round(C_DECIMAIS), 
        mean=(stats["mean"] * FATOR_C_CO2).round(C_DECIMAIS), 
        min=(stats["min"] * FATOR_C_CO2).round(C_DECIMAIS),
        max=(stats["max"] * FATOR_C_CO2).round(C_DECIMAIS), 
        sum_bruta=(stats["sum"] * FATOR_C_CO2).round(C_DECIMAIS), 
        sum_conv=(stats["sum"] * AREA_PIXEL_HA * FATOR_C_CO2).round(C_DECIMAIS) 
    ) 

def processar_dataset(config: dict, produtos_ativos: dict) -> dict[str, bool]: 
    """
    Orquestra o loop principal de processamento mascarando, extraindo valores e salvando a saída.
    
    Entrada:
        config: Dicionário contendo os dados de iteração da região de interesse.
        produtos_ativos: Produtos listados no catálogo para terem os recortes avaliados.
        
    Saída:
        Retorna um dicionário iterável avaliando o sucesso booleano (True/False) de gravação de cada layer.
    """
    resultados_prod = {k: False for k in produtos_ativos} 
    try: 
        gdf = etapa_overlay_preparar(config) # Executa o processo de mascaramento e cálculo estrito dos limites geográficos da entrada
    except Exception: 
        log.error("Falha no overlay.") 
        return resultados_prod 

    if "amazonia" in config["saida_base"].lower(): # Verifica na configuração para saber de qual banco ele vai despejar resultados
        gpkg_saida = DIR_RAIZ / "resultados_amazonia.gpkg" # Monta como saída base o banco do desmatamento da região Norte
    else: 
        gpkg_saida = DIR_RAIZ / "resultados_mata_atlantica.gpkg" # Monta o banco base correspondente ao bioma

    for prod_key, prod_cfg in produtos_ativos.items(): # Inicia a varredura percorrendo chaves ("biomassa") e o dicionário de suas particularidades atreladas
        log.info(f"Extraindo zonas para: {prod_cfg['descricao']}") 
        resultados = [] # Prepara uma lista provisória

        anos_iter = config["anos"] if config["tipo"] == "anual" else [config["ano_raster"]] # Regra ternária que analisa se o processamemto

        for estado in ESTADOS: 
            for ano in anos_iter: 
                filtro = (gdf[STATE] == estado) & (gdf[YEAR] == ano) if config["tipo"] == "anual" else (gdf[STATE] == estado) # Cria a condição (o filtro booleano) dinamicamente baseando-se no cruzamento da lógica com os dados na memória
                gdf_subset = gdf[filtro].copy() # Executa fisicamente um recorte limpo na base filtrando aquilo estipulado

                if not gdf_subset.empty: # Início da verificação
                    # NOVA LÓGICA: Se anual, usa raster do ano anterior. Se acumulado, usa o ano fixo.
                    ano_raster = ano if config["tipo"] == "anual" else ano
                    
                    # Passa a variável 'ano_raster' para interpolar no nome do arquivo TIF
                    caminho = DIR_RAIZ / prod_cfg["dir_raster"] / prod_cfg["subpasta"].format(estado=estado) / prod_cfg["arquivo"].format(estado=estado, ano=ano_raster) 
                    
                    # Empacotando os argumentos
                    args_extracao = {
                        "gdf_subset": gdf_subset,
                        "caminho": caminho
                    }
                    
                    try: # Controle de risco para leitura do TIF formatado acima, que pode faltar
                        # Desempacotando na chamada
                        resultados.append(extrair_raster(**args_extracao)) 
                        log.info(f"[{estado}/PRODES:{ano}->RASTER:{ano_raster}] ✔") 
                    except Exception as e: 
                        log.warning(f"[{estado}/PRODES:{ano}->RASTER:{ano_raster}] ✗ {e}") 

        if resultados: # Ao fim dos laços for do estado e do ano. Existindo qualquer resultado gravado na lista provisória...
            gdf_out = gpd.GeoDataFrame(pd.concat(resultados, ignore_index=True), crs=CRS_SAIDA) # Empacota tudo de volta
            nome_camada = f"{config['saida_base']}_{prod_key}" # Forja e estipula o nome definitivo para a aba (layer) usando a combinação da base do prodes com a tag do produto

            # Salva Excel (sem a coluna de geometria) 
            gdf_out.drop(columns="geometry").rename(columns={ # Deleta em momento de escrita a coluna geometry que atrapalharia as planilhas; abre a regra para renomear textos de cabeçalho
                "mean": "mean_MgCO2e_ha", "min": "min_MgCO2e_ha", # Substitui as variáveis básicas originais geradas pelo pacote Zonal por explicações padronizadas
                "max": "max_MgCO2e_ha", "sum_bruta": "sum_MgCO2e_ha", "sum_conv": "sum_MgCO2e" # Substitui as variáveis de máxima e sumário para o modelo métrico explicativo do projeto
            }).to_excel(DIR_RAIZ / f"{nome_camada}.xlsx", index=False) # Roda a biblioteca openpyxl internamente para chutar as alterações descritas acima em formato .xlsx limpo (sem index sujo)

            # Salva como nova camada (layer) no GeoPackage consolidado 
            gdf_out.to_file(gpkg_saida, layer=nome_camada, driver="GPKG")  

            resultados_prod[prod_key] = True # Se chegou na linha de baixo e gravou tudo nos HDs, ele registra Sucesso absoluto naquele item do catálogo de produtos avaliados
            log.info(f"Salvo no GPKG -> Layer: {nome_camada}") 
    return resultados_prod

if __name__ == "__main__":
    processos = {sys.argv[1]: PROCESSAMENTOS[sys.argv[1]]} if len(sys.argv) >= 2 else PROCESSAMENTOS 
    produtos = {sys.argv[2]: PRODUTOS[sys.argv[2]]} if len(sys.argv) >= 3 else PRODUTOS 

    log.info("MASTER – AUTOMATIZAÇÃO DE DESMATAMENTO (PRODES)") 
    sucessos = falhas = 0 

    for chave, config in processos.items():     
        args_dataset = {
            "config": config,
            "produtos_ativos": produtos
        }     
        for ok in processar_dataset(**args_dataset).values(): 
            sucessos += 1 if ok else 0 
            falhas += 0 if ok else 1   

    log.info(f"Concluído: {sucessos} Sucessos | {falhas} Falhas.")