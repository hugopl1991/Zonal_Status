# Análise Zonal – Estoque de Carbono (Docker)

Scripts **`Zonal_shp.py`** e **`Prodes_Overlay_one_year.py`** executados em contêiner Docker, sem necessidade de instalar Python, GDAL ou qualquer dependência no computador.

Toda a configuração do ambiente é realizada através do arquivo **`.env`**, enquanto os parâmetros dos processamentos são controlados pelo **`config.yaml`** e pelo **`processamentos.csv`** (regras do PRODES).

---

# Estrutura do Projeto

```text
docker/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── config.yaml            # Configurações dos scripts (estados, anos, produtos, etc.)
├── _env                   # Modelo para criação do .env (copie para .env)
└── scripts/
    ├── Zonal_shp.py
    └── Prodes_Overlay_one_year.py
```

## Pastas externas (computador do usuário)

```text
Suprimidas/                 (montada em /dados)
├── Dados/
│   ├── TAGB_BGB_Estoque/       # Rasters de biomassa por estado/ano
│   ├── Csoil_Estoque/          # Rasters de carbono do solo por estado/ano
│   ├── Suprimidas/2024/        # Shapefiles de supressão – 2024
│   ├── Suprimidas/2025/        # Shapefiles de supressão – 2025 (1º e 2º sem.)
│   └── PRODES/                 # GeoPackages do PRODES (Amazônia / Mata Atlântica)
├── resultado_*.xlsx / *.gpkg   # Saídas geradas pelos scripts
└── *_log_*.log                 # Logs de execução (zonal e prodes)

Shape/                       (montada em /mascara_dir)
└── Compilado.shp               # Máscara da área de interesse (Vale)

Tabela/                      (montada em /tabelas)
└── processamentos.csv          # Regras de processamento do PRODES
```

---

# Como funciona

O projeto utiliza três arquivos de configuração independentes.

| Arquivo                  | Responsabilidade                                                                                      |
| --------------------------| ------------------------------------------------------------------------------------------------------ |
| **.env**                 | Informa ao Docker onde estão as pastas do computador (volumes).                                       |
| **config.yaml**          | Define anos, estados, biomas, produtos, nomes de arquivos e parâmetros globais dos dois scripts.      |
| **processamentos.csv**   | Define cada processamento do PRODES (período, bioma/gpkg, layer de origem, nome de saída), lido pelo `Prodes_Overlay_one_year.py`. |

Essa separação permite alterar os parâmetros dos processamentos sem modificar o código Python.

---

# Pré-requisitos

* Docker Desktop 4.x ou superior
* Git Bash ou PowerShell

> **Importante:** Antes de executar qualquer comando, verifique se o Docker Desktop está em execução.

---

# Configuração Inicial (executar apenas uma vez)

## 1. Criar o arquivo `.env`

Copie o arquivo de exemplo.

Edite o arquivo `.env` com os caminhos existentes no seu computador.

```text
# Pasta que contém as tabelas de configuração (processamentos.csv)
DIR_TABELAS=C:/Users/lima-/Downloads/Dados_Hugo/Git/ITV_Indicadores_Ecossistemas/Supressão/Docker/Tabela

# Pasta principal onde estão os dados e serão gravados resultados e logs
DIR_SUPRIMIDAS=C:/Users/lima-/Downloads/Suprimidas

# Pasta PAI que contém o arquivo Compilado.shp
DIR_MASCARA_PAI=C:/Users/lima-/Downloads/Dados_Hugo/Shape
```

### Windows

Utilize sempre barras normais:

```text
C:/Users/Usuario/Pasta
```

Evite utilizar:

```text
C:\Users\Usuario\Pasta
```

---

## 2. Editar o `config.yaml`

O arquivo `config.yaml` contém os parâmetros globais e o catálogo de produtos utilizados pelos scripts.

Exemplos de configurações:

* Estados (zonal e PRODES têm listas independentes)
* Produtos (`biomassa`, `solo`) — pastas e padrões de nome de arquivo raster
* Anos e semestres de supressão vegetal (`zonal.anos`)
* GeoPackages do PRODES por bioma (Amazônia / Mata Atlântica)
* Caminho do `processamentos.csv` (`prodes.processamentos_csv`)
* Fator de conversão C → CO2e, área do pixel, CRS de cálculo e de saída

Sempre que for necessário alterar algum processamento, basta editar esse arquivo.

Não é necessário alterar o código Python.

## 3. Editar o `processamentos.csv`

Cada linha define **um** processamento do PRODES. Colunas:

| Coluna         | Descrição                                                                                   |
| -------------- | --------------------------------------------------------------------------------------------- |
| `chave`        | Identificador único, usado para rodar um processamento específico (ex.: `anual_bio`).        |
| `nome`         | Nome descritivo (apenas informativo).                                                        |
| `tipo`         | `anual` (série de anos) ou `acumulado` (um único raster/ano fixo).                            |
| `ano_inicio`   | Primeiro ano da série (somente para `tipo=anual`).                                            |
| `ano_fim`      | **Último ano incluído** na série (somente para `tipo=anual`) — o script já ajusta o `range()` internamente, não é necessário somar +1. |
| `ano_raster`   | Ano fixo do raster (somente para `tipo=acumulado`).                                            |
| `gpkg`         | `amazonia` ou `mata` — bioma/GeoPackage de origem.                                             |
| `layer`        | Nome da camada dentro do GeoPackage do PRODES.                                                |
| `saida_base`   | Prefixo do nome da camada/arquivo de saída.                                                   |

