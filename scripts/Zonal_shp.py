""" 
Análise Zonal Estatística – Estoque de Carbono (Via Docker e config.yaml) 
Saída consolidada no arquivo resultados_vale.gpkg 
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

# ════════════════════════════════════════════════════════════════════════════ 
# CARREGAMENTO DAS CONFIGURAÇÕES (YAML)
# ════════════════════════════════════════════════════════════════════════════ 
with open("config.yaml", "r", encoding="utf-8") as f: # Processa fisicamente e trava um ponteiro em cima do config.yaml 
    CFG = yaml.safe_load(f) 

DIR_RAIZ = Path(os.environ.get("DIR_RAIZ", CFG["global"]["dir_raiz"])) # Extrai as configurações que lidam com variáveis globais do servidor onde o script foi plugado. Prioriza o uso do sistema local, senão vai pelo YAML.
FATOR_C_CO2 = CFG["global"]["fator_c_co2"] # Lê as normas específicas descritas no dicionário sob o escopo global referente à conversão estipulada C/CO2
AREA_PIXEL_HA = CFG["global"]["area_pixel_ha"] # Lê informações contidas no nó global referenciando tamanho real pré-calculado em um pixel da área mapeada (em hectares)
CRS_AREA = CFG["global"]["crs_area"] # Lê do YAML qual norma técnica está associada ao cálculo preciso espacial dentro da área local brasileira de avaliação (geralmente SIRGAS 2000 correspondente)
CRS_SAIDA = CFG["global"]["crs_saida"] # Indica para o interpretador qual é a configuração geográfica de finalização que todos os frames devem se alinhar no output global
C_DECIMAIS = CFG["global"]["c_decimais"] # Quantidade de casa decimais usadas no arrendodamento.

ESTADOS = CFG["zonal"]["estados"] # Acessa a raiz específica de rotinas locais do algoritmo de análise zonal estipulando em quais UFs e partes da rede atuar
CONFIGS_ANO = CFG["zonal"]["anos"] # Lê parâmetros da árvore atrelada a métricas de tempos anuais presentes dentro da variável das configurações ativas do modelo zonal
PRODUTOS = CFG["produtos"] # Atrela subchaves das análises, tais como estoques, biomassas em geral (TAGB e Csoil) lendo-as diretamente do YAML

COLUNAS_EXCLUIR = ["Shape_Leng", "Shape_Area"] # Definição antecipada da lista de vetores temporários ou inúteis, herdados de ferramentas de modelagem externas (ex. ArcGIS), para não contaminar a estrutura da matriz analítica

def configurar_log() -> logging.Logger: # Declara uma função sem argumentos que retorna um objeto Logger configurado
    ts = datetime.now().strftime("%Y%m%d_%H%M%S") # Gera uma string de texto (timestamp) formatada com ano, mês, dia, hora, minuto e segundo
    logger = logging.getLogger("zonal") # Retorna (e gera, se não houver um) um rastreador independente referenciado pela sigla explícita 'zonal' 
    logger.setLevel(logging.DEBUG) # Configura a severidade mínima que será registrada (tudo de DEBUG para cima será gravado)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S") # Prepara um formato estruturado padronizado para a escrita das mensagens do log
    
    for h in [logging.FileHandler(DIR_RAIZ / f"zonal_log_{ts}.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)]: # Distribui ações definindo dois ouvintes fixos.
        h.setFormatter(fmt) # Associa o formatador (criado acima) à atual saída iterada no loop
        logger.addHandler(h) # Acopla esse manipulador recém-configurado à instância principal do logger
    return logger # Retorna o objeto logger pronto para ser invocado pelo resto do script

log = configurar_log() 

def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame: 
    df = df.rename(columns={"ID_1": "ID", "SUM_area_h": "area_ha"}) # Altera forçadamente textos do cabeçalho caso ocorram anomalias identificadas previamente durante gerações via sistemas secundários (QGIS)
    if "ID_1" in df.columns and "ID" in df.columns: df["ID"] = df["ID"].fillna(df.pop("ID_1")) # Bloqueio condicional que corrige erros estruturais e transfere (pop) eventuais colunas de IDs duplicadas ou deslocadas, suprindo e arranjando falhas pontuais (fillna) no objeto primário correspondente 
    if "SUM_area_h" in df.columns and "area_ha" in df.columns: df["area_ha"] = df["area_ha"].fillna(df.pop("SUM_area_h")) # O mesmo princípio aplicado aos blocos espaciais de polígonos referentes à identificação e correção paramétrica das áreas
    return df 

def processar(ano: str, config_ano: dict, prod_key: str, prod_cfg: dict) -> bool: 
    geodataframes = [] # Cria e esvazia matriz virtual para acoplagem das respostas

    for semestre, padrao in config_ano["semestres"]: 
        for estado in ESTADOS: 
            caminho_shp = DIR_RAIZ / config_ano["pasta_shape"] / padrao.format(estado=estado) # Interpola variáveis textuais e aponta o ponteiro fixo criando caminhos válidos atrelados as características mapeadas dos limites e contornos dos lotes no ano local
            caminho_ras = DIR_RAIZ / prod_cfg["dir_raster"] / prod_cfg["subpasta"].format(estado=estado) / prod_cfg["arquivo"].format(estado=estado, ano=ano) # Utiliza as mesmas concatenações dinâmicas de texto, apontando à correspondência visual da foto em forma de diretório estrutural físico gerando acesso final TIF

            try: 
                gdf = gpd.read_file(caminho_shp).to_crs(CRS_AREA) # Dispara processamento paralelo via gdal de mapeamento topográfico do shape local projetando seus cálculos pro fuso padrão do limite continental (EPSG configurado para cálculo de Área)
                gdf["area_c_ha"] = (gdf.geometry.area / 10_000).round(C_DECIMAIS) # Retira os cálculos do frame bruto em dimensão planar natural (geralmente metros) fazendo um shift paramétrico equivalente para extrair dimensões base e aproxima precisões gerando escala simplificada final
                gdf = gdf.to_crs(CRS_SAIDA) 

                with rasterio.open(caminho_ras) as src: # Cria um gerenciador de contexto do Python que abrirá a imagem (tif) e garantirá seu fechamento de memória em seguida
                    stats = exact_extract(str(caminho_ras), gdf.to_crs(src.crs), ["count", "sum", "mean", "min", "max"], output="pandas") # Usando C/C++ por baixo, extrai em um pd.DataFrame contagem, soma, mínima e máxima, enquanto faz o ajuste do CRS do recorte para ficar alinhado à imagem

                gdf_out = gdf.drop(columns=COLUNAS_EXCLUIR, errors="ignore").reset_index(drop=True) # Destila excessos tabulares eliminando vetores residuais vindos no dataframe original antes de resetar contadores posicionais puros das linhas da nova lista
                if ano == "2025": gdf_out = normalizar_colunas(gdf_out) # Cria interceptação preventiva na série temporal atrelando chamada explícita do processo saneador das colunas, contornando a estrutura anômala gerada nos arquivos mapeados em 2025 

                gdf_out = gdf_out.assign( # Concatena colunas de medição geradas pelo bloco analítico exactextract na saída tabular bruta principal
                    produto=prod_key, estado=estado, semestre=semestre, ano=ano, # Registra o escopo da operação em colunas simples como indexador informacional 
                    cnt_pix=stats["count"].round(C_DECIMAIS), 
                    mean=(stats["mean"] * FATOR_C_CO2).round(C_DECIMAIS), 
                    min=(stats["min"] * FATOR_C_CO2).round(C_DECIMAIS), 
                    max=(stats["max"] * FATOR_C_CO2).round(C_DECIMAIS), 
                    sum_bruta=(stats["sum"] * FATOR_C_CO2).round(C_DECIMAIS),  
                    sum_conv=(stats["sum"] * FATOR_C_CO2 * AREA_PIXEL_HA).round(C_DECIMAIS)  
                ) # Finaliza inserção modular das colunas temporárias processadas pela função do panda
                geodataframes.append(gdf_out) # Atrela sub-bloco estadual mapeado perfeitamente na fila mestra do interpretador
                log.info(f"✔ {estado} {semestre}") 

            except Exception as exc: 
                if "No such file" in str(exc):  
                    log.warning(f"✗ {estado} {semestre}: arquivo não encontrado.") 
                else: 
                    log.warning(f"✗ {estado} {semestre}: {exc}") 

    if not geodataframes: # Condição global para ver se toda a fila mapeada rodou vazio, finalizando interações e processamento inócuo
        return False 

    gdf_final = gpd.GeoDataFrame(pd.concat(geodataframes, ignore_index=True), geometry="geometry", crs=CRS_SAIDA) # Condensa blocos empilhados dos subitens gerados nas operações atreladas ao CRS padrão forjado via Pandas 
    nome_camada = f"{ano}_{prod_key}" # Amarra texto provisório formatando chave com base de ciclo estipulada via loop mestre para dar título à camada de saída
    gpkg_saida = DIR_RAIZ / "resultados_vale.gpkg" # Interpola arquivo final gerando repositório matriz dos pacotes com extensão GeoPackage num ponteiro central 
    
    # Salva Excel # Informa visualmente salvamento tabular avulso e limpo de index base
    gdf_final.drop(columns="geometry").rename(columns={"mean": "mean_MgCO2e_ha", "min": "min_MgCO2e_ha", "max": "max_MgCO2e_ha", "sum_bruta": "sum_MgCO2e_ha", "sum_conv": "sum_MgCO2e"}).to_excel(DIR_RAIZ / f"resultado_{nome_camada}.xlsx", index=False)  
    
    # Salva como nova camada no GeoPackage consolidado # Informa visualmente etapa contínua de salvamento espacial agregado no mesmo arquivo GPKG alvo central 
    gdf_final.to_file(gpkg_saida, layer=nome_camada, driver="GPKG") 
    log.info(f"Salvo no GPKG -> Layer: {nome_camada}") 
    
    return True 

if __name__ == "__main__": 
    log.info("MASTER – ANÁLISE ZONAL ESTATÍSTICA (VALE)")  
    sucessos = falhas = 0 

    for p_key, p_cfg in PRODUTOS.items(): 
        for ano, cfg_ano in CONFIGS_ANO.items(): 
            
            # Empacotando os argumentos
            arg_dict = {
                "ano": ano,
                "config_ano": cfg_ano,
                "prod_key": p_key,
                "prod_cfg": p_cfg
            }
            
            # Desempacotando na chamada
            if processar(**arg_dict): 
                sucessos += 1 
            else: 
                falhas += 1 

    log.info(f"Concluído: {sucessos} Sucessos | {falhas} Falhas.")