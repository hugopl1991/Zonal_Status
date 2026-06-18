# Análise Zonal – Estoque de Carbono (Docker)

Scripts `Zonal_shp.py` e `Prodes_gpkg.py` rodando em contêiner Docker,
sem precisar instalar Python, GDAL ou qualquer dependência no PC.

---

## Estrutura de pastas

```
docker/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example          ← copie para .env e edite
└── scripts/
    ├── Zonal_shp.py
    └── Prodes_gpkg.py
```

---

## Pré-requisitos

| Software | Download |
|---|---|
| Docker Desktop (Windows) | https://docs.docker.com/desktop/install/windows/ |
| Git Bash ou PowerShell | já vem com o Windows |

Certifique-se de que o Docker Desktop está **rodando** antes de continuar.

---

## Configuração (única vez)

### 1. Configure os caminhos dos seus dados

Copie o arquivo de exemplo e edite com os caminhos reais do seu PC:

```bash
# No Git Bash ou PowerShell, dentro da pasta docker/
cp .env.example .env
```

Abra o `.env` e ajuste:

```env
# Pasta raiz — contém Dados/, resultados, logs
DIR_SUPRIMIDAS=C:/Users/lima-/Downloads/Suprimidas

# Pasta PAI do Compilado.shp (monte a pasta inteira, não o arquivo)
DIR_MASCARA_PAI=C:/Users/lima-/Downloads/Dados_Hugo/Shape
```

> **Atenção Windows:** use barras normais `/` nos caminhos, não `\`.

### 2. Construa a imagem Docker

```bash
docker compose build
```

Isso instala Python, GDAL, geopandas, exactextract etc. dentro da imagem.
Só precisa fazer **uma vez** (ou quando mudar o `requirements.txt`).

---

## Rodando os scripts

### Zonal_shp.py (análise zonal por shapefile)

```bash
docker compose run --rm zonal
```

### Prodes_gpkg.py (desmatamento via GeoPackage)

```bash
docker compose run --rm prodes
```

### Prodes_gpkg.py com argumentos (ex.: só um processamento)

```bash
# Um processamento, os dois produtos
docker compose run --rm prodes python scripts/Prodes_gpkg.py anual_bio

# Um processamento + um produto específico
docker compose run --rm prodes python scripts/Prodes_gpkg.py anual_bio biomassa
```

---

## Onde ficam os resultados?

Os arquivos de saída (`.xlsx`, `.shp`, `.log`) são gravados **dentro da pasta**
`DIR_SUPRIMIDAS` que você configurou no `.env` — ou seja, diretamente no seu
disco local, via volume Docker. Nada fica preso dentro do contêiner.

```
C:/Users/lima-/Downloads/Suprimidas/
├── resultado_bio_2024.xlsx
├── resultado_bio_2024.shp
├── resultado_solo_2024.xlsx
├── zonal_log_20250101_120000.log
└── ...
```

---

## Solução de problemas comuns

| Erro | Causa provável | Solução |
|---|---|---|
| `cannot find path` | Caminho no `.env` errado | Verifique com `/` e sem `\` no final |
| `No module named 'exactextract'` | Imagem desatualizada | `docker compose build --no-cache` |
| `GDAL: No such file or directory` | Arquivo `.tif` ou `.shp` não encontrado | Confirme que a pasta montada contém os dados esperados |
| `Permission denied` | Docker sem acesso à pasta | Libere a pasta em Docker Desktop → Settings → Resources → File Sharing |

### Ver logs em tempo real

```bash
docker compose logs -f zonal
```

### Entrar no contêiner para depurar

```bash
docker compose run --rm --entrypoint bash zonal
# dentro do contêiner:
ls /dados/Dados/
python scripts/Zonal_shp.py
```

---

## Rebuild após alterar os scripts

Os scripts ficam copiados dentro da imagem. Se você editá-los, rebuilde:

```bash
docker compose build
```

Ou, para evitar rebuild a cada edição, monte a pasta `scripts/` como volume
adicional no `docker-compose.yml`:

```yaml
    volumes:
      - ${DIR_SUPRIMIDAS}:/dados
      - ${DIR_MASCARA_PAI}:/mascara_dir
      - ./scripts:/app/scripts   # ← adicione esta linha
```

Assim qualquer edição local reflete imediatamente sem rebuild.
