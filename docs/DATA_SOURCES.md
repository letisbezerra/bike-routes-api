# Data Sources — bike-routes-api

Detailed reference on the raw GeoJSON files this project ingests. `docs/CONTEXT.md` states the essential facts; this file has the detail for whoever writes the ingestion pipeline.

## Files

| File | Layer (`name`) | Features | Geometry | Size | CRS |
|---|---|---|---|---|---|
| `fortaleza_ciclovias.geojson` | Malha_cicloviaria | 447 | LineString | 323K | CRS84 (WGS84) |
| `estacionamentos_de_bicicleta.geojson` | Estacionamentos_de_bicicleta | 301 | Point | 97K | CRS84 (WGS84) |
| `estacoes_bicicletar.geojson` | DadosAbertos_EstacoesBicicletar | 267 | Point | 95K | EPSG:4674 (SIRGAS2000) |
| `pontos_de_descanso.geojson` | Parapes | 18 | Point | 11K | CRS84 (WGS84) |
| `rotas_ciclofaixa_de_lazer.geojson` | Rotas_ciclofaixa_de_Lazer | 3 | MultiLineString | 4.5K | CRS84 (WGS84) |

All bounding boxes fall within Fortaleza (lon ≈ -38.42 to -38.63, lat ≈ -3.69 to -3.87).

## Fields per file

- **Ciclovias** (LineString): `Nome`, `Id`, `Tipologia` (Ciclofaixas=313, Ciclovias=93, Ciclorrotas=32, Passeios compartilhados=9), `Extensão (km)`, `Trecho`, `Posição na via`, `Sentido de circulação`, `Pavimento`, `Elementos de separação`, `Data de implantação`, `Bairros`, `anoref`.
- **Estacionamentos** (Point): `Local`, `Quantidade de paraciclos`, `Tipo` (Paraciclo=296, Bicicletário=5), `Horário de funcionamento`, `Data de implantação` (98% null), `Número de vagas em bicletário` (98% null).
- **Estações Bicicletar** (Point): `ID`, `NOME`, `BAIRRO`, `REGIONAL`, `DATA INAUGURAÇÃO`, `STATUS`, `PATROCINADOR`, `VAGAS ATUAIS`, `LONG`/`LAT` (duplicates geometry), `TIPO`.
- **Pontos de descanso** (Point): `Nome`, `Imagem` (raw HTML).
- **Rotas ciclofaixa de lazer** (MultiLineString, only 3 features): `Rota` (name, e.g. "Rota Leste"), `n.apoios` (support-point count). No quality issues found — clean, complete, no nulls.

## Data quality issues to handle at ingestion

1. Leading whitespace in string values (ciclovias) — `.strip()` everything.
2. Null represented inconsistently — `""` in ciclovias vs. real `null` in estacionamentos.
3. Field naming has no shared convention across files — needs an explicit per-layer mapping to a unified internal schema.
4. CRS differs (EPSG:4674 vs CRS84) — reproject explicitly to WGS84/EPSG:4326, don't assume they already match.
5. `estacoes_bicicletar` duplicates coordinates in `LONG`/`LAT` properties — geometry is the source of truth, drop or validate-then-drop the properties.
6. `Id`/`ID` not reliable as identifier — 17 blank in ciclovias. API needs its own generated IDs.
7. `STATUS` has inconsistent values (`"EXISTENTE"` vs `"EXISTENTE 3.0"`) — needs normalization.
8. `Imagem` field is raw HTML from external Google-hosted URLs — **security risk** (stored XSS if ever returned unsanitized) and reliability risk (hotlinked, may break). Extract the URL only, or drop the field for v1.
9. `Data de implantação` and `Número de vagas em bicletário` in estacionamentos are ~98% null — not reliable enough to expose as-is.

## Practical notes

- All files are small (largest 323K) — load fully in memory with GeoPandas, no streaming needed.
- Mixed geometry types across layers (LineString vs Point) suggest one table per feature type in the database, not one generic table.

## License

Confirmed via the CKAN portal UI (resource metadata table, checked on the ciclovias/estacionamentos resources): **"Licença: Nenhuma Licença Fornecida"** — no license declared at all, not CC BY-SA or anything else. This is more precise than the earlier API check (which just showed an empty `license_id` field) — it's an explicit confirmation, not an inference.

**Decision**: no declared license means no blanket legal permission to redistribute — treat conservatively. Mandatory attribution ("Fonte: AMC/Prefeitura de Fortaleza") in the API's README regardless, and be ready to take data down or adjust if AMC ever objects. This is a portal published under the city's own "Dados Abertos" branding, so the intent is clearly public reuse — but intent isn't a license, so the safety net (attribution, no implied endorsement, ready to comply with a takedown) stays. See `docs/CONTEXT.md` section 3.

## Open (TBD)

- Source confirmed: `dados.fortaleza.ce.gov.br` (CKAN). Can pull via CKAN's Action API in the ingestion pipeline instead of manual download.
- Full list of layers beyond these 5 and update frequency — still TBD.