Linhas vazias em colunas não aplicáveis ao `tipo` (ex.: `ano_raster` em processamentos anuais) devem ficar em branco.

---

# Construindo a imagem Docker

Execute apenas na primeira utilização.

```bash
docker compose build
```

Também será necessário executar novamente caso ocorra alguma destas situações:

* alteração do `Dockerfile`;
* alteração do `requirements.txt`;
* atualização da imagem base do Python.

Alterações em:

* scripts Python;
* `config.yaml`;
* `.env`;
* `processamentos.csv`;

**não exigem reconstrução da imagem** — desde que o volume dos scripts esteja montado (ver seção *"Atualizando Scripts sem Rebuild"* abaixo).

---

# Fluxo de Utilização

Após a configuração inicial, o fluxo normal será:

1. Editar o `.env` (quando necessário).
2. Editar o `config.yaml` e/ou `processamentos.csv`.
3. Executar o processamento.

Não é necessário executar `docker compose build` novamente.

---

# Executando os Scripts

## Análise Zonal

```bash
docker compose run --rm zonal
```

---

## Processamento PRODES

Executa todos os processamentos definidos no `processamentos.csv`, para todos os produtos do `config.yaml`.

```bash
docker compose run --rm prodes
```

---

## Executar apenas um processamento

Use a `chave` definida no `processamentos.csv`:

```bash
docker compose run --rm prodes python scripts/Prodes_Overlay_one_year.py anual_bio
```

---

## Executar um processamento e um produto específico

Use a `chave` do CSV seguida da chave do produto no `config.yaml` (`biomassa` ou `solo`):

```bash
docker compose run --rm prodes python scripts/Prodes_Overlay_one_year.py anual_bio biomassa
```

---

# Onde ficam os resultados?

Todos os arquivos produzidos pelos scripts são gravados diretamente na pasta configurada em **DIR_SUPRIMIDAS**.

Nenhum resultado fica armazenado dentro do contêiner Docker.

Exemplo:

```text
Suprimidas/
├── resultado_2024_biomassa.xlsx
├── amazonia_bio_2008_2025_biomassa.xlsx
├── resultados_vale.gpkg
├── resultados_amazonia.gpkg
├── resultados_mata_atlantica.gpkg
├── zonal_log_20260101_120000.log
├── prodes_log_20260101_120500.log
└── ...
```

---

# Estrutura dos Volumes Docker

Os diretórios do computador são montados dentro do contêiner conforme o esquema abaixo.

```text
Computador
│
├── Suprimidas
│      └────────────► /dados
│
├── Shape
│      └────────────► /mascara_dir
│
├── Tabela
│      └────────────► /tabelas          (apenas serviço "prodes")
│
└── config.yaml
       └────────────► /app/config.yaml


Docker
│
├── Python 3.13
├── GDAL
├── GeoPandas
├── Rasterio
├── ExactExtract
└── Demais dependências
```

---

# Depuração

## Ver logs em tempo real

```bash
docker compose logs -f zonal
```

---

## Acessar o terminal do contêiner

```bash
docker compose run --rm --entrypoint bash zonal
```

Exemplos de comandos dentro do contêiner:

```bash
ls /dados

ls /dados/Dados

python scripts/Zonal_shp.py
```

---

# Solução de Problemas

| Problema                      | Possível causa                                | Solução                                                                    |
| ------------------------------ | ---------------------------------------------- | ----------------------------------------------------------------------------- |
| cannot find path               | Caminho incorreto no `.env`                     | Verifique se utilizou barras `/` e se a pasta existe.                        |
| KeyError                       | Erro no `config.yaml`                           | Verifique a indentação e a estrutura do YAML.                                |
| GDAL: No such file             | Arquivo inexistente                             | Confirme se o raster ou shapefile está na pasta montada.                     |
| Permission denied              | Pasta não compartilhada no Docker Desktop       | Libere a pasta em **Settings → Resources → File Sharing**.                  |
| `no such file or directory` (Prodes) | `chave` incorreta ou ausente no `processamentos.csv` | Confira se a `chave` passada como argumento existe no CSV.               |

---

# Observações

* O `.env` define apenas os caminhos do computador (`DIR_TABELAS`, `DIR_SUPRIMIDAS`, `DIR_MASCARA_PAI`).
* O `config.yaml` controla os parâmetros globais e o catálogo de produtos dos processamentos.
* O `processamentos.csv` controla as regras específicas de cada processamento do PRODES (evita listar tudo dentro do YAML).
* Os resultados permanecem sempre no computador do usuário — nada fica salvo dentro do contêiner.
* A imagem Docker precisa ser reconstruída apenas quando houver alterações nas dependências do ambiente (`Dockerfile` / `requirements.txt`).
