# Subsidencia en Vaca Muerta con InSAR

Experimento: **¿se puede observar deformación del suelo (subsidencia/uplift) en Vaca Muerta con datos
satelitales Sentinel-1 gratuitos, y qué dicen los datos?**

🌐 **Sitio:** https://mpodeley.github.io/vaca-muerta-insar/

Sitio MkDocs Material con las demos interactivas, el método paso a paso reproducible, la interpretación
de resultados y las fuentes. Los scripts del pipeline (Sentinel-1 → HyP3 → MintPy → ERA5) están en
[`docs/pipeline/`](docs/pipeline).

## Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdocs serve   # http://127.0.0.1:8000
```

El push a `main` despliega automáticamente a GitHub Pages (ver `.github/workflows/deploy.yml`).
